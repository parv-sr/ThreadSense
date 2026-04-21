from fastapi import APIRouter
from typing import Any

router = APIRouter()

@router.get("/fetch_progress")
def fetch_progress() -> Any:
    pass