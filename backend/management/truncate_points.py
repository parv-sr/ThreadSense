import os
from fastapi import Header, HTTPException, APIRouter, Depends
from backend.src.embeddings.service import EmbeddingService
from functools import lru_cache

router = APIRouter(prefix="/admin")

def verify_admin(x_api_key: str = Header(...)):
    ADMIN_KEY = os.getenv("THREADSENSE_ADMIN_KEY", "160977_p1")
    if not ADMIN_KEY or x_api_key != ADMIN_KEY:
        raise HTTPException(status_code=403, detail="Forbidden")
    
#Cache disabled for internal testing.
#@lru_cache    
def get_embedding_service() -> EmbeddingService:
    return EmbeddingService()

    
@router.post('/truncate-vectors')
async def truncate_points(dep = Depends(verify_admin), service: EmbeddingService = Depends(get_embedding_service)):
    try:
        await service.truncate_all_points()
        return {
        "status" : "success"
    }
    except Exception as e:
        print(f"Error while truncating: {e}")
        raise HTTPException(status_code=500, detail="Truncate failed")

