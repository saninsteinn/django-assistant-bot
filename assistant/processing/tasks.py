import logging

from asgiref.sync import async_to_sync
from celery import shared_task, chain, group
from django.db import transaction

from assistant.assistant.queue import CeleryQueues
from assistant.processing.documents.processor import process_document
from assistant.processing.wiki import split_wiki_document
from assistant.storage.models import WikiDocument, Document, WikiDocumentProcessing

logger = logging.getLogger(__name__)


@shared_task(
    queue=CeleryQueues.PROCESSING.value,
    acks_late=True,
    autoretry_for=(Exception,),
    reject_on_worker_lost=True,
    max_retries=10,
    default_retry_delay=60
)
def wiki_processing_task(wiki_document_id: int, **kwargs):
    logger.info(f'Wiki Document Processing Task started for id {wiki_document_id}')
    try:
        wiki_document = WikiDocument.objects.get(id=wiki_document_id)
    except WikiDocument.DoesNotExist:
        logger.error(f'Wiki Document with id {wiki_document_id} not found. Task aborted')
        return
    processing: WikiDocumentProcessing = async_to_sync(
        split_wiki_document
    )(wiki_document)
    task_group = group(
        document_processing_task.si(document.id)
        for document in processing.documents.all()
    )
    task_chain = chain(task_group, finalize_document_processing_task.si(processing.id))
    task_chain()
    logger.info(f'Wiki Document Processing Task finished for id {wiki_document_id}')


@shared_task(
    queue=CeleryQueues.PROCESSING.value,
    acks_late=True,
    autoretry_for=(Exception,),
    reject_on_worker_lost=True,
    max_retries=10,
    default_retry_delay=60
)
def document_processing_task(document_id: int, **kwargs):
    logger.info(f'Document Processing Task started for id {document_id}')
    document = Document.objects.get(id=document_id)
    async_to_sync(
        process_document
    )(document)
    logger.info(f'Document Processing Task finished for id {document_id}')


@shared_task(
    queue=CeleryQueues.PROCESSING.value,
    acks_late=True,
    autoretry_for=(Exception,),
    reject_on_worker_lost=True,
    max_retries=10,
    default_retry_delay=60
)
def finalize_document_processing_task(processing_id: int, **kwargs):
    logger.info(f'Finalize Document Processing Task started for id {processing_id}')
    processing = WikiDocumentProcessing.objects.get(id=processing_id)
    with transaction.atomic():
        processing.status = WikiDocumentProcessing.Status.COMPLETED
        processing.save()
        processing.wiki_document.processing.exclude(id=processing_id).delete()
    logger.info(f'Finalize Document Processing Task finished for id {processing_id}')
