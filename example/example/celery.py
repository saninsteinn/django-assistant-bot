import os
from logging.config import dictConfig
from celery import Celery, signals

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'example.settings')

from django.conf import settings

app = Celery('example')
app.config_from_object('django.conf:settings', namespace='CELERY')

app.conf.update(
    broker_connection_retry_on_startup=True,
    worker_concurrency=settings.ENV.int('CELERY_CONCURRENCY', 1),
    task_track_started=True
)


@signals.setup_logging.connect
def on_celery_setup_logging(**kwargs):
    dictConfig(settings.CELERY_LOGGING)


app.autodiscover_tasks()
