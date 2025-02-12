import logging
from datetime import timedelta
from typing import Dict

from asgiref.sync import sync_to_async, async_to_sync
from celery import shared_task
from rest_framework.generics import get_object_or_404

from assistant.assistant.queue import CeleryQueues
from assistant.bot.domain import Update, MultiPartAnswer, BotPlatform, SingleAnswer, User
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
        except Exception as e:
            logger.error(f'Error while sending answer: {e}')
            resource_manager = ResourceManager(
                codename=bot_codename,
                language='en',
            )
            answer = SingleAnswer(resource_manager.get_phrase('`An error occurred while sending the response\\.`'), no_store=True)
            await _post_answer(platform, update.chat_id, answer)
        await bot.on_answer_sent(answer)


async def _post_answer(platform: BotPlatform, chat_id: str, answer):
    if isinstance(answer, MultiPartAnswer):
        answers = answer.parts
    else:
        answers = [answer]

    for answer in answers:
        await platform.post_answer(chat_id, answer)

