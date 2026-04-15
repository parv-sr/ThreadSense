from __future__ import annotations

import argparse

from sqlalchemy import delete, func, select

from backend.src.db.session import AsyncSessionLocal
from backend.src.models.preprocessing import ListingStatus, PropertyListing, PropertyType


def _build_placeholder_filter():
    return (
        PropertyListing.status == ListingStatus.FAILED,
        PropertyListing.property_type == PropertyType.OTHER,
        PropertyListing.bhk.is_(None),
        PropertyListing.price.is_(None),
        PropertyListing.location.is_(None),
        PropertyListing.contact_number.is_(None),
        PropertyListing.furnished.is_(None),
        PropertyListing.floor_number.is_(None),
        PropertyListing.total_floors.is_(None),
        PropertyListing.area_sqft.is_(None),
        PropertyListing.landmark.is_(None),
        PropertyListing.confidence_score == 0.0,
    )


async def run_cleanup(*, dry_run: bool) -> None:
    async with AsyncSessionLocal() as session:
        count_stmt = select(func.count(PropertyListing.id)).where(*_build_placeholder_filter())
        affected = (await session.execute(count_stmt)).scalar_one()
        print(f"placeholder_failed_rows={affected}")

        if dry_run or affected == 0:
            await session.rollback()
            return

        await session.execute(delete(PropertyListing).where(*_build_placeholder_filter()))
        await session.commit()
        print("cleanup_complete=true")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Remove failed placeholder listings with null extraction fields.")
    parser.add_argument("--dry-run", action="store_true", help="Only print matching row count.")
    return parser.parse_args()


if __name__ == "__main__":
    import asyncio

    args = parse_args()
    asyncio.run(run_cleanup(dry_run=args.dry_run))
