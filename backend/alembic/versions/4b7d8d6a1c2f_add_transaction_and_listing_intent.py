"""add transaction_type and listing_intent to property_listings

Revision ID: 4b7d8d6a1c2f
Revises: e9d2fb0a4fe1
Create Date: 2026-04-19 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "4b7d8d6a1c2f"
down_revision: str | None = "e9d2fb0a4fe1"
branch_labels: str | None = None
depends_on: str | None = None


transaction_type_enum = sa.Enum("RENT", "SALE", "UNKNOWN", name="transaction_type_enum")
listing_intent_enum = sa.Enum("OFFER", "REQUEST", "UNKNOWN", name="listing_intent_enum")


def upgrade() -> None:
    bind = op.get_bind()
    transaction_type_enum.create(bind, checkfirst=True)
    listing_intent_enum.create(bind, checkfirst=True)

    op.add_column(
        "property_listings",
        sa.Column(
            "transaction_type",
            transaction_type_enum,
            nullable=False,
            server_default=sa.text("'UNKNOWN'"),
        ),
    )
    op.add_column(
        "property_listings",
        sa.Column(
            "listing_intent",
            listing_intent_enum,
            nullable=False,
            server_default=sa.text("'UNKNOWN'"),
        ),
    )
    op.create_index(
        "ix_property_listings_transaction_type",
        "property_listings",
        ["transaction_type"],
        unique=False,
    )
    op.create_index(
        "ix_property_listings_listing_intent",
        "property_listings",
        ["listing_intent"],
        unique=False,
    )

    op.alter_column("property_listings", "transaction_type", server_default=None)
    op.alter_column("property_listings", "listing_intent", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_property_listings_listing_intent", table_name="property_listings")
    op.drop_index("ix_property_listings_transaction_type", table_name="property_listings")
    op.drop_column("property_listings", "listing_intent")
    op.drop_column("property_listings", "transaction_type")

    bind = op.get_bind()
    listing_intent_enum.drop(bind, checkfirst=True)
    transaction_type_enum.drop(bind, checkfirst=True)
