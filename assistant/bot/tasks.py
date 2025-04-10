import logging
from datetime import timedelta
from typing import Dict, List, Any, Union

from asgiref.sync import sync_to_async, async_to_sync
from celery import shared_task
from rest_framework.generics import get_object_or_404

from assistant.assistant.queue import CeleryQueues
from assistant.bot.domain import Update, MultiPartAnswer, BotPlatform, SingleAnswer, User, Answer, Button, answer_from_dict
from assistant.bot.exceptions import UserUnavailableError
from assistant.bot.models import Instance, Bot, BotUser, Dialog, Message
from assistant.bot.resource_manager import ResourceManager
from assistant.bot.services.dialog_service import get_dialog
from assistant.bot.services.instance_service import InstanceLock, InstanceLockAsync
from assistant.bot.utils import get_bot_platform, get_bot_class

logger = logging.getLogger(__name__)


@shared_task(queue=CeleryQueues.QUERY.value)
def answer_task(*args, **kwargs):
    logger.info('Answer Task started')
    return async_to_sync(_answer_task)(*args, **kwargs)


async def _answer_task(bot_codename: str, dialog_id: int, platform_codename: str, update: Dict):
    update: Update = Update.from_dict(update)

    platform = await sync_to_async(get_bot_platform)(bot_codename, platform_codename)
    dialog = await sync_to_async(
        lambda: Dialog.objects.select_related('instance', 'instance__bot', 'instance__user').get(id=dialog_id)
    )()

    bot_cls = get_bot_class(bot_codename)
    bot = bot_cls(
        dialog=dialog,
        platform=platform,
    )

    async with InstanceLockAsync(dialog.instance):
        message_ids = await sync_to_async(
            lambda: list(Message.objects.filter(dialog__instance_id=dialog.instance.id)[:2])
        )()
        if len(message_ids) <= 1:
            # instance created
            await bot.on_instance_created()
        answer = await bot.handle_update(update)

    if answer:
        try:
            await _post_answer(platform, update.chat_id, answer)
            await bot.on_answer_sent(answer)
        except UserUnavailableError as e:
            logger.warning(f'User {e.chat_id} is unavailable. Marking instance {dialog.instance.id}.')
            dialog.instance.is_unavailable = True
            await sync_to_async(dialog.instance.save)(update_fields=['is_unavailable'])
        except Exception as e:
            logger.error(f'Error while sending answer: {e}')
            # try:
            #     # Try sending an error message back
            #     resource_manager = ResourceManager(
            #         codename=bot_codename,
            #         language='en', # Use default language for error message
            #     )
            #     error_answer = SingleAnswer(resource_manager.get_phrase('`An error occurred while sending the response\.`'), no_store=True)
            #     await _post_answer(platform, update.chat_id, error_answer)
            # except Exception as inner_e:
            #     logger.error(f'Failed to send error message back to {update.chat_id}: {inner_e}')


async def _post_answer(platform: BotPlatform, chat_id: str, answer):
    if isinstance(answer, MultiPartAnswer):
        answers = answer.parts
    else:
        answers = [answer]

    for answer_part in answers:
        await platform.post_answer(chat_id, answer_part)


@shared_task(queue=CeleryQueues.QUERY.value)
def send_answer_task(*args, **kwargs):
    """Sends a single pre-defined answer to a specific chat ID."""
    logger.info('Send Answer Task started')
    return async_to_sync(_send_answer_task)(*args, **kwargs)


async def _send_answer_task(bot_codename: str, platform_codename: str, chat_id: str, answer_data: Dict):
    """
    Worker coroutine for sending a single pre-defined Answer.
    Checks if the user is marked as unavailable before sending.
    """
    instance = None # Initialize instance to None
    try:
        # Fetch the instance associated with the chat_id to check the status
        bot_user = await sync_to_async(BotUser.objects.get)(user_id=chat_id, platform=platform_codename)
        bot_model = await sync_to_async(Bot.objects.get)(codename=bot_codename)
        instance = await sync_to_async(Instance.objects.get)(bot=bot_model, user=bot_user)

        if instance.is_unavailable:
            logger.info(f"Skipping sending message to unavailable user {chat_id} for instance {instance.id}")
            return
    except (BotUser.DoesNotExist, Bot.DoesNotExist, Instance.DoesNotExist) as e:
        logger.warning(f"Could not find instance for chat_id {chat_id}, platform {platform_codename}, bot {bot_codename}. Cannot check unavailable status. Error: {e}")
        # Proceeding, as the status is unknown

    platform = await sync_to_async(get_bot_platform)(bot_codename, platform_codename)

    try:
        answer = answer_from_dict(answer_data)
    except Exception as e:
        logger.error(f"Error deserializing answer in _send_answer_task: {e}\nData: {answer_data}")
        return

    try:
        await _post_answer(platform, chat_id, answer)
        logger.info(f"Successfully sent answer via task to chat_id {chat_id}")
    except UserUnavailableError as e:
        logger.warning(f'User {e.chat_id} became unavailable during send_answer_task.')
        if instance: # Only update if instance was found earlier
            instance.is_unavailable = True
            await sync_to_async(instance.save)(update_fields=['is_unavailable'])
            logger.info(f"Marked instance {instance.id} as unavailable.")
        else:
             logger.warning(f"Could not mark instance as unavailable for chat_id {chat_id} because instance was not found.")
    except Exception as e:
        logger.error(f'Error while sending answer via task to chat_id {chat_id}: {e}')

