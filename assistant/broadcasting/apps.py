from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class BroadcastingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'assistant.broadcasting'
    verbose_name = _("Broadcasting")

    def ready(self):
        # Import signals here to ensure they are connected when the app loads.
        import assistant.broadcasting.signals  # noqa: F401 - Needs to be imported to connect signals
