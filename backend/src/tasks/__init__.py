from __future__ import annotations

import asyncio
import sys
from types import SimpleNamespace
from typing import Any, Awaitable, Callable, TypeVar
from uuid import uuid4

from backend.src.core.config import get_settings

settings = get_settings()

try:
    from celery import Celery
except ModuleNotFoundError:  # pragma: no cover - local fallback before dependencies are installed.
    class Celery:  # type: ignore[no-redef]
        def __init__(self, *_: Any, **__: Any) -> None:
            self.conf = SimpleNamespace(update=lambda **___: None)

        def task(self, *_: Any, **__: Any):
            def decorator(func: Callable[..., Any]):
                func.delay = lambda *args, **kwargs: SimpleNamespace(id=str(uuid4()))  # type: ignore[attr-defined]
                return func

            return decorator


if __name__ == "src.tasks":
    sys.modules.setdefault("backend.src.tasks", sys.modules[__name__])

app = Celery(
    "threadsense",
    broker=settings.redis_broker_url,
    backend=settings.redis_broker_url,
)
app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    result_expires=settings.celery_result_ttl_seconds,
)

T = TypeVar("T")
AsyncFunc = Callable[..., Awaitable[T]]


class TaskHandle:
    def __init__(self, celery_task: Callable[..., Any], async_func: AsyncFunc[Any]) -> None:
        self._celery_task = celery_task
        self._async_func = async_func
        self.__name__ = async_func.__name__
        self.__doc__ = async_func.__doc__

    async def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return await self._async_func(*args, **kwargs)

    async def kiq(self, *args: Any, **kwargs: Any) -> SimpleNamespace:
        result = self._celery_task.delay(*args, **kwargs)
        return SimpleNamespace(task_id=result.id)

    def delay(self, *args: Any, **kwargs: Any) -> Any:
        return self._celery_task.delay(*args, **kwargs)


class CeleryCompatBroker:
    def task(self, func: AsyncFunc[Any] | None = None, **options: Any):
        def decorator(async_func: AsyncFunc[Any]) -> TaskHandle:
            retry_on_error = bool(options.get("retry_on_error", False))
            max_retries = int(options.get("max_retries", 0) or 0)
            # Normalise module path so the task name is identical regardless
            # of whether the module was loaded as "src.tasks.…" (worker via
            # celery -A src.tasks) or "backend.src.tasks.…" (API via uvicorn).
            module = async_func.__module__
            if not module.startswith("backend."):
                module = f"backend.{module}"
            task_name = f"{module}.{async_func.__name__}"

            task_options: dict[str, Any] = {"name": task_name}
            if retry_on_error:
                task_options.update(
                    {
                        "autoretry_for": (Exception,),
                        "retry_backoff": True,
                        "retry_kwargs": {"max_retries": max_retries},
                    }
                )

            @app.task(**task_options)
            def run_async_task(*args: Any, **kwargs: Any) -> Any:
                return asyncio.run(async_func(*args, **kwargs))

            return TaskHandle(run_async_task, async_func)

        if func is not None:
            return decorator(func)
        return decorator

    async def startup(self) -> None:
        return None

    async def shutdown(self) -> None:
        return None


broker = CeleryCompatBroker()

from backend.src.tasks import ingestion as _ingestion  # noqa: E402,F401
from backend.src.tasks import extraction as _extraction  # noqa: E402,F401
from backend.src.preprocessing import tasks as _preprocessing_tasks  # noqa: E402,F401
from backend.src.embeddings import tasks as _embedding_tasks  # noqa: E402,F401
