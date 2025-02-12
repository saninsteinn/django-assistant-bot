import logging
from typing import List

from asgiref.sync import sync_to_async
from django.conf import settings

from assistant.ai.dialog import AIDialog
from assistant.processing.utils import json_prompt
from assistant.storage.models import Document, WikiDocument, WikiDocumentProcessing
from assistant.utils.language import get_language
from assistant.utils.repeat_until import repeat_until

logger = logging.getLogger(__name__)


class WikiDocumentSplitter:

    def __init__(self, wiki_document: WikiDocument):
        self._wiki_document = wiki_document
        self._ai = AIDialog(
            settings.SPLIT_DOCUMENTS_AI_MODEL
        )

    async def run(self) -> WikiDocumentProcessing:
        logger.info(
            f"Split document \"{self._wiki_document}\". Content length: {len(self._wiki_document.content)}"
        )

        processing = await sync_to_async(
            WikiDocumentProcessing.objects.create
        )(wiki_document=self._wiki_document)

        new_documents = []
        names = await self._get_section_names()
        logger.info(f"Section names: {names}")

        for section_name in names:
            section = await self._get_section(names, section_name)
            logger.info(f"Got section \"{section_name}\". Content length: {len(section)}")
            new_document = await (sync_to_async(Document.objects.create))(
                processing=processing,
                name=section_name,
                content=section,
                wiki=self._wiki_document,
            )
            new_documents.append(new_document)
        return processing

    async def _get_section_names(self) -> List[str]:
        if not self._wiki_document.content:
            return []
        if len(self._wiki_document.content) < getattr(settings, 'DOCUMENT_MAX_LENGTH', 1000):
            return [self._wiki_document.title]
        response = await repeat_until(
            self._ai.prompt,
            (
                f"This is a long document called \"{self._wiki_document.title}\":\n"
                f"```\n"
                f"{self._wiki_document.content.strip()}\n"
                f"```\n\n"
                f"This document needs to be broken down into 2 or more parts.\n"
                f"Consider breaking this text into an optimal number of sections based on meaning.\n"
                f"And create a list of proposed section titles for the document.\n"
                f"Keep the original language.\n"
                f"{json_prompt('split_document_get_names')}"
            ),
            json_format=True,
            condition=lambda resp: 'names' in resp.result and len(resp.result['names']) >= 2 and all(
                get_language(name) == 'ru' for name in resp.result['names']
            )
        )
        return response.result['names']

    async def _get_section(self, names: List[str], section_name: str):
        if len(names) == 1 and section_name == names[0]:
            return self._wiki_document.content
        names_list_str = '\n- '.join(names)
        response = await repeat_until(
            self._ai.prompt,
            (
                f"This is a long document called \"{self._wiki_document.title}\":\n"
                f"```\n"
                f"{self._wiki_document.content.strip()}\n"
                f"```\n\n"
                f"This document needs to be broken into {len(names)} parts:\n"
                f"{names_list_str}\n"
                f"Give the text of the section \"{section_name}\".\n"
                f"The text must match the original maximally in detail (word-for-word).\n"
                f"Keep the original language.\n"
                f"{json_prompt('split_document_get_section', do_escape=True)}"
            ),
            json_format=True,
            condition=lambda resp: 'text' in resp.result and isinstance(resp.result['text'], str) and get_language(resp.result['text']) == 'ru'
        )
        return response.result['text']


async def split_wiki_document(wiki_document: WikiDocument) -> WikiDocumentProcessing:
    return await WikiDocumentSplitter(wiki_document).run()
