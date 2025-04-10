import asyncio
import logging
import json
import os
import readline
import sys
import uuid
import time
import signal
from datetime import timedelta
from threading import Thread

from asgiref.sync import sync_to_async
from django.core.management import BaseCommand
from django.db.models import Max
from django.utils import autoreload

from assistant.bot.management.commands.utils import get_instance
from assistant.bot.models import Message
from assistant.bot.domain import Update, User, SingleAnswer, MultiPartAnswer, BotPlatform
from assistant.bot.utils import get_bot_class
from assistant.bot.services.dialog_service import get_dialog, create_user_message
from assistant.bot.services.instance_service import InstanceLockAsync
from assistant.bot.resource_manager import ResourceManager

logger = logging.getLogger(__name__)

# Silence all DEBUG logs in console
for logger_name in logging.root.manager.loggerDict:
    logging.getLogger(logger_name).setLevel(logging.WARNING)
logging.getLogger().setLevel(logging.WARNING)


HISTORY_FILE_NAME = ".chat_history.jsonl"


class Command(BaseCommand):
    help = 'Interactive interaction with bot through console for debugging'

    def add_arguments(self, parser):
        parser.add_argument('bot_codename', type=str, help='Bot codename for interaction')

    def handle(self, *args, **options):
        self.bot_codename = options['bot_codename']
        logger.info("Starting chat with auto-reload enabled")

        # Use Django's built-in autoreload functionality
        autoreload.run_with_reloader(self._run_chat_main)

    def _run_chat_main(self):
        """Main entry point that will be run by the reloader."""
        # The bot_codename is already set in handle() before autoreloading
        self._run_chat()

    def _run_chat(self):
        platform_codename = 'console'
        chat_id = str(uuid.uuid4())

        # Load history from file
        load_chat_history()

        # Create a new event loop instead of getting the default one
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        print(f"Interactive chat with bot '{self.bot_codename}'")
        while True:
            try:
                user_message = input("\nYou: ")
                if user_message.lower() in ('exit', 'quit', 'exit'):
                    print("Ending interactive chat.")
                    break

                readline.add_history(user_message)

                # Log the user message
                log_chat_history("user", user_message)

                # Process message asynchronously
                loop.run_until_complete(process_message(self.bot_codename, user_message, chat_id, platform_codename))

            except (KeyboardInterrupt, EOFError):
                print("\nEnding interactive chat.")
                break

        # Ensure we properly close the loop
        loop.close()
        # Send SIGTERM to self to exit completely
        os.kill(os.getpid(), signal.SIGTERM)


class ConsolePlatform(BotPlatform):
    """Custom platform for interaction through console."""

    @property
    def codename(self) -> str:
        return 'console'

    def __init__(self, bot_codename: str):
        self.bot_codename = bot_codename

    async def post_answer(self, chat_id: str, answer):
        if isinstance(answer, MultiPartAnswer):
            for part in answer.parts:
                self._print_single_answer(part)
        elif isinstance(answer, SingleAnswer):
            self._print_single_answer(answer)
        else:
            print(f"Bot sent unknown response type: {answer}")

    def _print_single_answer(self, answer: SingleAnswer):
        print(f"Bot: {answer.text}")
        # Log the bot answer
        log_kwargs = {}
        if answer.buttons:
            print('')
            buttons_text = '\n'.join(
                ' '.join(
                    f'[{button.text}]({button.callback_data or button.url})' for button in row
                )
                for row in answer.buttons
            )
            print(buttons_text)
            log_kwargs['buttons'] = [
                [
                    {"text": button.text, "callback_data": button.callback_data, "url": button.url}
                    for button in row
                ]
                for row in answer.buttons
            ]
        if answer.reply_keyboard:
            print('')
            keyboard_text = '\n'.join(
                ' '.join(
                    f'{{{button}}}'
                    for button in row
                )
                for row in answer.reply_keyboard
            )
            print(keyboard_text)
            log_kwargs['reply_keyboard'] = [
                [button for button in row]
                for row in answer.reply_keyboard
            ]
        log_chat_history("assistant", answer.text, **log_kwargs)

    async def get_update(self, request):
        pass  # Not used in this context

    async def action_typing(self, chat_id):
        pass


async def process_message(bot_codename: str, user_message: str, chat_id: str, platform_codename: str = 'console'):

    # Create Update object
    user = User(
        id=chat_id,
        username='tester',
        first_name='Test',
        last_name='User',
        language_code='ru',
    )

    # Use custom platform
    platform = ConsolePlatform(bot_codename=bot_codename)

    # Get or create bot instance
    instance = await sync_to_async(get_instance)(bot_codename, platform_codename, chat_id, user)

    # Get dialog
    dialog = await sync_to_async(get_dialog)(instance, timedelta(days=1))

    # Create bot instance
    bot_cls = get_bot_class(bot_codename)
    bot = bot_cls(
        dialog=dialog,
        platform=platform,
    )

    max_message_id = await sync_to_async(
        lambda: Message.objects.filter(dialog=dialog).aggregate(Max('id'))['id__max'] or 0
    )()

    update = Update(
        chat_id=chat_id,
        message_id=max_message_id + 1,
        user=user,
        text=user_message,
    )

    # create message
    user_message = await sync_to_async(create_user_message)(dialog, update.message_id, update.text, update.photo)

    async with InstanceLockAsync(instance):
        try:
            answer = await bot.handle_update(update)
        except Exception as e:
            logger.exception(f'Error while handling update: {e}')
            resource_manager = ResourceManager(
                codename=bot_codename,
                language='ru',
            )
            answer = SingleAnswer(resource_manager.get_phrase('An error occurred while processing your message.'), no_store=True)

    if answer:
        try:
            await platform.post_answer(chat_id, answer)
        except Exception as e:
            logger.exception(f'Error while sending answer: {e}')
            resource_manager = ResourceManager(
                codename=bot_codename,
                language='ru',
            )
            error_answer = SingleAnswer(resource_manager.get_phrase('An error occurred while sending the response.'), no_store=True)
            await platform.post_answer(chat_id, error_answer)
        await bot.on_answer_sent(answer)


def log_chat_history(role: str, text: str, **kwargs):
    """Log chat messages to a JSONL file."""
    try:
        with open(HISTORY_FILE_NAME, "a", encoding="utf-8") as f:
            json_record = json.dumps({"role": role, "text": text, **kwargs}, ensure_ascii=False)
            f.write(json_record + "\n")
    except Exception as e:
        logger.error(f"Failed to write chat history: {e}")


# Function to load chat history from file into readline
def load_chat_history():
    if os.path.exists(HISTORY_FILE_NAME):
        try:
            with open(HISTORY_FILE_NAME, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        record = json.loads(line.strip())
                        if record.get("role") == "user":  # Add only user messages to history
                            readline.add_history(record.get("text", ""))
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            logger.error(f"Failed to load chat history: {e}")
