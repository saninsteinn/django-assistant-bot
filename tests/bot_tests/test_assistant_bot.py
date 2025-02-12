import pytest
from unittest.mock import AsyncMock

from asgiref.sync import async_to_sync, sync_to_async

from assistant.ai.domain import AIResponse
from assistant.bot.assistant_bot import AssistantBot
from assistant.bot.domain import Update, User, SingleAnswer, BotPlatform
from assistant.bot.tasks import _answer_task
# Import necessary classes and functions
from assistant.bot.domain import Update, User, SingleAnswer, BotPlatform
from assistant.bot.models import Bot as BotModel, Instance, BotUser, Dialog, Message
from assistant.bot.services.dialog_service import create_user_message, have_existing_answers, get_gpt_messages
from django.contrib.auth.models import User as DjangoUser


@pytest.mark.django_db
def test_answer_task(mocker, dialog):

    # Test data setup
    platform_codename = 'telegram'
    # bot = Bot.objects.create(codename=bot_codename, platform=platform_codename)

    user = User(id='123', username='testuser', first_name='Test', last_name='User', language_code='en')
    update = Update(chat_id='12345', message_id=1, text='Hello', user=user)
    update_dict = update.to_dict()

    # Mock bot class
    class MockBot:
        def __init__(self, dialog, platform):
            self.dialog = dialog
            self.platform = platform

        async def handle_update(self, update):
            return SingleAnswer(text='Test response', no_store=False)

        async def on_answer_sent(self, answer):
            pass

        async def on_instance_created(self):
            pass

    mocker.patch('assistant.bot.tasks.get_bot_class', return_value=MockBot)

    # Mock platform
    mock_platform = AsyncMock(spec=BotPlatform)
    mocker.patch('assistant.bot.tasks.get_bot_platform', return_value=mock_platform)

    # Execute the task
    async_to_sync(_answer_task)(dialog.instance.bot.codename, dialog.id, platform_codename, update_dict)

    # Assertions
    mock_platform.post_answer.assert_called_once()
    called_args = mock_platform.post_answer.call_args
    assert called_args[0][0] == '12345'
    assert isinstance(called_args[0][1], SingleAnswer)
    assert called_args[0][1].text == 'Test response'


@pytest.mark.django_db
def test_handle_update(user_message, mocker):

    # Setup test data
    bot_codename = 'test_bot'
    platform_codename = 'telegram'

    # Create Update
    user = User(
        id='12345',
        username='testuser',
        first_name='Test',
        last_name='User',
        language_code='en'
    )
    update = Update(
        chat_id='12345',
        message_id=1,
        text='Hello',
        user=user
    )

    # Create a minimal BotPlatform implementation
    class TestPlatform(BotPlatform):
        async def get_update(self, request):
            pass  # Not needed for this test

        async def post_answer(self, chat_id: str, answer: SingleAnswer):
            # We can verify if this method is called as expected
            pass

        async def action_typing(self, chat_id):
            # We can leave this empty or print a message for debugging
            pass

    platform = TestPlatform()

    # Create AssistantBot instance
    bot_instance = AssistantBot(dialog=user_message.dialog, platform=platform)

    # Mock only the AI response by patching ChatCompletion.generate_answer
    with mocker.patch('assistant.bot.chat_completion.ChatCompletion.generate_answer', return_value=AIResponse('Test AI response')):
        # Run handle_update
        answer = async_to_sync(bot_instance.handle_update)(update)

    # Assertions
    assert isinstance(answer, SingleAnswer)
    assert answer.text == 'Test AI response'


