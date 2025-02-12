import logging

from asgiref.sync import sync_to_async

from assistant.ai.services.ai_service import get_ai_embdedder
from django.conf import settings

from assistant.processing.documents.steps.base import DocumentProcessingStep
from assistant.storage.models import Document, Sentence, Question

logger = logging.getLogger(__name__)


class SentencesEmbeddingsStep(DocumentProcessingStep):

    def __init__(self, document: Document):
        super().__init__(document)
        self._ai_embedder = get_ai_embdedder(settings.EMBEDDING_AI_MODEL)

    async def run(self):
        self._logger.info(f'Embedding sentences for document {self._document}')

        sentences = await (sync_to_async(
            lambda: list(self._document.sentences.all())
        ))()

        if sentences:
            sentences_embeddings = await self._ai_embedder.embeddings(
                [s.text for s in sentences]
            )
            logger.debug(f'Sentences embedding len: {len(sentences_embeddings)}')
            assert len(sentences_embeddings) == len(sentences)
            for e in sentences_embeddings:
                assert len(e) > 0
            for s, e in zip(sentences, sentences_embeddings):
                s.embedding = e
            await (sync_to_async(
                lambda: Sentence.objects.bulk_update(sentences, fields=['embedding'])
            ))()

        logger.debug(f'Sentences embedded for document {self._document}')


class QuestionsEmbeddingsStep(DocumentProcessingStep):

    def __init__(self, document: Document):
        super().__init__(document)
        self._ai_embedder = get_ai_embdedder(settings.EMBEDDING_AI_MODEL)

    async def run(self):
        self._logger.info(f'Embedding questions for document {self._document}')

        questions = await (sync_to_async(
            lambda: list(self._document.questions.all())
        ))()

        if questions:
            questions_embeddings = await self._ai_embedder.embeddings(
                [q.text for q in questions]
            )
            logger.debug(f'Questions embedding len: {len(questions_embeddings)}')
            assert len(questions_embeddings) == len(questions)
            for e in questions_embeddings:
                assert len(e) > 0
            for q, e in zip(questions, questions_embeddings):
                q.embedding = e
            await (sync_to_async(
                lambda: Question.objects.bulk_update(questions, fields=['embedding'])
            ))()

        logger.debug(f'Questions embedded for document {self._document}')


class ContentEmbeddingsStep(DocumentProcessingStep):

    def __init__(self, document: Document):
        super().__init__(document)
        self._ai_embedder = get_ai_embdedder(settings.EMBEDDING_AI_MODEL)

    async def run(self):
        self._logger.info(f'Embedding content for document {self._document}')

        content_embedding = (await self._ai_embedder.embeddings([self._document.content]))[0]
        assert len(content_embedding) > 0
        self._document.content_embedding = content_embedding
        await (sync_to_async(
            self._document.save
        ))(update_fields=['content_embedding'])

        logger.debug(f'Content embedded for document {self._document}')