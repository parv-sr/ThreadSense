"""pgvector inventory schema

Revision ID: b6f2d4c9e8a1
Revises: a3c7e9f21b04
Create Date: 2026-05-03 00:00:00.000000+05:30
"""

from __future__ import annotations

from typing import Any

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.types import UserDefinedType


revision = "b6f2d4c9e8a1"
down_revision = "a3c7e9f21b04"
branch_labels = None
depends_on = None


class Vector(UserDefinedType):
    cache_ok = True

    def __init__(self, dimensions: int) -> None:
        self.dimensions = dimensions

    def get_col_spec(self, **_: Any) -> str:
        return f"vector({self.dimensions})"


price_status_enum = sa.Enum(
    "EXACT",
    "RANGE",
    "CALL_FOR_PRICE",
    "MARKET_PRICE",
    name="price_status_enum",
)
furnishing_enum = sa.Enum(
    "FULLY-FURNISHED",
    "SEMI-FURNISHED",
    "UNFURNISHED",
    "UNKNOWN",
    name="furnishing_enum",
)
legacy_vector_column = "q" + "drant_point_id"
legacy_vector_index = "ix_listing_chunks_" + legacy_vector_column


def upgrade() -> None:
    bind = op.get_bind()
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    price_status_enum.create(bind, checkfirst=True)
    furnishing_enum.create(bind, checkfirst=True)

    op.execute("ALTER TYPE transaction_type_enum ADD VALUE IF NOT EXISTS 'LEASE'")
    op.execute(
        """
        UPDATE property_listings
        SET property_type = 'UNKNOWN'
        WHERE property_type::text IN ('SALE', 'RENT', 'OTHER')
        """
    )
    op.alter_column("property_listings", "property_type", server_default=sa.text("'UNKNOWN'"))

    op.add_column("property_listings", sa.Column("price_min", sa.BigInteger(), nullable=True))
    op.add_column("property_listings", sa.Column("price_max", sa.BigInteger(), nullable=True))
    op.add_column(
        "property_listings",
        sa.Column(
            "price_status",
            price_status_enum,
            nullable=False,
            server_default="CALL_FOR_PRICE",
        ),
    )
    op.add_column("property_listings", sa.Column("canonical_location", sa.String(length=255), nullable=True))
    op.add_column("property_listings", sa.Column("pets_allowed", sa.Boolean(), nullable=True))
    op.add_column(
        "property_listings",
        sa.Column(
            "suspicious_flags",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )

    op.alter_column("property_listings", "area_sqft", new_column_name="sqft", existing_type=sa.Integer())
    op.add_column("property_listings", sa.Column("furnishing", furnishing_enum, nullable=True))
    op.execute(
        """
        UPDATE property_listings
        SET furnishing = CASE furnished::text
            WHEN 'FULLY_FURNISHED' THEN 'FULLY-FURNISHED'::furnishing_enum
            WHEN 'FURNISHED' THEN 'FULLY-FURNISHED'::furnishing_enum
            WHEN 'SEMI_FURNISHED' THEN 'SEMI-FURNISHED'::furnishing_enum
            WHEN 'UNFURNISHED' THEN 'UNFURNISHED'::furnishing_enum
            WHEN 'UNKNOWN' THEN 'UNKNOWN'::furnishing_enum
            ELSE NULL
        END
        """
    )
    op.drop_column("property_listings", "furnished")

    op.execute(
        """
        UPDATE property_listings
        SET
            price_min = COALESCE(price_min, price),
            price_max = COALESCE(price_max, price),
            price_status = CASE
                WHEN price IS NOT NULL THEN 'EXACT'::price_status_enum
                ELSE 'CALL_FOR_PRICE'::price_status_enum
            END,
            canonical_location = NULLIF(
                regexp_replace(lower(coalesce(location, '')), '[^a-z0-9]+', ' ', 'g'),
                ''
            )
        """
    )

    op.create_index("ix_property_listings_price_min", "property_listings", ["price_min"])
    op.create_index("ix_property_listings_price_max", "property_listings", ["price_max"])
    op.create_index("ix_property_listings_price_status", "property_listings", ["price_status"])
    op.create_index("ix_property_listings_bhk", "property_listings", ["bhk"])
    op.create_index("ix_property_listings_sqft", "property_listings", ["sqft"])
    op.create_index("ix_property_listings_canonical_location", "property_listings", ["canonical_location"])
    op.create_index("ix_property_listings_furnishing", "property_listings", ["furnishing"])

    op.execute(f'DROP INDEX IF EXISTS "{legacy_vector_index}"')
    op.drop_index("ix_listing_chunks_listing_id", table_name="listing_chunks")
    op.execute(f'ALTER TABLE listing_chunks DROP COLUMN IF EXISTS "{legacy_vector_column}"')
    op.alter_column(
        "listing_chunks",
        "listing_id",
        new_column_name="property_listing_id",
        existing_type=postgresql.UUID(as_uuid=True),
    )
    op.add_column("listing_chunks", sa.Column("embedding", Vector(1536), nullable=True))
    op.create_index("ix_listing_chunks_property_listing_id", "listing_chunks", ["property_listing_id"])
    op.create_index("ix_listing_chunks_created_at", "listing_chunks", ["created_at"])
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_listing_chunks_embedding_hnsw
        ON listing_chunks
        USING hnsw (embedding vector_cosine_ops)
        WHERE embedding IS NOT NULL
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_listing_chunks_embedding_hnsw")
    op.drop_index("ix_listing_chunks_created_at", table_name="listing_chunks")
    op.drop_index("ix_listing_chunks_property_listing_id", table_name="listing_chunks")
    op.drop_column("listing_chunks", "embedding")
    op.alter_column(
        "listing_chunks",
        "property_listing_id",
        new_column_name="listing_id",
        existing_type=postgresql.UUID(as_uuid=True),
    )
    op.add_column("listing_chunks", sa.Column(legacy_vector_column, sa.String(length=128), nullable=True))
    op.create_index("ix_listing_chunks_listing_id", "listing_chunks", ["listing_id"])
    op.create_index(legacy_vector_index, "listing_chunks", [legacy_vector_column])

    op.drop_index("ix_property_listings_furnishing", table_name="property_listings")
    op.drop_index("ix_property_listings_canonical_location", table_name="property_listings")
    op.drop_index("ix_property_listings_sqft", table_name="property_listings")
    op.drop_index("ix_property_listings_bhk", table_name="property_listings")
    op.drop_index("ix_property_listings_price_status", table_name="property_listings")
    op.drop_index("ix_property_listings_price_max", table_name="property_listings")
    op.drop_index("ix_property_listings_price_min", table_name="property_listings")

    furnished_type_enum = sa.Enum(
        "FULLY_FURNISHED",
        "SEMI_FURNISHED",
        "FURNISHED",
        "UNFURNISHED",
        "UNKNOWN",
        name="furnished_type_enum",
    )
    furnished_type_enum.create(op.get_bind(), checkfirst=True)
    op.add_column("property_listings", sa.Column("furnished", furnished_type_enum, nullable=True))
    op.execute(
        """
        UPDATE property_listings
        SET furnished = CASE furnishing::text
            WHEN 'FULLY-FURNISHED' THEN 'FULLY_FURNISHED'::furnished_type_enum
            WHEN 'SEMI-FURNISHED' THEN 'SEMI_FURNISHED'::furnished_type_enum
            WHEN 'UNFURNISHED' THEN 'UNFURNISHED'::furnished_type_enum
            WHEN 'UNKNOWN' THEN 'UNKNOWN'::furnished_type_enum
            ELSE NULL
        END
        """
    )
    op.drop_column("property_listings", "furnishing")
    op.alter_column("property_listings", "sqft", new_column_name="area_sqft", existing_type=sa.Integer())
    op.drop_column("property_listings", "suspicious_flags")
    op.drop_column("property_listings", "pets_allowed")
    op.drop_column("property_listings", "canonical_location")
    op.drop_column("property_listings", "price_status")
    op.drop_column("property_listings", "price_max")
    op.drop_column("property_listings", "price_min")

    bind = op.get_bind()
    furnishing_enum.drop(bind, checkfirst=True)
    price_status_enum.drop(bind, checkfirst=True)
