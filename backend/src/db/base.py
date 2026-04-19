from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    """Base class for all models."""
    pass

def import_all_models() -> None:
    """Import all model modules so SQLAlchemy metadata is fully registered."""
    from backend.src.models.ingestion import (  # noqa: F401
        FileProcess,
        RawFile,
        RawMessageChunk,
    )
    from backend.src.models.preprocessing import (  # noqa: F401
        ListingChunk,
        PropertyListing,
    )
    from backend.src.models.users import User # noqa: F401
