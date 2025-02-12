from itertools import chain

from asgiref.sync import sync_to_async
from assistant.bot.services.context_service.steps.base import ContextProcessingStep, time_debugger
from assistant.storage.models import Question, Document, WikiDocumentProcessing
from assistant.rag.services.search_service import embedding_search, embedding_search_questions, \
    get_embedding
from assistant.utils.debug import TimeDebugger


class EmbeddingsStep(ContextProcessingStep):
    """
    Get embeddings for the user question.
    """

    debug_info_key = 'embedding_search'
    debugger_class = TimeDebugger

    @time_debugger
    async def run(self):
        search_query = self._state.user_question
        self._logger.debug(f'Search query: {search_query}')

        query_embedding = await get_embedding(search_query)

        qs = Question.objects.filter(
            document__wiki__bot=self._bot,
            document__wiki__processing__status=WikiDocumentProcessing.Status.COMPLETED
        )
        questions = list(await embedding_search_questions(query_embedding, qs, n=5))

        self._state.related_questions = questions
        self._debug_info['related_questions'] = [
            f"[{q.id} {1 - q.distance}] {q.text}" for q in questions[:5]
        ]

        # documents_q_prec = await embedding_search(search_query, max_scores_n=1, top_n=5, field='questions')  #, root=self._state.topic)

        if questions and questions[0].distance < 0.05:
            self._debug_info['the_same_question'] = questions[0].text
            documents = [
                await sync_to_async(
                    lambda: (Document.objects.get(id=questions[0].document_id), 1 - questions[0].distance)
                )()
            ]
        else:
            documents_q_broad = await embedding_search(search_query, qs, max_scores_n=5, top_n=5)  #, root=self._state.topic)
            # documents_s_prec = await embedding_search(search_query, max_scores_n=1, top_n=5, field='sentences', root=root)
            # documents_s_broad = await embedding_search(search_query, max_scores_n=5, top_n=5, field='sentences', root=root)

            documents = list(chain(*zip(
                # documents_q_prec,
                # documents_s_prec,
                documents_q_broad,
                # documents_s_broad
            )))

        await sync_to_async(self._log_scores)(documents)

        # uniq by doc.id
        documents = list({doc[0].id: doc for doc in documents}.values())

        self._debug_info['documents'] = [f"[{d[0].id} {d[1]}] {d[0].name}" for d in documents]

        documents = [doc[0] for doc in documents]
        self._state.documents = documents

    def _log_scores(self, docs):
        self._logger.debug(
            f'Embedding search results:\n'
            + (
                f'\n'.join(
                    f'{doc[0].id} {doc[1]} {doc[0].wiki.path}'
                    for doc in docs
                )
            )
        )
