from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from taskiq_redis import ListQueueBroker, RedisAsyncResultBackend

from backend.src.core.config import get_settings

settings = get_settings()


def _with_redis_health_check(url: str, interval: int = 30) -> str:
    parsed = urlparse(url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query.setdefault("health_check_interval", str(interval))
    return urlunparse(parsed._replace(query=urlencode(query)))


broker = ListQueueBroker(url=_with_redis_health_check(settings.redis_url)).with_result_backend(
    RedisAsyncResultBackend(
        redis_url=_with_redis_health_check(settings.redis_broker_url),
        result_ex_time=settings.taskiq_result_ttl_seconds,
    )
)

# Ensure task registration side-effect on import.
from backend.src.tasks import ingestion as _ingestion  # noqa: F401,E402
from backend.src.preprocessing import tasks as _preprocessing_tasks  # noqa: F401,E402
from backend.src.embeddings import tasks as _embedding_tasks  # noqa: F401,E402
