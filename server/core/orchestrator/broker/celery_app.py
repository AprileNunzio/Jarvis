import os
from celery import Celery

REDIS_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")

# Inizializza l'app Celery per i task asincroni
celery_app = Celery(
    "jarvis_tasks",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=['server.core.orchestrator.broker.tasks']
)

celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='Europe/Rome',
    enable_utc=True,
)
