from typing import List

from assistant.ai.domain import Message
from assistant.storage.models import Document, Question, WikiDocument


class ContextProcessingState:

    messages: List[Message] = None
    topic: WikiDocument = None
    related_questions: List[Question] = None
    documents: List[Document] = None
    final_info: str = None
    context_is_ok: bool = None

    done: bool = False

    @property
    def user_question(self) -> str:
        return self.messages[-1]['content'].strip()

    @user_question.setter
    def user_question(self, value: str):
        self.messages[-1]['content'] = value
