import logging
import telegram
from rest_framework.request import Request

from assistant.bot.domain import BotPlatform, Update, User, UnknownUpdate, SingleAnswer, Photo
from telegram import Bot, Update as TelegramUpdate, ReplyKeyboardRemove

from assistant.bot.platforms.telegram.format import TelegramMarkdownV2FormattedText

logger = logging.getLogger(__name__)


class TelegramBotPlatform(BotPlatform):

    def __init__(self, token: str):
        self.bot = Bot(token=token)

    async def convert_telegram_update(self, telegram_update: TelegramUpdate) -> Update:
        """Convert a Telegram update to our Update object."""
        if telegram_update.message:
            user_data = telegram_update.message.from_user
        elif telegram_update.callback_query:
            user_data = telegram_update.callback_query.from_user
        else:
            user_data = None

        user = User(
            id=str(user_data.id),
            username=user_data.username,
            first_name=user_data.first_name,
            last_name=user_data.last_name,
            language_code=user_data.language_code
        ) if user_data else None

        photo = None

        if telegram_update.message:
            chat_id = telegram_update.message.chat_id
            message_id = telegram_update.message.message_id
            text = telegram_update.message.text
            if telegram_update.message.photo:
                photo = telegram_update.message.photo[-1]
                photo_file = await self.bot.get_file(photo.file_id)
                photo_bytearray = await photo_file.download_as_bytearray()
                photo = Photo(
                    file_id=photo.file_unique_id,
                    extension=photo_file.file_path.split('.')[-1],
                    content=photo_bytearray
                )
                if not text:
                    text = telegram_update.message.caption
        elif telegram_update.callback_query:
            chat_id = telegram_update.callback_query['from']['id']
            message_id = telegram_update.callback_query['message']['message_id']
            text = telegram_update.callback_query.data
        else:
            raise UnknownUpdate('Unknown update type')

        return Update(
            chat_id=str(chat_id),
            message_id=message_id,
            text=text,
            photo=photo,
            user=user,
        )

    async def get_update(self, request: Request) -> Update:
        logger.debug(f'Got Telegram request: {request.data}')
        telegram_update = TelegramUpdate.de_json(request.data, self.bot)
        return await self.convert_telegram_update(telegram_update)

    async def post_answer(self, chat_id: str, answer: SingleAnswer):
        logger.info(f"Answer Text: {answer.text}")

        if answer.buttons:
            reply_markup = telegram.InlineKeyboardMarkup(
                [
                    [
                        telegram.InlineKeyboardButton(button.text, callback_data=button.callback_data, url=button.url)
                        for button in button_row
                    ]
                    for button_row in answer.buttons
                ]
            )
        elif answer.reply_keyboard:
            reply_markup = telegram.ReplyKeyboardMarkup(
                [
                    [telegram.KeyboardButton(button) for button in button_row]
                    for button_row in answer.reply_keyboard
                ],
                resize_keyboard=True,
            )
        else:
            reply_markup = ReplyKeyboardRemove()

        text = TelegramMarkdownV2FormattedText(answer.text)

        for parse_mode in ('MarkdownV2', None):
            try:

                if text:
                    logger.debug(f'Sending Telegram message with parse_mode={parse_mode}:\n{text}')
                await self.bot.send_message(
                    chat_id=chat_id, text=text, reply_markup=reply_markup, parse_mode=parse_mode
                )
                break
            except telegram.error.BadRequest as e:
                if "Can't parse" in e.message:
                    logger.warning(f'Can\'t parse message with parse_mode={parse_mode}: {e}')
                    continue
                else:
                    raise
            except telegram.error.Forbidden as e:
                logger.warning(f'Message sending forbidden: {e}')
                break

    async def action_typing(self, chat_id):
        await self.bot.send_chat_action(chat_id=chat_id, action='typing')
