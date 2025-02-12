from typing import List

import aiohttp

from assistant.ai.domain import Message, AIResponse
from assistant.ai.providers.base import AIProvider


class GPUServiceProvider(AIProvider):

    def __init__(self, base_url: str, model=str):
        self._base_url = base_url
        self._model = model

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
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self._base_url}/dialog/",
                json={
                    "model": self._model,
                    "messages": messages,
                },
            ) as response:
                if response.status != 200:
                    raise Exception(f"Failed to get response. "
                                    f"Got status code {response.status} from GPU Service with message {await response.text()}")
                response_data = await response.json()
                response = AIResponse(**response_data['response'])
                return response





