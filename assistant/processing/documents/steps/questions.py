import logging
from typing import List

from asgiref.sync import sync_to_async
from assistant.ai.dialog import AIDialog
from django.conf import settings

from assistant.processing.documents.steps.base import DocumentProcessingStep
from assistant.processing.utils import json_prompt, split_text_by_parts
from assistant.storage.models import Document, Question
from assistant.rag.services.search_service import embedding_search_questions
from assistant.utils.language import get_language
from assistant.utils.repeat_until import repeat_until


logger = logging.getLogger(__name__)


class GenerateQuestionsStep(DocumentProcessingStep):

    def __init__(self, document: Document):
        super().__init__(document)
        self._ai = AIDialog(
            settings.QUESTIONS_AI_MODEL
        )

    async def run(self):
        self._logger.info(f"Generate questions for document {self._document}")

        doc_path = await (sync_to_async(lambda: self._document.wiki.path))()
        doc_full_title = doc_path.replace(' / ', '. ')
        text = (
            f"# {doc_full_title}\n\n"
            f"{self._document.content}\n"
        )

        questions = []
        i = 0
        for part in split_text_by_parts(text, 500):
            part_questions = await self._generate_questions(part)
            questions.extend([
                Question(
                    document=self._document,
                    text=question,
                    order=i
                )
                for question in part_questions
            ])

        await (sync_to_async(
            lambda: Question.objects.bulk_create(questions)
        ))()

    async def _generate_questions(self, text: str) -> List[str]:
        """
        Split the document into sentences using AI.
        """
        prompt = (
            f"This is a text of a document:\n"
            f"```\n"
            f"{text.strip()}\n"
            f"```\n"
            f"Generate all possible questions that this document will help ANSWER.\n"
            f"Do not generate questions for which the answers are not contained in the text.\n"
            f"Include appropriate keywords in your questions so that they match the document well when searching.\n"
            # f"The total length of the questions must not be less than the length of the document.\n"
            f"You must provide sentences in natural formatting removing any extra spaces or symbols.\n"
            f"You must use the ORIGINAL DOCUMENT LANGUAGE in the answer.\n"
            f"{json_prompt('document_questions')}"
        )

        def check_fn(response):
            if 'questions' not in response.result:
                logger.warning(f'Questions not found in response: {response.result}')
                return False

            questions = response.result['questions']
            if not all(isinstance(part, str) for part in questions):
                logger.warning(f'Invalid questions: {questions}')
                return False

            estimated_total_length = int(len(text) * 0.5)

            total_length = sum(len(part) for part in questions)
            if total_length < estimated_total_length:
                logger.warning(f'Too short questions: {total_length} / {estimated_total_length}')
                return False

            if not all(get_language(part) == 'ru' for part in questions):
                logger.warning(f'Invalid questions language: {[get_language(part) == "ru" for part in questions]}')
                return False

            return True

        response = await repeat_until(
            self._ai.prompt, prompt, json_format=True,
            condition=check_fn
        )

        questions = response.result['questions']
        return questions


class MergeQuestionsStep(DocumentProcessingStep):

    def __init__(self, document: Document):
        super().__init__(document)
        self._ai = AIDialog(
            settings.QUESTIONS_AI_MODEL
        )

    async def run(self):
        self._logger.info(f"Merge questions for document {self._document}")

        questions = await sync_to_async(
            lambda: list(self._document.questions.all())
        )()
        if not questions:
            return

        for q in questions:
            similar_question = await embedding_search_questions(
                query_embedding=q.embedding,
                qs=Question.objects.filter(document__id__lt=self._document.id),
                n=1
            )
            if not similar_question:
                continue
            similar_question = similar_question[0]

            self._logger.info(f"Question: {q.text}")
            self._logger.info(f"Similar question: {similar_question.text}")
            self._logger.info(f"Distance: {similar_question.distance}")

            if similar_question.distance <= 0.05:
                is_similar = await self._check_similarity(q.text, similar_question.text)
                self._logger.info(f"Is similar: {is_similar}")
                if is_similar:
                    await self._merge_queries(q, similar_question)

    async def _check_similarity(self, question: str, similar_question: str) -> bool:
        if question == similar_question:
            return True
        prompt = (
            f"Check if the following two questions have exactly the same meaning:\n"
            f"```\n"
            f"1. {question}\n"
            f"2. {similar_question}\n"
            f"```\n\n"
            f"When comparing, consider the following:\n"
            f"1. Questions may differ in context, purpose, level of detail, or scope even a little.\n"
            f"2. Questions are considered to have the same meaning if they request exactly the same information or have exactly the same goal.\n"
            f"3. Questions are considered to have different meanings if they target different aspects, contexts, levels of detail, or scopes. Even a little.\n"
            f"\n"
            f"Please answer 'true' if the questions are the same, 'false' otherwise.\n"
            f"{json_prompt('questions_similarity')}"
        )
        # print("PROMPT:")
        # print(prompt)
        response = await repeat_until(
            self._ai.prompt, prompt, json_format=True,
            condition=lambda response: isinstance(response.result.get('result'), bool)
        )
        return response.result['result']

    async def _merge_queries(self, question: Question, similar_question: Question):
        prompt = await sync_to_async(
            lambda: (
                f"Choose one of the two documents that contains the best answer to the following question:\n"
                f"```\n"
                f"{question.text}\n"
                f"```\n\n"
                f"1. The first document\n"
                f"```\n"
                f"# {question.document.wiki.path.replace(' / ', '. ')}\n\n"
                f"{question.document.content}\n"
                f"```\n\n"
                f"2. The second document\n"
                f"```\n"
                f"# {similar_question.document.wiki.path.replace(' / ', '. ')}\n\n"
                f"{similar_question.document.content}\n"
                f"```\n\n"
                f"Please answer `1` if the first document is better, or `2` if the second document is better.\n"
                f"{json_prompt('questions_merge')}"
            )
        )()
        print("PROMPT:")
        print(prompt)

        response = await repeat_until(
            self._ai.prompt, prompt, json_format=True,
            condition=lambda response: response.result.get('result') in (1, 2)
        )
        print('MERGE:', response.result['result'])

        if response.result['result'] == 1:
            await sync_to_async(
                lambda: similar_question.delete()
            )()
        elif response.result['result'] == 2:
            await sync_to_async(
                lambda: question.delete()
            )()



# def split_text_to_sentences(text: str) -> List[str]:
#     # Regular expression to split text into sentences
#     sentence_endings = re.compile(r'(?<!\w\.\w.)(?<![A-Z][a-z]\.)(?<=\.|\?|\!)\s')
#     sentences = sentence_endings.split(text)
#     return [sentence.strip() for sentence in sentences]
