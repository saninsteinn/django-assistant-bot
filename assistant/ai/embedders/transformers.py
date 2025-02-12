import torch
from typing import List
from transformers import AutoTokenizer, AutoModel
from assistant.ai.providers.base import AIEmbedder
from assistant.ai.utils.transformers import get_torch_device


class TransformersEmbedder(AIEmbedder):
    def __init__(self, model_name: str, local_files_only: bool = True):
        self._model_name = model_name
        self._tokenizer = AutoTokenizer.from_pretrained(model_name, local_files_only=local_files_only)
        self._device = get_torch_device()
        self._model = AutoModel.from_pretrained(model_name, local_files_only=local_files_only).to(self._device)

    async def embeddings(self, input: List[str]) -> List[List[float]]:
        result = []
        for text in input:
            inputs = self._tokenizer(text, return_tensors="pt").to(self._device)

            # Get embeddings
            with torch.no_grad():
                outputs = self._model(**inputs)

            # Extract the embeddings and average them
            embeddings = outputs.last_hidden_state.mean(dim=1).squeeze().tolist()

            result.append(embeddings)

        return result
