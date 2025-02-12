import logging
from typing import List

from assistant.ai.domain import Message, AIResponse
from assistant.ai.providers.base import AIProvider
from assistant.ai.services.ai_service import get_ai_provider

logger = logging.getLogger(__name__)


class AIDialog(AIProvider):

    _model: str
    messages: List[Message]

    def __init__(self, model):
        self._model = model
        self._provider = get_ai_provider(model)

    async def prompt(self, context: str, role='user', *args, **kwargs) -> AIResponse:
        message = Message(role=role, content=context)
        ai_response = await self._provider.get_response(
            messages=[message],
            *args, **kwargs
        )
        logger.debug(f'AI response: {ai_response}')
        return ai_response

    @property
    def calls_attempts(self):
        return self._provider.calls_attempts

    @calls_attempts.setter
    def calls_attempts(self, value):
        self._provider.calls_attempts = value

    @property
    def context_size(self) -> int:
        return self._provider.context_size

    def calculate_tokens(self, text: str) -> int:
        return self._provider.calculate_tokens(text)

    async def get_response(self, messages: List[Message], max_tokens=1024, json_format: bool = False) -> AIResponse:
        return await self._provider.get_response(messages, max_tokens, json_format)



