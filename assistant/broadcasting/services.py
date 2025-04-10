import logging
from typing import List, TYPE_CHECKING, Dict

from asgiref.sync import sync_to_async
from django.db import transaction
from django.utils import timezone

# Assuming models are in .models and bot models are in assistant.bot.models
from .models import BroadcastCampaign
from assistant.bot.models import Instance, BotUser # Need these for targeting

# Import tasks for runtime execution
# from .tasks import send_broadcast_batch, finalize_campaign_task


logger = logging.getLogger(__name__)


# --- Core Service Functions ---

def resolve_target_chat_ids(campaign: BroadcastCampaign) -> List[str]:
    """
    Resolves the target chat IDs for a given broadcast campaign (Synchronous ORM version).

    Currently targets all active (not unavailable) instances associated with the campaign's bot.
    TODO: Implement filtering based on campaign.target_criteria in the future.
    """
    logger.info(f"Resolving target chat IDs for campaign {campaign.id} (Bot: {campaign.bot.id})")
    try:
        # Use synchronous ORM call with values_list
        chat_ids_qs = Instance.objects.filter(
            bot=campaign.bot,
            is_unavailable=False
        ).select_related('user').distinct('user__user_id').values_list('user__user_id', flat=True)

        # Evaluate the queryset
        chat_ids = list(chat_ids_qs)

        logger.info(f"Resolved {len(chat_ids)} target chat IDs for campaign {campaign.id}.")
        return chat_ids
    except Exception as e:
        logger.error(f"Error resolving target chat IDs for campaign {campaign.id}: {e}")
        return [] # Return empty list on error


async def schedule_campaign_sending(campaign: BroadcastCampaign):
    """
    Validates the campaign and sets its status for sending.

    If scheduled_at is set, marks it as SCHEDULED.
    If scheduled_at is not set, it could potentially trigger immediate sending (requires task).
    For now, focuses on setting the status.
    """
    logger.info(f"Scheduling campaign {campaign.id}...")
    if campaign.status != BroadcastCampaign.Status.DRAFT:
        logger.warning(f"Campaign {campaign.id} is not in DRAFT status. Current status: {campaign.status}. Cannot schedule.")
        return False

    if campaign.scheduled_at and campaign.scheduled_at > timezone.now():
        campaign.status = BroadcastCampaign.Status.SCHEDULED
        await sync_to_async(campaign.save)(update_fields=['status'])
        logger.info(f"Campaign {campaign.id} set to SCHEDULED for {campaign.scheduled_at}.")
        return True
    elif not campaign.scheduled_at:
        # Option 1: Immediately trigger sending (requires async task call)
        logger.info(f"Campaign {campaign.id} has no scheduled time. Triggering immediate sending.")
        # Placeholder: Need to call the task that initiates sending
        # from .tasks import start_campaign_sending_task
        # await sync_to_async(start_campaign_sending_task.delay)(campaign.id)
        # For now, just log. The actual triggering will be handled by admin action or task.
        # Or set to a status that indicates manual trigger is needed?
        # Let's assume for now an admin action or separate process handles 'Send Now'.
        # If called without schedule time, maybe log a warning or require explicit action?
        logger.warning(f"Campaign {campaign.id} has no scheduled time. Manual trigger required.")
        # Or should we set it to scheduled and let the periodic task pick it up immediately?
        # Setting to SCHEDULED seems safer, letting the standard flow handle it.
        campaign.status = BroadcastCampaign.Status.SCHEDULED
        await sync_to_async(campaign.save)(update_fields=['status'])
        logger.info(f"Campaign {campaign.id} set to SCHEDULED for immediate pickup by task runner.")
        return True
    else: # Scheduled time is in the past
        logger.warning(f"Campaign {campaign.id} scheduled time {campaign.scheduled_at} is in the past. Setting to SCHEDULED for immediate pickup.")
        campaign.status = BroadcastCampaign.Status.SCHEDULED
        await sync_to_async(campaign.save)(update_fields=['status'])
        return True


async def initiate_campaign_sending(campaign_id: int):
    """
    Initiates the sending process for a broadcast campaign.

    - Fetches the campaign.
    - Checks status.
    - Updates status to SENDING.
    - Resolves target chat IDs.
    - Updates total_recipients.
    - Batches chat IDs and dispatches tasks for sending.
    """
    logger.info(f"Initiating sending process for campaign ID: {campaign_id}")
    try:
        # Use sync_to_async for the initial fetch
        campaign = await sync_to_async(BroadcastCampaign.objects.select_related('bot').get)(id=campaign_id)
    except BroadcastCampaign.DoesNotExist:
        logger.error(f"Cannot initiate sending: BroadcastCampaign with ID {campaign_id} not found.")
        return

    # Check if campaign is in a state that allows sending
    if campaign.status not in [BroadcastCampaign.Status.SCHEDULED]:
        logger.warning(f"Campaign {campaign_id} is not in SCHEDULED status (current: {campaign.status}). Cannot start sending.")
        # If triggered manually (e.g. 'Send Now' action), it might be DRAFT.
        # We might adjust this check depending on how 'Send Now' is implemented.
        # For scheduled tasks, checking for SCHEDULED is correct.
        return

    # --- Start Transaction --- (Locking and Status Update)
    try:
        @sync_to_async
        def run_initiation_in_transaction():
            with transaction.atomic():
                # Reload campaign within transaction
                # Select related bot needed for bot_codename later
                campaign_locked = BroadcastCampaign.objects.select_for_update().select_related('bot').get(id=campaign_id)

                if campaign_locked.status != BroadcastCampaign.Status.SCHEDULED:
                    logger.warning(f"Campaign {campaign_id} status changed. Aborting.")
                    return None # Indicate abortion

                campaign_locked.status = BroadcastCampaign.Status.SENDING
                campaign_locked.started_at = timezone.now()

                chat_ids = resolve_target_chat_ids(campaign_locked)
                total_recipients = len(chat_ids)
                campaign_locked.total_recipients = total_recipients
                campaign_locked.save(update_fields=['status', 'started_at', 'total_recipients'])
                logger.info(f"Campaign {campaign_id} status SENDING, targeting {total_recipients} recipients.")

                # Return locked campaign object and chat_ids for dispatching
                return campaign_locked, chat_ids

        # Run the transaction
        result = await run_initiation_in_transaction()
        if result is None: return
        campaign, chat_ids = result # Unpack locked campaign and chat_ids
        total_recipients = len(chat_ids)

        # --- Finalize immediately if no recipients ---
        if not chat_ids:
            logger.warning(f"Campaign {campaign_id} has no recipients. Finalizing.")
            await finalize_campaign(campaign_id)
            return

        # --- Prepare for Dispatching (outside transaction) ---
        batch_size = 100
        # Get platform from the campaign object
        platform_codename = campaign.platform
        bot_codename = campaign.bot.codename # Already loaded via select_related

        if not platform_codename:
            # This check might be redundant if platform has a default and cannot be null,
            # but keep for safety or if defaults change.
            logger.error(f"Platform codename is missing for campaign {campaign_id}. Finalizing as FAILED.")
            await finalize_campaign(campaign_id)
            return

        # Create simple message data from message_text
        message_content_data = {'text': campaign.message_text}

        # --- Dispatch tasks ---
        for i in range(0, total_recipients, batch_size):
            batch_chat_ids = chat_ids[i:i + batch_size]
            logger.info(f"Dispatching batch {i // batch_size + 1} for campaign {campaign_id} ({len(batch_chat_ids)} recipients).")
            from .tasks import send_broadcast_batch
            send_broadcast_batch.delay( # Direct call
                campaign_id=campaign.id,
                bot_codename=bot_codename,
                platform_codename=platform_codename, # Use the value from campaign.platform
                chat_ids=batch_chat_ids,
                message_content_data=message_content_data
            )

    except Exception as e:
        logger.exception(f"Error during campaign initiation or dispatch for {campaign_id}. Attempting to mark as FAILED.")
        try:
            # Use sync_to_async to update status to FAILED
            await sync_to_async(BroadcastCampaign.objects.filter(id=campaign_id).update)(
                 status=BroadcastCampaign.Status.FAILED,
                 completed_at=timezone.now()
            )
        except Exception as update_err:
            logger.error(f"Failed to mark campaign {campaign_id} as FAILED after initiation/dispatch error: {update_err}")
    # --- End Transaction Scope ---


@sync_to_async
def record_batch_results(campaign_id: int, successful: int, failed: int):
    """
    Atomically updates the statistics for a campaign based on results from a batch.
    Checks if the campaign is complete after this batch and triggers the finalization task.
    """
    logger.debug(f"Recording batch results for campaign {campaign_id}: success={successful}, failed={failed}")
    should_finalize = False
    try:
        with transaction.atomic():
            # Lock the campaign row for update
            try:
                campaign = BroadcastCampaign.objects.select_for_update().get(id=campaign_id)
            except BroadcastCampaign.DoesNotExist:
                logger.error(f"Cannot record batch results: Campaign {campaign_id} not found.")
                return

            # Only update stats if the campaign is still in SENDING state
            if campaign.status != BroadcastCampaign.Status.SENDING:
                logger.warning(f"Campaign {campaign_id} is not in SENDING state (current: {campaign.status}). Ignoring batch results.")
                return

            campaign.successful_sents += successful
            campaign.failed_sents += failed
            campaign.save(update_fields=['successful_sents', 'failed_sents', 'updated_at'])

            logger.debug(f"Campaign {campaign_id} stats updated: success={campaign.successful_sents}, failed={campaign.failed_sents}, total={campaign.total_recipients}")

            # Check if all recipients have been processed
            processed_count = campaign.successful_sents + campaign.failed_sents
            if campaign.total_recipients is not None and processed_count >= campaign.total_recipients:
                logger.info(f"All recipients processed for campaign {campaign_id}. Marking for finalization.")
                should_finalize = True # Mark to finalize *after* transaction
            else:
                logger.debug(f"Campaign {campaign_id} still in progress: {processed_count}/{campaign.total_recipients} processed.")

        # If finalization is needed, trigger the task *after* the transaction commits.
        if should_finalize:
             logger.info(f"Triggering finalization task for campaign {campaign_id}.")
             from .tasks import finalize_campaign_task
             finalize_campaign_task.delay(campaign_id) # Direct call

    except Exception as e:
        logger.exception(f"Error recording batch results for campaign {campaign_id}: {e}")


async def finalize_campaign(campaign_id: int):
    """
    Finalizes a broadcast campaign by setting its completed_at timestamp
    and determining the final status based on success/failure counts.
    """
    logger.info(f"Finalizing campaign {campaign_id}...")
    try:
        # Wrap the transaction logic in sync_to_async
        @sync_to_async
        def run_finalization_in_transaction():
            with transaction.atomic():
                try:
                    campaign = BroadcastCampaign.objects.select_for_update().get(id=campaign_id)
                except BroadcastCampaign.DoesNotExist:
                    logger.error(f"Cannot finalize: Campaign {campaign_id} not found.")
                    return False # Indicate failure

                # Status check logic (sync)
                if campaign.status not in [BroadcastCampaign.Status.SENDING]:
                    if campaign.status == BroadcastCampaign.Status.FAILED and campaign.completed_at is None:
                        logger.warning(f"Campaign {campaign_id} was already marked FAILED. Setting completed_at.")
                        campaign.completed_at = campaign.started_at or timezone.now()
                    elif campaign.status == BroadcastCampaign.Status.COMPLETED or campaign.completed_at is not None:
                        logger.info(f"Campaign {campaign_id} is already finalized. Skipping.")
                        return True # Indicate success (already done)
                    else:
                        logger.warning(f"Campaign {campaign_id} not in SENDING/FAILED state ({campaign.status}). Cannot finalize.")
                        return False # Indicate cannot finalize

                # Determine final status (sync)
                final_status = BroadcastCampaign.Status.COMPLETED
                if campaign.total_recipients is None or campaign.total_recipients == 0:
                    final_status = BroadcastCampaign.Status.COMPLETED
                elif campaign.failed_sents == campaign.total_recipients:
                    final_status = BroadcastCampaign.Status.FAILED
                elif campaign.failed_sents > 0:
                    final_status = BroadcastCampaign.Status.PARTIAL_FAILURE

                campaign.status = final_status
                campaign.completed_at = timezone.now()

                campaign.save(update_fields=['status', 'completed_at', 'updated_at'])
                logger.info(f"Campaign {campaign_id} finalized with status {final_status}.")
                return True # Indicate success

        # Execute the synchronous transaction block asynchronously
        success = await run_finalization_in_transaction()
        if not success:
             logger.warning(f"Finalization transaction did not complete successfully for campaign {campaign_id}.")

    except Exception as e:
        logger.exception(f"Error finalizing campaign {campaign_id}: {e}")
        # Consider if we need to retry or mark as failed here