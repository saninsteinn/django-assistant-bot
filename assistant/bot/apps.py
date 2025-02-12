from django.apps import AppConfig


class BotConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'assistant.bot'
    label = 'assistant_bot'

    def ready(self):
        from . import signals
