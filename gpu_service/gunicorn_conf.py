import logging
import os
import sys

sys.path.append(os.path.join(os.path.realpath(os.path.dirname(__file__)), '..'))

os.environ["TOKENIZERS_PARALLELISM"] = "false"

workers = int(os.getenv("GPU_SERVICE_WORKERS", 2))
bind = "0.0.0.0:11435"
timeout = 120  # Timeout in seconds
accesslog = os.getenv("GPU_SERVICE_ACCESS_LOG", "access.log")
errorlog = os.getenv("GPU_SERVICE_ERROR_LOG", "error.log")
loglevel = os.getenv("GPU_SERVICE_LOG_LEVEL", "info")
worker_class = "uvicorn.workers.UvicornWorker"
wsgi_app = "main:app"

# Дополнительные настройки для логирования
logger = logging.getLogger("gunicorn.error")
logger.setLevel(logging.DEBUG)

