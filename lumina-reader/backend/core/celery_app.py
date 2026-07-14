from celery import Celery
from core.config import settings

# Handle in-memory mode for local development without Redis
broker_url = settings.REDIS_URL
result_backend = settings.REDIS_URL

if settings.REDIS_URL == "memory://":
    broker_url = "memory://"
    result_backend = "cache+memory://"

celery_app = Celery(
    "lumina_worker",
    broker=broker_url,
    backend=result_backend
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)

# Import tasks so they are registered
import tasks
