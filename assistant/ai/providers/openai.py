import json
import logging
import time
from typing import List

from openai import AsyncOpenAI
from assistant.ai.domain import Message, AIResponse
from assistant.ai.providers.base import AIProvider

logger = logging.getLogger(__name__)


class ChatGPTAIProvider(AIProvider):

    def __init__(self, model: str, api_key: str):
        self._model = model
        self._client = AsyncOpenAI(
            api_key=api_key
        )

    @property
    def context_size(self) -> int:
        return 8000  # TODO: get by model

    def calculate_tokens(self, text: str) -> int:
        return len(text.split()) // 2

    async def get_response(
            self,
            messages: List[Message],
            max_tokens=1024,
            json_format: bool = False
    ) -> AIResponse:
        start_ts = time.time()
        kwargs = {}
        if json_format:
            kwargs['response_format'] = {"type": "json_object"}

        chat_response = await self._client.chat.completions.create(
            model=self._model,
            messages=[dict(m) for m in messages],
            max_tokens=max_tokens,
            **kwargs
        )
        end_ts = time.time()

        logger.debug(f'Raw GPT response ({end_ts - start_ts} s): {chat_response}')

        choice = chat_response.choices[0]
        if json_format:
            result = json.loads(choice.message.content)
        else:
            result = choice.message.content.strip()
        ai_response = AIResponse(
            result=result,
            usage={
                'model': chat_response.model,
                'prompt_tokens': chat_response.usage.prompt_tokens,
                'completion_tokens': chat_response.usage.completion_tokens,
            },
            length_limited=choice.finish_reason == 'length'
        )
        return ai_response


