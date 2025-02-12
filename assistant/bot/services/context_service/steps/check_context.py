from assistant.bot.services.context_service.utils import add_system_message
from assistant.bot.services.context_service.steps.base import ContextProcessingStep, ai_debugger
from assistant.bot.services.schema_service import json_prompt
from assistant.utils.repeat_until import repeat_until


class CheckContextStep(ContextProcessingStep):
    """
    Check if the context contains the answer to the user's question.
    """

    debug_info_key = 'check_context'

    @ai_debugger
    async def run(self):
        if not self._state.final_info:
            self._state.context_is_ok = False
            return
        new_messages = add_system_message(
            self._state.messages,
            (
                f"You must find out if the information below contains an answer to the user's question.\n"
                f"{self._state.final_info}\n"
                f"Do check if the information above contains an answer to the user's question.\n"
                f"As you remember, the user's question is:\n"
                f"```\n"
                f"{self._state.user_question}\n"
                f"```\n"
                f"If the information is enough just answer `true`.\n"
                f"If the information does not contain the answer, answer `false`.\n"
                f"{json_prompt('check_context')}"
            )
        )
        response = await repeat_until(
            self._fast_ai.get_response, new_messages, max_tokens=256,
            json_format=True,
            condition=lambda resp: 'result' in resp.result
        )
        self._state.context_is_ok = response.result['result']
