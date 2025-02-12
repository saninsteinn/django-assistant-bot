import logging
from collections import defaultdict
from typing import List, Tuple

import numpy as np
from asgiref.sync import sync_to_async
from django.conf import settings
from django.db.models import QuerySet
from pgvector.django import CosineDistance

from assistant.ai.services.ai_service import get_ai_embdedder
from assistant.storage.models import Document, Sentence, Question, BaseEmbeddingModel, WikiDocument

logger = logging.getLogger(__name__)


def cosine_similarity(a, b):
    dot_product = np.dot(a, b)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    return dot_product / (norm_a * norm_b)

# def cosine_similarity(a, b):
#     a = np.squeeze(a)  # Удалить лишние измерения, если они есть
#     b = np.squeeze(b)  # Удалить лишние измерения, если они есть
#     dot_product = np.dot(a, b)
#     norm_a = np.linalg.norm(a)
#     norm_b = np.linalg.norm(b)
#     return dot_product / (norm_a * norm_b)


def embeddings_similarity(a: List[float], b: List[float]) -> float:
    a = np.array(a)
    b = np.array(b)
    return cosine_similarity(a, b)


async def embedding_search_old(
        query: str,
        max_scores_n: int = 10,
        top_n: int = 10,
        field: str = 'sentences',
        root: WikiDocument = None,
) -> List[Tuple[dict, float]]:

    logger.info(f'Embedding search for query: {query}')

    model = settings.EMBEDDING_AI_MODEL
    embedder = get_ai_embdedder(model)

    query_embedding = (await embedder.embeddings([query]))[0]

    # Получение всех эмбеддингов из базы данных
    filter_kwargs = {
        f'{field}_embeddings__has_key': model,
    }
    if root is not None:
        wiki_ids = root.get_descendants(include_self=True).values_list('id', flat=True)
        filter_kwargs['wiki_id__in'] = wiki_ids
    embeddings = await (sync_to_async(
        lambda: list(Document.objects.filter(
            **filter_kwargs
        ).values('id', f'{field}_embeddings'))
    ))()

    # Преобразование эмбеддингов в numpy массивы для вычислений
    ids, db_embeddings = [], []
    for item in embeddings:
        item_embeddings = item[f'{field}_embeddings'][model]
        for sentence_embedding in item_embeddings:
            ids.append(item['id'])
            db_embeddings.append(np.array(
                sentence_embedding
            ))

    query_embedding = np.array(query_embedding)

    # Вычисление косинусного сходства между эмбеддингом запроса и эмбеддингами в базе данных
    similarities = [cosine_similarity(query_embedding, db_emb) for db_emb in db_embeddings]

    # Сортировка результатов по сходству
    sorted_indices = np.argsort(similarities)[::-1]

    results = [(ids[i], similarities[i]) for i in sorted_indices]

    result_doc_ids = defaultdict(list)
    for r in results:
        result_doc_ids[r[0]].append(r[1])

    def score(scores):
        return sum(scores[:max_scores_n]) / min(max_scores_n, len(scores))

    documents = {
        d.id: d
        for d in await (sync_to_async(
            lambda: list(Document.objects.filter(id__in=list(result_doc_ids.keys())))
        ))()
    }

    result = [
        (documents[did], score(scores))
        for did, scores in result_doc_ids.items()
    ]

    result.sort(key=lambda x: x[1], reverse=True)
    result = result[:top_n]

    return result


async def embedding_search(
        query: str,
        qs: QuerySet,
        max_scores_n: int = 10,
        top_n: int = 10,
) -> List[Tuple[dict, float]]:

    logger.info(f'Embedding search for query: {query}')

    filter_kwargs = {
    }

    embedding_qs = qs.filter(
        **filter_kwargs
    )

    query_embedding = await get_embedding(query)

    top_objects = await _objects_embedding_search(
        query_embedding, embedding_qs, n=max_scores_n * top_n * 10
    )

    docs = defaultdict(list)
    for obj in top_objects:
        docs[obj.document_id].append(obj)

    doc_scores = {
        doc_id: 1 - sum([o.distance for o in v[:max_scores_n]]) / max_scores_n
        for doc_id, v in docs.items() if len(v) >= max_scores_n
    }

    result = [
        (d, doc_scores[d.id])
        for d in await (sync_to_async(
            lambda: list(Document.objects.filter(id__in=list(doc_scores.keys())))
        ))()
    ]

    result.sort(key=lambda x: x[1], reverse=True)
    result = result[:top_n]

    return result


async def get_embedding(text: str) -> List[float]:
    model = settings.EMBEDDING_AI_MODEL
    embedder = get_ai_embdedder(model)
    return (await embedder.embeddings([text]))[0]


async def embedding_search_documents(
        query_embedding: List[float],
        qs: QuerySet,
        n: int = 10
) -> List[Document]:
    return await _objects_embedding_search(query_embedding, qs, n, field='content_embedding')


async def embedding_search_questions(
        query_embedding: List[float],
        qs: QuerySet,
        n: int = 10
) -> List[Question]:
    return await _objects_embedding_search(query_embedding, qs, n)


async def embedding_search_sentences(
        query_embedding: List[float],
        qs: QuerySet,
        n: int = 10
) -> List[Sentence]:
    return await _objects_embedding_search(query_embedding, qs, n)


async def _objects_embedding_search(
        query_embedding: List[float],
        qs: QuerySet,
        n: int = 10,
        field: str = 'embedding',
) -> List[BaseEmbeddingModel]:
    top_objects = await (sync_to_async(
        lambda: list(qs.annotate(
            distance=CosineDistance(field, query_embedding)
        ).order_by('distance')[:n])
    ))()
    return top_objects
