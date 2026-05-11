worker:
	celery -A backend.src.tasks worker --loglevel=info --concurrency=10
api:
	uvicorn backend.src.main:app --reload