import asyncio
import json
import logging
import random
import re
import time
from typing import Optional, Dict, Set, Callable, List

from asgiref.sync import sync_to_async
from django.db.models import Count
from django.conf import settings

from assistant.ai.dialog import AIDialog
from assistant.ai.domain import AIResponse, Message as GPTMessage
from assistant.ai.services.ai_service import extract_tagged_text, get_ai_provider
from assistant.bot.domain import Bot, Update, Answer, MultiPartAnswer, NoMessageFound, SingleAnswer, \
    Button, User, BotPlatform, Photo

from assistant.bot.models import Instance, Dialog, Message, BotUser, Bot as BotModel
from assistant.bot.platforms.telegram.format import TelegramMarkdownV2FormattedText
from assistant.bot.resource_manager import ResourceManager
from assistant.bot.services.dialog_service import get_dialog, create_bot_message, create_user_message, have_existing_answers, \
    get_gpt_messages
from assistant.bot.utils import truncate_text


logger = logging.getLogger(__name__)


class AssistantBot(Bot):

    platform: BotPlatform
    instance: Instance

    instance: Instance
    dialog: Dialog
    messages: List[GPTMessage]
    debug_info: Dict
    bot: BotModel
    bot_user: BotUser
    resource_manager: ResourceManager
    allowed_commands: Optional[List[str]] = None  # Allowed command prefixes

    DEFAULT_LANGUAGE = 'ru'
    SERVICE_TAG_REGEXP = re.compile(r'#service', re.I)

    _command_handlers: List[tuple] = []

    def __init__(self, dialog: Dialog, platform: BotPlatform):
        self.dialog = dialog
        self.instance = dialog.instance
        self.bot = self.instance.bot
        self.bot_user = self.instance.user
        self.platform = platform

    @classmethod
    def command(cls, pattern: str):
        """
        Decorator for registering a command.

        :param pattern: Regular expression string for the command.
        """
        def decorator(func: Callable):
            cls._command_handlers.append((re.compile(pattern), func))
            return func
        return decorator

    async def handle_update(self, update: Update) -> Optional[Answer]:

        # Unmark instance if the user writes after being marked as unavailable
        if self.instance.is_unavailable:
            logger.info(f"User {update.user.id} sent a message. Unmarking instance {self.instance.id} as available.")
            self.instance.is_unavailable = False
            await sync_to_async(self.instance.save)(update_fields=['is_unavailable'])

        self.resource_manager = ResourceManager(
            codename=self.bot.codename,
            language=self.bot_user.language or self.DEFAULT_LANGUAGE
        )

        if self.bot.is_whitelist_enabled:
            whitelist = self.whitelist()
            if not (
                update.user.id in whitelist or
                update.user.username in whitelist
            ):
                return SingleAnswer(
                    "`Authorization required.`",
                    no_store=True,
                )

        logger.info('Instance %s text: %s', self.instance, update.text)

        answer_task = asyncio.create_task(self._get_answer(self.dialog, update))
        typing_task = asyncio.create_task(self.delayed_typing(update.chat_id, answer_task))

        await answer_task
        typing_task.cancel()
        answer = answer_task.result()

        if answer is None:
            return None

        if answer.state:
            await self.update_state(answer.state)

        return answer

    def whitelist(self) -> Set[str]:
        return {
            user_id.strip().strip('@')
            for user_id in self.bot.telegram_whitelist.split('\n') if user_id.strip()
        }

    async def on_instance_created(self):
        pass

    async def on_answer_sent(self, answer: Answer):
        if not answer.no_store:
            if isinstance(answer, MultiPartAnswer):
                answers = answer.parts
            else:
                answers = [answer]
            for answer in answers:
                if answer.raw_text:
                    # To safe tokens amount and because command messages have native formatting
                    await sync_to_async(create_bot_message)(self.dialog, answer)

    async def delayed_typing(self, chat_id, answer_task):
        await asyncio.sleep(1)
        while not answer_task.done():
            await self.platform.action_typing(chat_id)
            await asyncio.sleep(random.choice([8, 9]))

    async def _get_answer(self, dialog: Dialog, update: Update) -> Optional[Answer]:
        message_id = update.message_id
        text = update.text
        photo = update.photo
        phone_number = update.phone_number

        if not text and not photo and not phone_number:
            return SingleAnswer("`Sorry, only text messages, photos, or contact shares are supported.`", no_store=True)

        if self.instance.state.get('mode') == 'image_creation':
            if text and text.startswith('/'):
                await self.update_state({
                    'mode': 'text'
                })
            else:
                text = f'/image {text}'

        self.messages = await sync_to_async(self._get_messages)()
        self.debug_info = {}
        self.debug_info['state'] = dict(self.instance.state)
        self.debug_info['state'].pop('debug_info', None)
        handle_start_ts = time.time()

        if text and text.startswith('/'):
            answer = await self.handle_command(dialog, message_id, text)
        elif phone_number:
            answer = await self.handle_phone_number(dialog, message_id, phone_number)
        else:
            answer = await self.handle_message(dialog, message_id, text, photo)

        self.debug_info['total'] = {
            'took': time.time() - handle_start_ts
        }
        await self.update_state({
            'debug_info': json.dumps(self.debug_info, ensure_ascii=False, indent=2)  # dump now to keep key order
        })
        logger.debug('Debug info: %s', self.debug_info)
        return answer

    def _get_messages(self):
        system_text = self._get_system_text()
        messages_from_db = get_gpt_messages(self.dialog, system_text)

        messages = []
        for m in messages_from_db:
            # Filter duplicated messages
            if m['role'] == 'user' and m['content'] and m['content'].startswith('/'):
                continue
            if not messages or messages[-1]['role'] != m['role']:
                messages.append(m)
            else:
                messages[-1] = self._merge_messages(messages[-1], m)
        return messages

    async def command_continue(self, dialog: Dialog, message_id: int) -> Optional[SingleAnswer]:
        return await self.handle_message(dialog, message_id, "/continue")

    async def handle_message(self, dialog: Dialog, message_id: int, text: str = None, photo: Photo = None) -> Optional[SingleAnswer]:
        user_message = await sync_to_async(
            lambda: Message.objects.filter(dialog_id=dialog.id, role__name='user').order_by('timestamp').last()
        )()
        if not user_message:
            return

        if await self.already_answered(user_message):
            return

        try:
            async def do_interrupt():
                return await self.already_answered(user_message)

            answer = await self.get_answer_to_messages(self.messages, self.debug_info, do_interrupt)

        except Exception as e:
            logger.exception('Failed to handle dialog')
            return None
            # return SingleAnswer(
            #     self.resource_manager.get_phrase('`An error occurred while generating the response.`'), no_store=True)

        if await self.has_new_messages(message_id):
            logger.warning(f"User sent new messages during processing.")
            return None

        if answer is not None and await self.already_answered(user_message):
            logger.warning(f'Wasted request. User message {message_id} already has answers')
            return None

        return answer

    async def handle_phone_number(self, dialog: Dialog, message_id: int, phone_number: str) -> Optional[SingleAnswer]:
        raise NotImplementedError('Phone number handling is not implemented yet')

    def _merge_messages(self, *messages: GPTMessage) -> GPTMessage:
        return GPTMessage(
            role=messages[0]['role'],
            content='\n'.join(m['content'] for m in messages if m['content'])
        )

    async def has_new_messages(self, message_id: int) -> bool:
        return await sync_to_async(
            self.dialog.messages.filter(message_id__gt=message_id).exists
        )()

    async def already_answered(self, user_message: Message) -> bool:
        answered = await (sync_to_async(have_existing_answers)(user_message))
        logger.debug('User message %s already answered: %s', user_message.message_id, answered)
        return answered

    async def get_answer_to_messages(self, messages, debug_info, do_interrupt) -> Answer:
        from assistant.bot.chat_completion import ChatCompletion
        chat_completion = ChatCompletion(
            bot=self.bot,
            fast_ai_model=self._get_fast_ai_model(),
            strong_ai_model=self._get_strong_ai_model(),
            resource_manager=self.resource_manager,
        )
        ai_answer = await chat_completion.generate_answer(
            messages, debug_info=debug_info, do_interrupt=do_interrupt
        )
        answer = self._ai_response_to_answer(ai_answer)
        return answer

    def _extract_thinking_tag(self, text: str) -> Optional[str]:
        # Extract content between <think> and </think>
        match = re.search(r'<think>(.*?)</think>', text, flags=re.DOTALL)
        return match.group(1).strip() if match else None

    def _clean_thinking(self, text: str):
        return re.sub(r'.*?</think>', '', text, flags=re.DOTALL)

    def _ai_response_to_answer(self, ai_response: AIResponse) -> Optional[Answer]:
        original_text = ai_response.result

        # Extract analytical part
        thinking = self._extract_thinking_tag(original_text)

        # Remove all thinking tags from text
        cleaned_text = self._clean_thinking(original_text)

        # Process main text (existing logic)
        if text_tag := self._extract_text_tag(cleaned_text):
            cleaned_text = text_tag

        cleaned_text = cleaned_text.strip() if cleaned_text else None

        if not cleaned_text:
            return None

        return SingleAnswer(
            text=cleaned_text,
            thinking=thinking,
            raw_text=original_text,
            usage=[
                ai_response.usage
            ] if ai_response.usage else None,
            buttons=[
                [Button(self.resource_manager.get_phrase(f'Continue'), callback_data='/continue')],
            ] if ai_response.length_limited else None,
        )

    def _extract_text_tag(self, text: str) -> Optional[str]:
        tagged_text = extract_tagged_text(text)
        logger.debug('Tagged text: %s', tagged_text)
        if 'text' in tagged_text:
            return tagged_text['text']

    @property
    def vision_enabled(self) -> bool:
        return False

    @property
    def _fast_ai(self) -> AIDialog:
        return AIDialog(self._get_fast_ai_model())

    @property
    def _strong_ai(self) -> AIDialog:
        return AIDialog(self._get_strong_ai_model())

    def _get_fast_ai_model(self):
        return getattr(settings, 'DIALOG_FAST_AI_MODEL', settings.DEFAULT_AI_MODEL)

    def _get_strong_ai_model(self):
        return self.instance.state.get(
            'model', getattr(settings, 'DIALOG_STRONG_AI_MODEL', settings.DEFAULT_AI_MODEL)
        )

    async def handle_command(self, dialog: Dialog, message_id: int, text) -> Optional[SingleAnswer]:
        # Check if the command is allowed
        if self.allowed_commands is not None:
            is_allowed = False
            for prefix in self.allowed_commands:
                if text.startswith(prefix):
                    is_allowed = True
                    break
            if not is_allowed:
                logger.warning(f"Command '{text}' is not allowed for bot {self.bot.codename}")
                return None

        try:
            if text.startswith('/start'):
                return await self.command_start(text)
            elif text == '/help':
                return await self.command_help()
            elif text == '/continue':
                return await self.command_continue(dialog, message_id)
            elif text == '/test_message':
                return SingleAnswer(self.resource_manager.get_message(f'TestMessage.txt'), no_store=True)
            elif text == '/new':
                return await (sync_to_async(self.command_new_dialog))()
            elif text.startswith('/model '):
                return await self.command_select_model(text)
            elif text == '/model':
                return await(sync_to_async(self.command_show_model))()
            elif text == '/models':
                return await (sync_to_async(self.command_show_models))()
            elif text.startswith('/debug'):
                return await (sync_to_async(self.command_debug))()
            elif text.startswith('/doc ') or text.startswith('/document '):
                return await (sync_to_async(self.command_show_document))(text)
            elif text.startswith('/wiki '):
                return await (sync_to_async(self.command_show_wiki))(text)
            else:
                for pattern, handler in self._command_handlers:
                    match = pattern.match(text)
                    if match:
                        # Determine if the handler is asynchronous
                        if asyncio.iscoroutinefunction(handler):
                            return await handler(self, match, message_id)
                        else:
                            return await sync_to_async(handler)(self, match, message_id)

            return SingleAnswer("`Unknown command.`", no_store=True)
        except Exception as e:
            logger.exception('Failed to handle command')
            # return SingleAnswer(
            #     self.resource_manager.get_phrase('`An error occurred while generating the response.`'), no_store=True
            # )


    async def command_start(self, text) -> Optional[Answer]:
        answer = await(sync_to_async(self.command_new_dialog))()
        try:
            answer = SingleAnswer(self.bot.start_text, no_store=True)
        except NoMessageFound:
            try:
                answer = SingleAnswer(self.bot.help_text, no_store=True)
            except NoMessageFound:
                pass
        return answer

    def command_new_dialog(self) -> SingleAnswer:
        Dialog.objects.filter(instance=self.instance, is_completed=False).update(is_completed=True)
        return SingleAnswer("`New dialog started.`", no_store=True)

    def command_show_dialogs(self):
        dialogs = Dialog.objects.annotate(messages_count=Count('messages')).filter(messages_count__gt=0).order_by(
            '-id')[:10]
        dialogs = sorted(dialogs, key=lambda dialog: dialog.id)
        if dialogs:
            buttons = [
                [Button(truncate_text(dialog._messages.first().text),
                        callback_data=f'/dialog {dialog.id}')]
                for i, dialog in enumerate(dialogs)
            ]
            return SingleAnswer("`There are your last dialogs:`", buttons=buttons, no_store=True)
        else:
            return SingleAnswer("`You don't have any dialogs yet.`", no_store=True)

    async def command_select_model(self, text):
        model_id = text.split()[1].strip()
        await self.update_state({
            'model': model_id
        })
        return SingleAnswer(
            f"`Model` *{TelegramMarkdownV2FormattedText(model_id)}* `selected.`",
            no_store=True,
        )

    def command_show_model(self):
        model = self._get_strong_ai_model()
        return SingleAnswer(f"*{TelegramMarkdownV2FormattedText(model)}*", no_store=True)

    def command_show_models(self):
        # models = openai.Model.list()['data']
        # models = [m for m in models if 'gpt-' in m['id']]
        models = [
            {'id': i}
            for i in [
                "llama3.1:8b",
                "llama3.1:70b",
            ]
        ]
        # models.sort(key=lambda model: model['id'])
        buttons = [
            [Button(truncate_text(model["id"]), callback_data=f'/model {model["id"]}')]
            for model in models
        ]
        logger.info("Keyboard: %s", buttons)
        current_model = self._get_strong_ai_model()
        return SingleAnswer(
            (
                f"`Current AI model:` {current_model}\n"
                "`You can change the model to:`"
            ), buttons=buttons, no_store=True
        )

    def command_debug(self) -> SingleAnswer:
        return SingleAnswer(
            text=(
                f"```json\n"
                f"{self.instance.state.get('debug_info', '{}')}\n"
                f"```\n"
            ),
            no_store=True,
            debug_info=self.instance.state.get('debug_info', {})
        )

    def command_show_document(self, text):
        from assistant.storage.models import Document
        doc_id = text.split()[1].strip()
        try:
            doc = Document.objects.filter(wiki__bot=self.bot).select_related('wiki').get(id=doc_id)
        except Document.DoesNotExist:
            return SingleAnswer("`Document not found.`", no_store=True)

        return SingleAnswer(
            text=(
                f"*`ID:`* {doc.id}\n"
                f"*`Wiki ID:`* {doc.wiki_id}\n"
                f"*`Wiki Path:`* {TelegramMarkdownV2FormattedText(doc.wiki.path)}\n"
                f"*`Name:`* {TelegramMarkdownV2FormattedText(doc.name)}\n"
                f"*`Content:`*\n"
                f"{TelegramMarkdownV2FormattedText(doc.content)}"
            ),
            no_store=True,
        )

    def command_show_wiki(self, text):
        from assistant.storage.models import WikiDocument  # do not move this import to the top of the file
        wiki_id = text.split()[1].strip()
        try:
            wiki = WikiDocument.objects.filter(bot=self.bot).get(id=wiki_id)
        except WikiDocument.DoesNotExist:
            return SingleAnswer("`Wiki not found.`", no_store=True)

        return SingleAnswer(
            text=(
                f"*`ID:`* {wiki.id}\n"
                f"*`Path:`* {TelegramMarkdownV2FormattedText(wiki.path)}\n"
                f"*`Content:`*\n"
                f"{TelegramMarkdownV2FormattedText(wiki.content)}"
            ),
            no_store=True,
        )

    async def close_dialog(self):
        self.dialog.is_completed = True
        await sync_to_async(
            lambda: self.dialog.save(update_fields=['is_completed'])
        )()

    def _update_instance(self, update_fields):
        self.instance.save(update_fields=update_fields)

    def _get_system_text(self):
        return self.bot.system_text

    async def update_state(self, state: Dict):
        self.instance.state.update(state)
        await sync_to_async(
            lambda: self.instance.save(update_fields=['state'])
        )()

    async def clear_state(self):
        self.instance.state = {}
        await sync_to_async(
            lambda: self.instance.save(update_fields=['state'])
        )()

    async def command_help(self) -> Optional[SingleAnswer]:
        if text := self.bot.help_text:
            return SingleAnswer(text, no_store=True)
        return None
