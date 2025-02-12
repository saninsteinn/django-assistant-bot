import logging
from abc import ABC, abstractmethod
from datetime import timedelta

from asgiref.sync import sync_to_async
from django.shortcuts import get_object_or_404
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from assistant.bot.adrf import AsyncMixin
from assistant.bot.models import Instance, Bot, BotUser
from assistant.bot.assistant_bot import AssistantBot
from assistant.bot.domain import UnknownUpdate, User, Update
from assistant.bot.services.dialog_service import create_user_message, get_dialog

from assistant.bot.tasks import answer_task
from assistant.bot.utils import get_bot_platform

logger = logging.getLogger(__name__)


class BaseAssistantBotView(AsyncMixin, APIView, ABC):

    @abstractmethod
    def get_bot_codename(self, request: Request) -> str:
        pass

    @abstractmethod
    def get_platform_codename(self, request: Request) -> str:
        pass

    async def post(self, request, **kwargs):
        bot_codename = self.get_bot_codename(request)
        platform_codename = self.get_platform_codename(request)

        platform = await sync_to_async(get_bot_platform)(bot_codename, platform_codename)

        try:
            update = await platform.get_update(request)
        except UnknownUpdate as e:
            logger.exception(e)
            return Response(status=200)

        try:
            dialog = await self._get_dialog(bot_codename, platform_codename, update)
        except Exception as e:
            logger.exception(e)
            return Response(status=200)
        answer_task.delay(bot_codename, dialog.id, platform_codename, update.to_dict())
        return Response(status=200)

    async def _get_dialog(self, bot_codename, platform_codename, update):
        instance, instance_created = await sync_to_async(self._get_instance)(bot_codename, platform_codename, update)
        dialog = await sync_to_async(get_dialog)(instance, timedelta(days=1))
        user_message = await sync_to_async(create_user_message)(dialog, update.message_id, update.text, update.photo)
        return dialog

    def _get_instance(self, codename: str, platform_codename: str, update: Update):
        chat_id, user = update.chat_id, update.user
        bot = get_object_or_404(Bot, codename=codename)

        language = user.language_code if user else None
        username = self._get_username(user) if user else None

        bot_user, _ = BotUser.objects.get_or_create(
            user_id=chat_id,
            platform=platform_codename,
            defaults={
                'username': username,
                'language': language,
            }
        )
        if bot_user.language != language:
            bot_user.language = language
            bot_user.save(update_fields=['language'])
        if bot_user.username != username:
            bot_user.username = username
            bot_user.save(update_fields=['username'])

        instance, created = Instance.objects.get_or_create(
            user_id=bot_user.id,
            bot_id=bot.id,
        )

        instance = Instance.objects.prefetch_related('bot', 'user').get(id=instance.id)
        return instance, created

    def _get_username(self, user: User):
        if user.username:
            return '@' + user.username
        username = ''
        if user.first_name:
            username = user.first_name
        if user.last_name:
            username = f'{username} {user.last_name}'
        if username:
            return username


class TelegramAssistantBotView(BaseAssistantBotView):

    permission_classes = [AllowAny]

    def get_bot_codename(self, request: Request) -> str:
        return self.kwargs.get('codename', '')

    def get_platform_codename(self, request: Request) -> str:
        return 'telegram'
