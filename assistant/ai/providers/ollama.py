import json
import logging
import time
from json import JSONDecodeError
from typing import List

from ollama import AsyncClient, Options

from assistant.ai.providers.base import AIProvider

from assistant.ai.domain import Message, AIResponse

logger = logging.getLogger(__name__)


class OllamaAIProvider(AIProvider):

    calls_attempts: List[int] = None

    def __init__(self, model: str, host: str, debug=False):
        self._model = model
        self._client = AsyncClient(
            host=host
        )
        if debug:
            self.calls_attempts = []

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
            kwargs['format'] = 'json'

        self._check_roles(messages)

        call_attempts = 0
        while call_attempts < 5:
            try:
                call_attempts += 1
                logger.debug(f'Getting Ollama response for messages: {messages}')

                chat_response = await self._client.chat(
                    model=self._model,
                    messages=[dict(m) for m in messages],
                    options=Options(num_predict=max_tokens),
                    **kwargs
                )
                end_ts = time.time()

                logger.debug(f'Raw Ollama response ({end_ts - start_ts} s): {chat_response}')

                if json_format:
                    content = chat_response['message']['content']
                    if '\t\t\t\t' in content or '\n\n\n\n' in content:
                        logger.warning("Detected multiple tabs or newlines in the response. Retrying...")
                        continue
                    result = json.loads(content)
                else:
                    result = chat_response['message']['content'].strip()
                break
            except JSONDecodeError:
                if not json_format:
                    raise
                if '\n' in content and not '\\n' in content:
                    content = content.replace('\n', '\\n')
                    try:
                        result = json.loads(content)
                        logger.warning("Successfully parsed JSON response after replacing newlines")
                        break
                    except JSONDecodeError:
                        pass
                logger.warning("Failed to parse JSON response (attempt %d). Retrying...", call_attempts)
        else:
            raise ValueError("Failed to parse JSON response")

        ai_response = AIResponse(
            result=result,
            usage={
                'model': chat_response['model'],
                'prompt_tokens': chat_response.get('prompt_eval_count', 0),
                'completion_tokens': chat_response.get('eval_count', 0),
            },
            length_limited=not chat_response['done']
        )
        if self.calls_attempts is not None:
            self.calls_attempts.append(call_attempts)

        return ai_response

    @staticmethod
    def _check_roles(messages: List[Message]):
        for i in range(1, len(messages)):
            # Compare current role with the previous one
            if messages[i]['role'] == messages[i - 1]['role']:
                raise ValueError("OllamaAIProvider does not support multiple messages from the same role")
