from typing import List, Tuple

from asgiref.sync import sync_to_async
from fuzzywuzzy import process

from assistant.bot.services.context_service.utils import add_system_message, get_list_str
from assistant.bot.services.context_service.steps.base import ContextProcessingStep, ai_debugger
from assistant.bot.services.schema_service import json_prompt
from assistant.storage.models import WikiDocument, Document, Question, WikiDocumentProcessing
from assistant.utils.repeat_until import repeat_until


class ClassifyStep(ContextProcessingStep):
    """
    Classifies the question using the context.
    """

    debug_info_key = 'classify'

    _offtopic_examples = [
        ("Hello", "Small talk"),
        ("How are you?", "Small talk"),
        ("What's the weather in Moscow?", "Small talk")
    ]

    @ai_debugger
    async def run(self):
        wds = await (sync_to_async(
            lambda: list(WikiDocument.objects.filter(
                bot=self._bot, processing__status=WikiDocumentProcessing.Status.COMPLETED,
                parent=None
            ))
        ))()
        smalltalk_choice = 'Small talk'
        topics = [smalltalk_choice] + [t.title for t in wds]
        examples = self._offtopic_examples + await sync_to_async(self._examples)(wds)
        new_messages = add_system_message(
            self._state.messages,
            self.prompt(topics, examples, self._state.user_question)
        )
        response = await repeat_until(
            self._fast_ai.get_response, new_messages, max_tokens=256,
            json_format=True,
            condition=self._condition
        )

        topic = response.result['topic']
        self._logger.info(f'Classified question: {topic}')

        matches = process.extractBests(topic, topics)
        matches.sort(key=lambda x: x[1], reverse=True)
        best_title = matches[0][0]
        if best_title == smalltalk_choice:
            self._debug_info['topic'] = 'Small talk'
            return None

        i = topics.index(best_title)
        wd = wds[i - 1]
        self._debug_info['topic'] = wd.title
        self._state.topic = wd

    @staticmethod
    def prompt(topics, examples, user_question):
        topics_str = get_list_str(topics)
        examples_str = get_list_str(
            [f'"{q}" -> "{t}"' for q, t in examples]
        )
        return (
            f"Classify the user's question in a way that will help to search answer in the database by sentence embeddings.\n"
            f"Do not answer the question, but just classify to provide the search query.\n\n"
            f"Possible topics:\n"
            f"{topics_str}\n"
            f"Examples:\n"
            f"{examples_str}\n\n"
            f"Please, provide the topic name that is relevant to the user question:\n"
            f"```\n"
            f"{user_question}\n"
            f"```\n"
            f"Give only the topic name in the original spelling including language.\n"
            f"{json_prompt(['classify'])}"
        )

    def _examples(self, wiki_docs: List[WikiDocument], numbers_per_topic=2) -> List[Tuple[str, str]]:
        result = []
        for wiki in wiki_docs:
            questions = Question.objects.filter(
                document__wiki__tree_id=wiki.tree_id,
                document__wiki__lft__gt=wiki.lft,
                document__wiki__rght__lt=wiki.rght
            ).order_by('?')[:numbers_per_topic]
            for q in questions:
                result.append((q.text, wiki.title))
        return result

    @staticmethod
    def _condition(response):
        return 'topic' in response.result and isinstance(response.result['topic'], str)
