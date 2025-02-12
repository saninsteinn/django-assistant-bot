from datetime import datetime

from assistant.bot.services.context_service.utils import add_system_message
from assistant.bot.services.context_service.steps.base import ContextProcessingStep, ai_debugger


class FinalPromptStep(ContextProcessingStep):
    """
    Create a final prompt to answer the user's question.
    """
    debug_info_key = 'final'

    @ai_debugger
    async def run(self):
        if self._state.context_is_ok:
            self._state.messages = add_system_message(
                self._state.messages,
                (
                    f"You must answer the user only using the following information:\n"
                    f"```\n"
                    f"{self._state.final_info}\n"
                    f"# Current date: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`\n\n"
                    f"```\n"
                    f"As you remember, the question from the user is:\n"
                    f"```\n"
                    f"{self._state.user_question}\n"
                    f"```\n"
                    f"If that information does not contain the answer, you must say that you don't have information like "
                    f"\"I'm sorry, I don't have enough information to answer your question.\" (but in user's language).\n"
                    f"Follow the original wording as much as possible.\n"
                    f"It would be ideal if your answer was an exact and complete quote from the document. "
                    f"Don't leave out details in your answer.\n"
                )
            )
        else:
            self._state.messages = add_system_message(
                self._state.messages,
                (
                    f"Unfortunately, there is not enough information to answer the user's question for you.\n"
                    f"Answer the user that you could not help with the question.\n"
                )
            )
        self._debug_info['input'] = [
            f"[{doc.id}] {doc.name}" for doc in self._state.documents
        ]
