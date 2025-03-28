import asyncio
import logging
from typing import Optional
from datetime import timedelta

from asgiref.sync import sync_to_async
from django.core.management import BaseCommand
from telegram.ext import Application, MessageHandler, CallbackQueryHandler, filters

from assistant.bot.management.commands.utils import get_instance
from assistant.bot.domain import Update
from assistant.bot.utils import get_bot_platform
from assistant.bot.services.dialog_service import get_dialog, create_user_message
from assistant.bot.tasks import answer_task


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Run bot in Telegram polling mode for interactive interaction'

    def add_arguments(self, parser):
        parser.add_argument('bot_codename', type=str, help='Bot codename to run')
        parser.add_argument('--sync', action='store_true', help='Run in synchronous mode without Celery')

    def handle(self, *args, **options):
        bot_codename = options['bot_codename']
        platform_codename = 'telegram'
        self.sync_mode = options['sync']

        mode_str = "synchronous" if self.sync_mode else "asynchronous mode via Celery"
        logger.info(f"Starting bot {bot_codename} in {mode_str}")

        # Initialize Telegram platform
        try:
            platform = get_bot_platform(bot_codename, platform_codename)
            logger.info(f"Telegram platform initialized for bot {bot_codename}")
        except Exception as e:
            logger.error(f"Platform initialization error: {e}")
            return

        # Create and configure Application
        application = Application.builder().token(platform.bot.token).build()

        # Register handlers
        application.add_handler(MessageHandler(filters.ALL, self._create_handler(bot_codename)))
        application.add_handler(CallbackQueryHandler(self._create_handler(bot_codename)))
        application.add_error_handler(self._error_handler)

        # Start polling
        try:
            self.stdout.write(f"Bot '{bot_codename}' started in Telegram polling mode")
            asyncio.run(application.run_polling(allowed_updates=["message", "callback_query"]))
        except KeyboardInterrupt:
            self.stdout.write("\nBot stopped by user")
        except Exception as e:
            logger.error(f"Error starting polling: {e}", exc_info=True)

    def _create_handler(self, bot_codename: str):
        """Creates a universal handler for all update types."""
        async def handler(update, context):
            telegram_update = update
            chat_id = self._get_chat_id(telegram_update)
            user_id = self._get_user_id(telegram_update)

            logger.info(f"Received update: chat_id={chat_id}, user_id={user_id}, "
                       f"type={'message' if telegram_update.message else 'callback'}")

            try:
                # Convert Telegram update to our Update
                bot_update = await self._convert_telegram_update(telegram_update, bot_codename)
                if not bot_update:
                    logger.warning(f"Failed to convert update: chat_id={chat_id}")
                    return

                # Process update
                await self._process_update(bot_codename, bot_update)
            except Exception as e:
                logger.error(f"Error processing update: chat_id={chat_id}, user_id={user_id}, error={e}",
                            exc_info=True)

        return handler

    async def _error_handler(self, update, context):
        """Error handler from telegram.ext."""
        logger.error(f"Error in telegram.ext: {context.error}", exc_info=True)

    async def _convert_telegram_update(self, telegram_update, bot_codename: str) -> Optional[Update]:
        """Converts Telegram update to Update object."""
        platform_codename = 'telegram'
        platform = await sync_to_async(get_bot_platform)(bot_codename, platform_codename)

        try:
            if not telegram_update.message and not telegram_update.callback_query:
                logger.warning(f"Unknown update type: {telegram_update}")
                return None

            update = await platform.convert_telegram_update(telegram_update)
            return update

        except Exception as e:
            logger.error(f"Error converting update: {e}", exc_info=True)
            return None

    async def _process_update(self, bot_codename: str, update: Update):
        """Processes update and sends task to Celery or processes synchronously."""
        platform_codename = 'telegram'
        platform = await sync_to_async(get_bot_platform)(bot_codename, platform_codename)

        try:
            # Get bot instance and dialog
            instance = await sync_to_async(get_instance)(
                bot_codename, platform_codename, update.chat_id, update.user
            )
            dialog = await sync_to_async(get_dialog)(instance, timedelta(days=1))

            # Create user message
            user_message = await sync_to_async(create_user_message)(
                dialog, update.message_id, update.text, update.photo
            )
            logger.info(f"Message saved: chat_id={update.chat_id}, text={update.text[:50]}...")

            # Notify typing
            await platform.action_typing(update.chat_id)

            if self.sync_mode:
                # Synchronous processing
                await sync_to_async(answer_task)(
                    bot_codename, dialog.id, platform_codename, update.to_dict()
                )
                logger.debug(f"Message processed synchronously: chat_id={update.chat_id}")
            else:
                # Send task to Celery
                from celery import current_app
                current_app.send_task(
                    'assistant.bot.tasks.answer_task',
                    args=[bot_codename, dialog.id, platform_codename, update.to_dict()],
                    queue='query'
                )
                logger.debug(f"Task sent to Celery: chat_id={update.chat_id}")

        except Exception as e:
            logger.error(f"Error processing update: chat_id={update.chat_id}, error={e}", exc_info=True)

    @staticmethod
    def _get_chat_id(telegram_update) -> str:
        """Extracts chat_id from update."""
        if telegram_update.message:
            return str(telegram_update.message.chat_id)
        elif telegram_update.callback_query:
            return str(telegram_update.callback_query.message.chat_id)
        return "unknown"

    @staticmethod
    def _get_user_id(telegram_update) -> str:
        """Extracts user_id from update."""
        if telegram_update.message and telegram_update.message.from_user:
            return str(telegram_update.message.from_user.id)
        elif telegram_update.callback_query and telegram_update.callback_query.from_user:
            return str(telegram_update.callback_query.from_user.id)
        return "unknown"
