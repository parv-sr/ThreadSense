from fastapi import APIRouter, Depends, HTTPException, Header
import os

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_async_engine(DATABASE_URL)
SessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

router = APIRouter()

def verify_admin(x_api_key: str = Header(...)):
    ADMIN_KEY = os.getenv("THREADSENSE_ADMIN_KEY", "160977_p1")
    if not ADMIN_KEY or x_api_key != ADMIN_KEY:
        raise HTTPException(status_code=403, detail="Forbidden")
    
async def get_db():
    async with SessionLocal() as session:
        yield session

@router.post("/truncate-db")
async def truncate_db(db: AsyncSession = Depends(get_db), verify = Depends(verify_admin)):
    try:
        await db.execute(
            text("TRUNCATE TABLE raw_files, raw_message_chunks, listing_chunks, property_listings RESTART IDENTITY CASCADE;")
        )
        await db.commit()
        return {"status" : "success"}
    except Exception as e:
        print(f"Error while truncating RDB: {e}")
        raise HTTPException(status_code=500, detail="Error")
