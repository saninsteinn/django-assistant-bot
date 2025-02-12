from asgiref.sync import sync_to_async

from assistant.bot.services.context_service.steps.base import ContextProcessingStep, ai_debugger
from assistant.bot.services.context_service.utils import add_system_message, get_numerical_list_str
from assistant.bot.services.schema_service import json_prompt
from assistant.utils.repeat_until import repeat_until


class ChooseKnownQuestionStep(ContextProcessingStep):
    """
    Choose known question from the related questions.
    """

    debug_info_key = 'known_question_choice'

    prompt = (
        "The user asked a question:\n"
        "```\n"
        "{user_question}\n"
        "```\n\n"
        "Your task is to determine if any of the known questions below have the same meaning as the user's question. "
        "Two questions have the same meaning if the answer to the user's question would also correctly answer the known question. "
        "Only consider questions to be the same if their answers would be identical.\n"
        "Here are the known questions:\n"
        "```\n"
        "{questions}\n"
        "```\n"
        "Please provide the number of the known question that matches the user's question in meaning. "
        "If none of the known questions match the user's question in meaning, provide `null`.\n"
        f"{json_prompt(['choose_known_question']).replace('{', '{{').replace('}', '}}')}"
    )

    @ai_debugger
    async def run(self):
        questions = self._state.related_questions

        new_messages = add_system_message(
            # self._state.messages,
            [],
            self.prompt.format(
                user_question=self._state.user_question,
                questions=get_numerical_list_str([q.text for q in questions[:5]])
            )
        )
        response = await repeat_until(
            self._fast_ai.get_response, new_messages, json_format=True,
            condition=lambda response: 'question' in response.result and (
                        isinstance(response.result['question'], int) or response.result['question'] is None
            )
        )
        the_same_question = response.result['question']
        if the_same_question:
            the_same_question = the_same_question - 1
            self._debug_info['the_same_question'] = questions[the_same_question].text
            document = await sync_to_async(
                lambda: questions[the_same_question].document
            )()
            self._debug_info['document'] = f"[{document.id}] {document.name}"
            self._state.documents = [document]
        else:
            self._debug_info['the_same_question'] = None
