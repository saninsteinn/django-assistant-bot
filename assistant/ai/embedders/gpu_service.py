from typing import List

import aiohttp

from assistant.ai.providers.base import AIEmbedder


class GPUServiceEmbedder(AIEmbedder):

    def __init__(self, base_url: str, model=str):
        self._base_url = base_url
        self._model = model

    async def embeddings(self, input: List[str]) -> List[List[float]]:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self._base_url}/embeddings/",
                json={
                    "model": self._model,
                    "texts": input
                },
            ) as response:
                if response.status != 200:
                    raise Exception(f"Failed to get embeddings. "
                                    f"Got status code {response.status} from GPU Service with message {await response.text()}")
                response_data = await response.json()
                embeddings = response_data['embeddings']
                return embeddings





