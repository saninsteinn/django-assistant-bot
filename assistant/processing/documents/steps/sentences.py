import logging
import re
from typing import List

from asgiref.sync import sync_to_async
from django.conf import settings

from assistant.ai.dialog import AIDialog
from assistant.processing.documents.steps.base import DocumentProcessingStep
from assistant.processing.utils import split_text_by_parts
from assistant.storage.models import Document, Sentence
from assistant.utils.language import get_language
from assistant.utils.repeat_until import repeat_until


logger = logging.getLogger(__name__)


class ExtractSentencesStep(DocumentProcessingStep):

    def __init__(self, document: Document):
        super().__init__(document)
        self._ai = AIDialog(
            settings.SENTENCES_AI_MODEL
        )

    async def run(self):
        self._logger.info(f"Extract sentences for document {self._document}")

        doc_path = await (sync_to_async(lambda: self._document.wiki.path))()
        text = (
            f"# {doc_path}\n\n"
            # f"{document.description}\n\n"
            f"{self._document.content}\n"
        )

        sentences = []
        i = 0
        for part in split_text_by_parts(text, 500):
            part_sentences = await split_text_to_sentences(
                part,
                self._ai
            )
            sentences.extend([
                Sentence(
                    document=self._document,
                    text=sentence,
                    order=i
                )
                for sentence in part_sentences
            ])

        await (sync_to_async(
            lambda: Sentence.objects.bulk_create(sentences)
        ))()


async def split_text_to_sentences(text: str, ai: AIDialog) -> List[str]:
    """
    Split the document into sentences using AI.
    """
    prompt = (
        f"Break down the following text into meaningful sentences to facilitate the creation of embeddings for search optimization:\n"
        f"```\n"
        f"{text.strip()}\n"
        f"```\n"
        f"The total length of the sentences must not be less than the length of the document. Do not miss anything."
        f"You must clear any excess formatting or symbols. But keep the natural punctuation as if the sentence is independent.\n"
        f"You must also use the original DOCUMENT LANGUAGE in the answer.\n"
        f"Answer with a JSON response that strictly matches the following example:\n"
        f"```json\n"
        f"{{\n"
        f"  \"sentences\": [\n"
        f"    \"The first sentence of the text.\",\n"
        f"    \"The second sentence of the text.\",\n"
        f"    ...\n"
        f"  ]\n"
        f"}}\n"
        f"```\n"
    )

    def check_response(resp):
        if 'sentences' not in resp.result:
            logger.warning(f'Sentences not found in response: {resp}')
            return False

        sentences = resp.result['sentences']
        if not all(isinstance(part, str) for part in sentences):
            logger.warning(f'Invalid sentences: {sentences}')
            return False

        total_length = sum(len(part) for part in sentences)
        estimated_total_length = _calculate_estimated_total_length(text)

        if total_length < estimated_total_length:
            logger.warning(f'Invalid sentences length: {total_length} / {estimated_total_length}')
            return False

        if not all(get_language(part) == 'ru' for part in sentences):
            logger.warning(f'Invalid sentences language: {[get_language(part) == "ru" for part in sentences]}')
            return False

        return True

    response = await repeat_until(
        ai.prompt, prompt, json_format=True,
        condition=check_response
    )

    parts = response.result['sentences']
    parts = [part.strip() for part in parts]
    parts = [part for part in parts if part]
    return parts


def _calculate_estimated_total_length(text: str) -> int:
    words_count = len(re.findall(r'\w+', text))
    estimated_total_length = min(words_count * 5, int(len(text.strip()) * 0.8))
    return estimated_total_length



# def split_text_to_sentences(text: str) -> List[str]:
#     # Regular expression to split text into sentences
#     sentence_endings = re.compile(r'(?<!\w\.\w.)(?<![A-Z][a-z]\.)(?<=\.|\?|\!)\s')
#     sentences = sentence_endings.split(text)
#     return [sentence.strip() for sentence in sentences]
