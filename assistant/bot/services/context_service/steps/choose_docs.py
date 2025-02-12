from typing import List, Optional

from asgiref.sync import sync_to_async
from django.conf import settings
from fuzzywuzzy import process
from assistant.bot.services.context_service.utils import add_system_message
from assistant.bot.services.context_service.steps.base import ContextProcessingStep, ai_debugger
from assistant.bot.services.schema_service import json_prompt
from assistant.storage.models import Document
from assistant.utils.repeat_until import repeat_until


class ChooseDocsStep(ContextProcessingStep):
    """
    Choose the most relevant documents for the user question from the search results.
    """

    debug_info_key = 'choice'

    @ai_debugger
    async def run(self):
        documents = self._state.documents[:10]
        title_choices = await (sync_to_async(
            lambda: self._get_title_choices(documents)
        ))()
        title_choices = title_choices.replace(' / ', '. ')
        doc_titles = await (sync_to_async(
            lambda: [doc.wiki.path.replace(' / ', '. ') for doc in documents]
        ))()

        new_messages = add_system_message(
            self._state.messages,
            (
                f"You can answer the user using information from these documents:\n"
                f"{title_choices}\n"
                f"However, you must choose up to 3 documents from the list above to get details.\n"
                f"Give the rows from the list above that relate to the user's question:\n"
                f"```\n"
                f"{self._state.user_question}\n"
                f"```\n"
                f"Give each selected row in full - EXACTLY as it represented in the list.\n"
                f"Do not hesitate to provide MULTIPLE rows if necessary.\n"
                f"If none of the documents are relevant to the user's question, just provide an empty list.\n"
                f"{json_prompt(['choose_documents'])}"
            )
        )

        chosen_documents = []

        def select_docs(titles):
            nonlocal chosen_documents
            chosen_documents = []
            for title in titles:
                doc = self._select_doc(documents, doc_titles, title)
                chosen_documents.append(doc)
            return chosen_documents

        def check_answer(resp):
            if 'documents' not in resp.result:
                self._logger.warning(f'No documents in response: {resp.result}')
                return False
            if not resp.result['documents']:
                return True

            select_docs(resp.result['documents'])

            if None in chosen_documents:
                self._logger.warning(f'None in selected docs: {chosen_documents}')
                return False

            doc_ids = [doc.id for doc in chosen_documents]
            if len(doc_ids) != len(set(doc_ids)):
                self._logger.warning(f'Duplicate docs selected: {doc_ids}')
                return False

            self._logger.info(f'Selected docs: {resp.result}')

            return True

        if settings.DEBUG:
            log_messages = []
            for message in new_messages:
                log_messages.append(
                    f"\n\n################\n"
                    f"{message['role']}\n"
                    f"################\n"
                    f"{message['content']}"
                )
            self._logger.debug('Messages to AI:\n%s', '\n'.join(log_messages))

        await repeat_until(
            self._fast_ai.get_response, new_messages, max_tokens=256, json_format=True,
            condition=check_answer
        )

        self._debug_info['chosen'] = [f"[{d.id}] {d.name}" for d in chosen_documents]
        self._state.documents = self._state.documents[:2] + chosen_documents
        self._state.documents = list({doc.id: doc for doc in self._state.documents}.values())

        # ai = get_ai_provider('llama3:8b')
        # toc = None
        # path = []
        #
        # def path_str():
        #     return '/'.join([t.title for t in path]) + '/' if path else ''
        #
        # while True:
        #
        #     toc_str = await sync_to_async(get_toc_str)(toc)
        #     new_messages = add_system_message(
        #         messages,
        #         (
        #             f"You can get access to the information about the following topics of `{path_str()}` section:\n"
        #             f"{toc_str}\n\n"
        #             f"You have strictly 2 options:\n"
        #             f"1. Choose the topic from the list above that will help you to ask the user question above.\n"
        #             f"2. If you don't see the topic you need, "
        #             f"provide the search query optimized for embeddings algorithm "
        #             f"that will help you to find the necessary document.\n\n"
        #             f"{json_prompt(['topic', 'search'])}"
        #         )
        #     )
        #     response = await repeat_until(
        #         ai.get_response, new_messages, max_tokens=256, json_format=True,
        #         condition=lambda resp: bool(resp.result.get('topic')) or bool(resp.result.get('search'))
        #     )
        #     if 'search' in response.result:
        #         search = response.result.get('search')
        #         logger.debug(f'Search query: {search}')
        #         documents = await embedding_search(search, top_n=3)
        #         break
        #     elif 'topic' in response.result:
        #         topic = response.result.get('topic')
        #         logger.debug(f'Topic selected: {topic}')
        #
        #         toc = await sync_to_async(
        #             select_child
        #         )(toc, topic)
        #
        #         logger.info(f'TOC selected: {toc.title}')
        #
        #         if hasattr(toc, 'document'):
        #             logger.info(f'Document selected: {path_str()}')
        #             documents = [toc.document]
        #             break
        #         else:
        #             path.append(toc)
        #
        # new_messages = add_system_message(
        #     messages,
        #     (
        #         f"You can answer to the user using the following information from those documents:\n"
        #         ''.join(
        #             f"`# {path_str()}/{document.name}`\n"
        #             f"```\n"
        #             f"{document.content}\n"
        #             f"```\n"
        #             for document in documents
        #         )
        #     )
        # )
        # return new_messages

    def _get_title_choices(self, documents: List[Document], by_numbers=False) -> str:
        """
        Get the title choices for the documents.
        """
        titles = []
        for i, document in enumerate(documents):
            title = document.wiki.path
            if title not in titles:
                if by_numbers:
                    titles.append(f'{i + 1}. {title}')
                else:
                    titles.append(f'- {title}')
        return '\n'.join(titles)

    def _select_doc(self, documents: List[Document], titles: List[str], title: str) -> Optional[Document]:
        """
        Selects the child with the given title.
        """
        children = {
            title: doc
            for doc, title in zip(documents, titles)
        }

        matches = process.extractBests(title, children.keys())
        matches.sort(key=lambda x: x[1], reverse=True)

        score = matches[0][1]
        if score < 90:
            return

        self._logger.info(f'Matches: {matches}')

        best_title = matches[0][0]
        best_child = children[best_title]

        return best_child
