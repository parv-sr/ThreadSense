from __future__ import annotations

from taskiq_redis import ListQueueBroker, RedisAsyncResultBackend

from backend.src.core.config import get_settings

settings = get_settings()

broker = ListQueueBroker(url=settings.redis_broker_url).with_result_backend(
    RedisAsyncResultBackend(redis_url=settings.redis_broker_url, result_ex_time=settings.taskiq_result_ttl_seconds)
)

# Ensure task registration side-effect on import.
from backend.src.tasks import ingestion as _ingestion  # noqa: F401,E402
from backend.src.preprocessing import tasks as _preprocessing_tasks  # noqa: F401,E402
from backend.src.embeddings import tasks as _embedding_tasks  # noqa: F401,E402
