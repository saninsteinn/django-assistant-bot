import logging
from abc import ABC, abstractmethod
from functools import lru_cache
from typing import List, Type

from asgiref.sync import sync_to_async
from django.conf import settings
from django.utils.module_loading import import_string

from assistant.processing.documents.steps.base import DocumentProcessingStep
from assistant.processing.documents.steps.embeddings import SentencesEmbeddingsStep, QuestionsEmbeddingsStep
from assistant.processing.documents.steps.formatter import DocumentFormatStep
from assistant.processing.documents.steps.questions import GenerateQuestionsStep, MergeQuestionsStep
from assistant.processing.documents.steps.sentences import ExtractSentencesStep
from assistant.storage.models import Document


logger = logging.getLogger(__name__)


class DocumentProcessor(ABC):

    @property
    @abstractmethod
    def steps(self) -> List[Type[DocumentProcessingStep]]:
        pass

    @abstractmethod
    def process(self, document: Document):
        pass


class DefaultDocumentProcessor(DocumentProcessor):

    @property
    def steps(self) -> List[Type[DocumentProcessingStep]]:
        return [
            DocumentFormatStep,
            ExtractSentencesStep,
            GenerateQuestionsStep,
            SentencesEmbeddingsStep,
            QuestionsEmbeddingsStep,
            MergeQuestionsStep,
        ]

    async def process(self, document: Document):
        for step_cls in self.steps:
            step = step_cls(
                document=document
            )
            await step.run()


async def process_document(document: Document):
    processor = await sync_to_async(
        lambda: get_document_processor(document.wiki.bot.codename)
    )()
    await processor.process(document)


_default_document_processor_class_path = getattr(
    settings, 'DOCUMENT_PROCESSOR_CLASSES', 'processing.documents.processor.DefaultDocumentProcessor'
)


@lru_cache
def get_document_processor(bot_codename: str) -> DocumentProcessor:
    document_processor_class_path = getattr(settings, 'DOCUMENT_PROCESSOR_CLASSES', {}).get(
        bot_codename, _default_document_processor_class_path
    )
    logger.info(f"Using document processor class {document_processor_class_path} for bot {bot_codename}")
    document_processor_class = import_string(document_processor_class_path)
    return document_processor_class()
