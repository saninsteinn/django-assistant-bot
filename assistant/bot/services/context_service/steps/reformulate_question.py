from assistant.bot.services.context_service.utils import add_system_message
from assistant.bot.services.context_service.steps.base import ContextProcessingStep, ai_debugger
from assistant.bot.services.schema_service import json_prompt
from assistant.utils.repeat_until import repeat_until


class ReformulateQuestionStep(ContextProcessingStep):

    debug_info_key = 'reformulate_question'

    @ai_debugger
    async def run(self):
        new_messages = add_system_message(
            self._state.messages,
            (
                f"Reformulate the user's question in a way "
                f"that will help to search answer in the database by sentence embeddings.\n"
                f"Do not answer the question, but just reformulate to provide the search query.\n"
                f"You must use the original query language.\n"
                f"{json_prompt(['reformulate'])}"
            )
        )

        response = await repeat_until(
            self._fast_ai.get_response, new_messages, max_tokens=256,
            json_format=True,
            condition=lambda resp: 'query' in resp.result
        )

        query = response.result['query']
        self._logger.info(f'Reformulated question: {query}')
        self._debug_info['new_question'] = query
        self._state.user_question = query


