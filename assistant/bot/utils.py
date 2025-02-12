import logging
from functools import lru_cache

from django.conf import settings
from django.http import Http404
from django.utils.module_loading import import_string

from assistant.bot.domain import BotPlatform
from assistant.bot.models import Bot as BotModel
from assistant.bot.platforms.telegram.platform import TelegramBotPlatform


logger = logging.getLogger(__name__)


class MaxAttemptsExceededError(Exception):
    """Raised when the maximum number of attempts is exceeded."""
    pass


def truncate_text(text, max_tokens=1024):
    """Truncate text to max_tokens."""
    tokens = text.split()
    if len(tokens) > max_tokens:
        tokens = tokens[:max_tokens]
        text = " ".join(tokens) + '...'
    return text


def get_bot_platform(bot_codename: str, platform_codename: str) -> BotPlatform:
    bot_qs = BotModel.objects.filter(
        codename=bot_codename,
    )
    if platform_codename == 'telegram':
        token = bot_qs.values_list('telegram_token', flat=True).first()
        if token is None:
            raise Http404('Bot not found')
        return TelegramBotPlatform(token)


_default_bot_class_path = getattr(settings, 'DEFAULT_BOT_CLASS', 'assistant.bot.assistant_bot.AssistantBot')


@lru_cache
def get_bot_class(bot_codename):
    bot_class_path = getattr(settings, 'BOT_CLASSES', {}).get(bot_codename, _default_bot_class_path)
    logger.info(f"Using bot class {bot_class_path} for bot {bot_codename}")
    return import_string(bot_class_path)
