import functools
import logging
from abc import ABC, abstractmethod
from typing import Dict

from assistant.ai.providers.base import AIDebugger
from assistant.ai.services.ai_service import get_ai_provider
from assistant.bot.models import Bot
from assistant.bot.services.context_service.state import ContextProcessingState
from assistant.utils.debug import TimeDebugger


class ContextProcessingStep(ABC):

    debug_info_key: str = None

    def __init__(
            self,
            bot: Bot,
            state: ContextProcessingState,
            fast_ai_model: str,
            strong_ai_model: str,
            debug_info: Dict = None
    ):
        self._bot = bot
        self._state = state
        self._fast_ai = get_ai_provider(fast_ai_model)
        self._strong_ai = get_ai_provider(strong_ai_model)
        if self.debug_info_key is not None:
            if self.debug_info_key not in debug_info:
                debug_info[self.debug_info_key] = {}
            self._debug_info = debug_info[self.debug_info_key]
        self._logger = logging.getLogger(self.__class__.__name__)

    @abstractmethod
    async def run(self):
        pass


def time_debugger(func):
    @functools.wraps(func)
    async def wrapper(self, *args, **kwargs):
        with TimeDebugger(self._debug_info):
            result = await func(self, *args, **kwargs)
        return result
    return wrapper


def ai_debugger(func):
    @functools.wraps(func)
    async def wrapper(self, *args, **kwargs):
        with AIDebugger(self._fast_ai, self._debug_info):
            with AIDebugger(self._strong_ai, self._debug_info):
                result = await func(self, *args, **kwargs)
        return result
    return wrapper