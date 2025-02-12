from django.db.models.signals import post_save
from django.dispatch import receiver

from assistant.storage.models import WikiDocument
from .tasks import wiki_processing_task


@receiver(post_save, sender=WikiDocument)
def wiki_document_post_save(sender, instance, created, **kwargs):
    wiki_processing_task.delay(instance.id)
