import json
import logging

import groq
import time
from json import JSONDecodeError
from typing import List

from assistant.ai.domain import Message, AIResponse
from assistant.ai.providers.base import AIProvider
from groq import AsyncGroq

from assistant.utils.throttle import Throttle

logger = logging.getLogger(__name__)


class GroqAIProvider(AIProvider):
    """
    GPT-3 provider based on Groq API (https://groq.com/).
    """

    calls_attempts: List[int] = None
    _throttle = Throttle(2)  # https://console.groq.com/settings/limits

    def __init__(self, model: str, api_key: str, debug=False):
        self._model = model
        self._client = AsyncGroq(
            api_key=api_key,
        )
        if debug:
            self.calls_attempts = []


    @property
    def context_size(self) -> int:
        return 8000  # TODO: get by model

    def calculate_tokens(self, text: str) -> int:
        return len(text.split()) // 2  # TODO: get by model

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

        call_attempts = 0
        while call_attempts < 5:
            try:
                call_attempts += 1
                await self._throttle()


                converted_messages = [self.convert_message(m) for m in messages]
                for m in converted_messages:
                    if isinstance(m['content'], list):
                        converted_messages = [
                            m for m in converted_messages
                            if m['role'] != 'system'
                        ]
                        break

                chat_response = await self._client.chat.completions.create(
                    model=self._model,
                    messages=converted_messages,
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
                break
            except groq.BadRequestError as e:
                if not json_format:
                    raise
                if not 'JSON' in str(e):
                    raise
                logger.warning("Failed to parse JSON response (attempt %d). Retrying...", call_attempts)
        else:
            raise ValueError("Failed to parse JSON response")

        ai_response = AIResponse(
            result=result,
            usage={
                'model': chat_response.model,
                'prompt_tokens': chat_response.usage.prompt_tokens,
                'completion_tokens': chat_response.usage.completion_tokens,
            },
            length_limited=choice.finish_reason == 'length'
        )
        if self.calls_attempts is not None:
            self.calls_attempts.append(call_attempts)

        return ai_response

    def convert_message(self, message: Message) -> dict:
        content = []
        if message.get('images'):
            if message.get('content'):
                content.append(
                    {
                        "type": "text",
                        "text": message['content']
                    },
                )
            for img in message.get('images', []):
                content.append(
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{img}"
                        }
                    },
                )
        else:
            content = message['content']
        return {
            "role": message['role'],
            "content": content,
        }
