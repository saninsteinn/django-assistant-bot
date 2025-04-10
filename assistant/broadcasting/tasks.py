import logging
from typing import Dict, List

from asgiref.sync import sync_to_async, async_to_sync
from celery import shared_task
from django.utils import timezone
from django.db import transaction

# NOTE: Keeping dependencies on bot components for now.
# Ideally, the notifications app should have its own mechanism
# for platform interaction and message formatting.
from assistant.assistant.queue import CeleryQueues # Ensure this path is correct
from assistant.bot.domain import answer_from_dict, BotPlatform, MultiPartAnswer, SingleAnswer
from assistant.bot.exceptions import UserUnavailableError
# Import models needed to update instance status
from assistant.bot.models import Instance, Bot, BotUser
from assistant.bot.utils import get_bot_platform

# Broadcasting module imports
from .models import BroadcastCampaign
# Import specific service functions instead of the whole module
from .services import initiate_campaign_sending, record_batch_results, finalize_campaign

logger = logging.getLogger(__name__)


# Renamed from _post_notification, kept async helper for sending single/multi-part message
async def _post_notification_helper(platform: BotPlatform, chat_id: str, answer):
    """Helper function to post single or multi-part answers via a platform."""
    if isinstance(answer, MultiPartAnswer):
        answers = answer.parts
    elif isinstance(answer, SingleAnswer): # Handle SingleAnswer explicitly
        answers = [answer]
    else:
        # Log or raise error for unsupported types if necessary
        logger.warning(f"Unsupported answer type for notification: {type(answer)}")
        raise TypeError(f"Unsupported answer type: {type(answer)}") # Raise to count as failure

    for answer_part in answers:
        # This maintains the dependency on the BotPlatform interface from the bot app.
        await platform.post_answer(chat_id, answer_part)


# Renamed from send_broadcast, adapted for batch processing via Celery
@shared_task(queue=CeleryQueues.BROADCASTING.value)
def send_broadcast_batch(campaign_id: int, bot_codename: str, platform_codename: str, chat_ids: List[str], message_content_data: Dict):
    """
    Sends a broadcast message batch to a list of chat IDs.
    Handles platform interaction and error reporting, including UserUnavailableError.
    Triggers result recording task afterwards.
    """
    logger.info(f"Task received: Send batch for campaign {campaign_id}, bot {bot_codename}, platform {platform_codename} to {len(chat_ids)} users.")
    # Calls the renamed/adapted async worker
    return async_to_sync(_send_broadcast_batch_async)(campaign_id, bot_codename, platform_codename, chat_ids, message_content_data)


# Renamed from _send_broadcast, adapted async worker for batches
async def _send_broadcast_batch_async(campaign_id: int, bot_codename: str, platform_codename: str, chat_ids: List[str], message_content_data: Dict):
    """
    Async worker coroutine for sending a batch.
    Marks users as unavailable if UserUnavailableError is raised during sending.
    Triggers recording of batch results.
    """
    successful_sends = 0
    failed_sends = 0
    unavailable_user_ids = [] # Track users to mark unavailable

    # 1. Get Platform Instance
    try:
        # Use sync_to_async as get_bot_platform might do DB lookups
        platform = await sync_to_async(get_bot_platform)(bot_codename, platform_codename)
    except Exception as e:
        logger.error(f"Failed to get platform {platform_codename} for bot {bot_codename} in campaign {campaign_id}: {e}. Failing entire batch.")
        failed_sends = len(chat_ids) # Mark all as failed for this batch
        # Trigger result recording immediately, even on platform failure
        record_batch_results_task.delay(campaign_id, successful_sends, failed_sends)
        return # Cannot proceed without platform

    # 2. Deserialize Message Content
    try:
        # answer_from_dict is likely synchronous
        message_content = answer_from_dict(message_content_data)
    except Exception as e:
        logger.error(f"Error deserializing message_content_data in campaign {campaign_id}: {e}\nData: {message_content_data}. Failing entire batch.")
        failed_sends = len(chat_ids)
        record_batch_results_task.delay(campaign_id, successful_sends, failed_sends)
        return # Cannot send if content is invalid

    # 3. Iterate and Send using the helper (Ensure platform and message_content are not None)
    if platform and message_content:
        for chat_id in chat_ids:
            try:
                await _post_notification_helper(platform, chat_id, message_content)
                successful_sends += 1
                # Log successful delivery at DEBUG level
                logger.info(f"Successfully sent broadcast campaign {campaign_id} to chat_id {chat_id}")
            except UserUnavailableError as e:
                logger.warning(f'User {e.chat_id} unavailable during broadcast campaign {campaign_id} (bot {bot_codename}). Marking for update.')
                failed_sends += 1
                # Use the chat_id from the exception context
                unavailable_user_ids.append(e.chat_id) # Collect user ID to update later
            except Exception as e:
                logger.error(f'Error sending broadcast campaign {campaign_id} to chat_id {chat_id} (bot {bot_codename}): {e}')
                failed_sends += 1

    # 4. Mark Users as Unavailable (if any) - Moved to a separate sync helper
    if unavailable_user_ids:
        logger.info(f"Attempting to mark {len(unavailable_user_ids)} users as unavailable for campaign {campaign_id}, bot {bot_codename}.")
        # Use sync_to_async to perform the database update via the helper
        await sync_to_async(_mark_users_unavailable)(bot_codename, platform_codename, unavailable_user_ids)

    # 5. Record Batch Results - Trigger next task
    logger.info(f"Batch sending finished for campaign {campaign_id}. Success: {successful_sends}, Failed: {failed_sends}. Triggering result recording.")
    # Use .delay to call the result recording task asynchronously
    record_batch_results_task.delay(campaign_id, successful_sends, failed_sends)


# Synchronous helper function for database updates
def _mark_users_unavailable(bot_codename: str, platform_codename: str, user_ids: List[str]):
    """
    Marks instances associated with the given user IDs, bot, and platform as unavailable.
    Runs synchronously for efficient DB update.
    """
    if not user_ids:
        return

    try:
        # Find the Bot model first
        bot = Bot.objects.get(codename=bot_codename)
    except Bot.DoesNotExist:
        logger.error(f"Cannot mark users unavailable: Bot {bot_codename} not found.")
        return

    # Optimized query: Filter Instance directly using related user fields
    instances_to_update = Instance.objects.filter(
        bot=bot,
        user__platform=platform_codename, # Filter by platform of the related user
        user__user_id__in=user_ids,      # Filter by user_id of the related user
        is_unavailable=False             # Only update those not already unavailable
    )

    # Perform the update
    updated_count = instances_to_update.update(is_unavailable=True)

    if updated_count > 0:
        logger.info(f"Successfully marked {updated_count} instances as unavailable for bot {bot_codename}, platform {platform_codename}.")
    else:
        logger.info(f"No instances needed updating (likely already marked or users not found for this bot/platform) for bot {bot_codename}, platform {platform_codename}.")


# NOTE: This requires Celery Beat to be configured and running.
# You'll need to add this task to your CELERY_BEAT_SCHEDULE in settings.
@shared_task(name="broadcasting.check_scheduled_broadcasts", queue=CeleryQueues.BROADCASTING.value)
def check_scheduled_broadcasts():
    """
    Periodic task to check for scheduled broadcast campaigns that are due.
    """
    logger.info("Checking for scheduled broadcasts...")
    now = timezone.now()
    # Find campaigns that are scheduled and due
    campaigns_to_start = BroadcastCampaign.objects.filter(
        status=BroadcastCampaign.Status.SCHEDULED,
        scheduled_at__lte=now
    ).values_list('id', flat=True) # Get only IDs

    count = 0
    for campaign_id in campaigns_to_start:
        logger.info(f"Found scheduled campaign ready to start: {campaign_id}. Triggering sending task.")
        # Trigger the task to initiate sending for each campaign
        start_campaign_sending_task.delay(campaign_id)
        count += 1

    if count > 0:
        logger.info(f"Triggered sending tasks for {count} campaigns.")
    else:
        logger.info("No scheduled broadcasts found ready to start.")


@shared_task(queue=CeleryQueues.BROADCASTING.value)
def start_campaign_sending_task(campaign_id: int):
    """
    Task to initiate the sending process for a specific campaign.
    Calls the async service function `initiate_campaign_sending`.
    """
    logger.info(f"Task received: Initiate sending for campaign {campaign_id}.")
    try:
        # Call the imported async service function using async_to_sync
        async_to_sync(initiate_campaign_sending)(campaign_id)
        logger.info(f"Successfully initiated (or queued for initiation) campaign {campaign_id}.")
    except Exception as e:
        logger.exception(f"Critical error during task execution for initiating campaign {campaign_id}: {e}")
        # Attempt to mark the campaign as FAILED if initiation fails badly here
        try:
            campaign = BroadcastCampaign.objects.filter(id=campaign_id).first()
            if campaign and campaign.status not in [BroadcastCampaign.Status.COMPLETED, BroadcastCampaign.Status.FAILED]:
                 campaign.status = BroadcastCampaign.Status.FAILED
                 campaign.completed_at = timezone.now() # Mark completion time
                 campaign.save(update_fields=['status', 'completed_at', 'updated_at'])
                 logger.error(f"Marked campaign {campaign_id} as FAILED due to initiation task error.")
        except Exception as update_err:
            logger.error(f"Failed to mark campaign {campaign_id} as FAILED after initiation task error: {update_err}")


@shared_task(queue=CeleryQueues.BROADCASTING.value)
def record_batch_results_task(campaign_id: int, successful: int, failed: int):
    """
    Task to record the results of a completed sending batch.
    Calls the service function `record_batch_results`.
    """
    logger.info(f"Task received: Record results for campaign {campaign_id} (Success: {successful}, Failed: {failed}).")
    try:
        # Call the imported service function (which is already decorated with @sync_to_async)
        # Wrap the call in async_to_sync to properly execute the coroutine
        async_to_sync(record_batch_results)(campaign_id, successful, failed)

    except Exception as e:
        logger.exception(f"Error recording batch results via task for campaign {campaign_id}: {e}")


@shared_task(queue=CeleryQueues.BROADCASTING.value)
def finalize_campaign_task(campaign_id: int):
    """
    Task to finalize a campaign. Calls the async service function `finalize_campaign`.
    This can be triggered by `record_batch_results` when all batches are done.
    """
    logger.info(f"Task received: Finalize campaign {campaign_id}.")
    try:
        # Call the imported async service function using async_to_sync
        async_to_sync(finalize_campaign)(campaign_id)
        logger.info(f"Finalization task completed for campaign {campaign_id}.")
    except Exception as e:
        logger.exception(f"Error finalizing campaign {campaign_id} via task: {e}")