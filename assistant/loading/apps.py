from django.apps import AppConfig


class LoadingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'assistant.loading'
    label = 'assistant_loading'