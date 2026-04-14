worker:
	uv run taskiq worker backend.src.tasks:broker --workers 4 --max-async-tasks 100
api:
	uvicorn backend.src.main:app --reload