from django.conf import settings

from assistant.ai.dialog import AIDialog
from assistant.processing.documents.steps.base import DocumentProcessingStep
from assistant.processing.utils import json_prompt
from assistant.utils.language import get_language
from assistant.utils.repeat_until import repeat_until


class DocumentFormatStep(DocumentProcessingStep):

    def __init__(self, document):
        super().__init__(document)
        self._ai = AIDialog(
            settings.FORMAT_DOCUMENTS_AI_MODEL
        )

    async def run(self):
        self._logger.info(f"Format document {self._document}")

        content = self._document.content.replace('\t', ' ' * 4).strip()
        response = await repeat_until(
            self._ai.prompt,
            (
                f"This is a raw text of document called \"{self._document.name}\":\n"
                f"```\n"
                f"{content}\n"
                f"```\n\n"
                f"Reformat this text.\n"
                f"Give a text in the best human-readable format. Markdown must be used.\n"
                f"You must not lose any information.\n"
                f"Keep the original meaning fully.\n"
                f"Keep the original language too.\n"
                f"{json_prompt('format_document')}"
            ),
            json_format=True,
            condition=lambda resp: 'text' in resp.result and len(resp.result['text']) >= 2 and get_language(resp.result['text']) == 'ru'
        )
        self._document.content = response.result['text']
