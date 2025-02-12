from django.apps import AppConfig


class ProcessingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'assistant.processing'
    label = 'assistant_processing'

    def ready(self):
        from . import signals
