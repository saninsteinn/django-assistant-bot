from abc import ABC, abstractmethod
from typing import List

from assistant.ai.domain import AIResponse, Message
from assistant.utils.debug import TimeDebugger


class AIProvider(ABC):

    @property
    @abstractmethod
    def context_size(self) -> int:
        """
        Get the context size of the AI model.
        """
        pass

    @abstractmethod
    def calculate_tokens(self, text: str) -> int:
        """
        Calculate the number of tokens in the given text.
        """
        pass

    @abstractmethod
    async def get_response(
            self,
            messages: List[Message],
            max_tokens=1024,
            json_format: bool = False
    ) -> AIResponse:
        """
        Get GPT response for the given messages.
        """
        pass


class AIEmbedder(ABC):

    @abstractmethod
    async def embeddings(self, input: List[str]) -> List[List[float]]:
        """
        Get embeddings for the given input.
        """
        pass


class AIDebugger(TimeDebugger):

    def __init__(self, ai: AIProvider, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ai = ai

    def __enter__(self):
        self.ai.calls_attempts = []
        return super().__enter__()

    @property
    def call_attempts(self):
        try:
            return self._call_attempts
        except AttributeError:
            if hasattr(self.ai, 'calls_attempts'):
                return sum(self.ai.calls_attempts)

    def __exit__(self, exc_type, exc_val, exc_tb):
        super().__exit__(exc_type, exc_val, exc_tb)
        self._call_attempts = self.call_attempts
        self.info['attempts'] = self.call_attempts
        self.info['model'] = getattr(self.ai, '_model', None)

