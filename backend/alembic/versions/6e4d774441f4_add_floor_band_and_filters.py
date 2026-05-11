"""add_floor_band_and_filters

Revision ID: 6e4d774441f4
Revises: 64562d44a07f
Create Date: 2026-05-11 15:18:00.880251
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = '6e4d774441f4'
down_revision = '64562d44a07f'
branch_labels = None
depends_on = None


def _has_column(table: str, column: str) -> bool:
    """Check if a column already exists to make this migration idempotent."""
    bind = op.get_bind()
    insp = inspect(bind)
    columns = [c['name'] for c in insp.get_columns(table)]
    return column in columns


def upgrade() -> None:
    if not _has_column('property_listings', 'floor_band'):
        op.add_column('property_listings', sa.Column('floor_band', sa.String(50), nullable=True))
    if not _has_column('property_listings', 'price_per_sqft'):
        op.add_column('property_listings', sa.Column('price_per_sqft', sa.Integer(), nullable=True))
    if not _has_column('property_listings', 'landmark'):
        op.add_column('property_listings', sa.Column('landmark', sa.String(255), nullable=True))
    if not _has_column('property_listings', 'is_verified'):
        op.add_column('property_listings', sa.Column('is_verified', sa.Boolean(), nullable=False, server_default=sa.text('false')))


def downgrade() -> None:
    op.drop_column('property_listings', 'is_verified')
    op.drop_column('property_listings', 'landmark')
    op.drop_column('property_listings', 'price_per_sqft')
    op.drop_column('property_listings', 'floor_band')
