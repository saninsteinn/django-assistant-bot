import logging
from abc import ABC, abstractmethod

from assistant.storage.models import Document


class DocumentProcessingStep(ABC):

    _document: Document

    def __init__(self, document: Document):
        self._document = document
        self._logger = logging.getLogger(self.__class__.__name__)

    @abstractmethod
    def run(self):
        pass

