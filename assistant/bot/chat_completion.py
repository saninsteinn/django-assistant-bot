import logging
from typing import Optional

from assistant.ai.domain import AIResponse
from assistant.ai.providers.base import AIDebugger
from assistant.ai.services.ai_service import get_ai_provider, extract_tagged_text
from assistant.bot.domain import Answer, SingleAnswer, Button, NoResourceFound
from assistant.bot.models import Bot
from assistant.bot.resource_manager import ResourceManager
from assistant.bot.services.context_service.service import ContextService


logger = logging.getLogger(__name__)


class ChatCompletion:

    def __init__(self, bot: Bot, resource_manager: ResourceManager, fast_ai_model: str, strong_ai_model: str):
        self.bot = bot
        self.fast_ai_model = fast_ai_model
        self.strong_ai_model = strong_ai_model
        self.resource_manager = resource_manager

    async def generate_answer(self, messages: list, debug_info: dict = None, do_interrupt=None) -> AIResponse:

        if messages:
            debug_info['query'] = messages[-1]['content']

        context_service = ContextService(
            bot=self.bot,
            fast_ai_model=self.fast_ai_model,
            strong_ai_model=self.strong_ai_model,
            messages=messages,
            debug_info=debug_info,
            do_interrupt=do_interrupt
        )

        enriched_messages = await context_service.enrich()

        strong_ai = get_ai_provider(self.strong_ai_model)

        with AIDebugger(strong_ai, debug_info, 'final'):
            ai_response = await strong_ai.get_response(enriched_messages)

        return ai_response
