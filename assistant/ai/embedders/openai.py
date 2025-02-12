from typing import List

from openai import AsyncOpenAI

from assistant.ai.providers.base import AIEmbedder


class ChatGPTEmbedder(AIEmbedder):

    def __init__(self, model: str, api_key: str):
        self._model = model
        self._client = AsyncOpenAI(
            api_key=api_key
        )

    async def embeddings(self, input: List[str]) -> List[List[float]]:
        response = (await self._client.embeddings.create(
            model=self._model,
            input=input
        ))
        embeddings = [
            embedding.embedding
            for embedding in response.data
        ]
        return embeddings
