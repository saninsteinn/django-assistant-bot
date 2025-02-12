from typing import List

from ollama import AsyncClient

from assistant.ai.providers.base import AIEmbedder


class OllamaEmbedder(AIEmbedder):

    def __init__(self, host: str, model: str):
        self._model = model
        self._client = AsyncClient(
            host=host
        )

    async def embeddings(self, input: List[str]) -> List[List[float]]:
        result = []
        for text in input:
            response = await self._client.embeddings(model=self._model, prompt=text)
            embeding = response['embedding']
            result.append(embeding)
        return result
