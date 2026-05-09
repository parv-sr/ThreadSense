"""add last_heartbeat_at to raw_files

Revision ID: a3c7e9f21b04
Revises: f4a042ad1a0f
Create Date: 2026-04-23 12:50:00.000000+05:30
"""

from alembic import op
import sqlalchemy as sa

revision = 'a3c7e9f21b04'
down_revision = 'f4a042ad1a0f'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'raw_files',
        sa.Column('last_heartbeat_at', sa.DateTime(timezone=True), nullable=True)
    )
    op.create_index(
        'ix_raw_files_last_heartbeat_at',
        'raw_files',
        ['last_heartbeat_at'],
        unique=False
    )


def downgrade() -> None:
    op.drop_index('ix_raw_files_last_heartbeat_at', table_name='raw_files')
    op.drop_column('raw_files', 'last_heartbeat_at')
