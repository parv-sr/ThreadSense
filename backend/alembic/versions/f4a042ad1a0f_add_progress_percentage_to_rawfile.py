"""Add progress_percentage to RawFile

Revision ID: f4a042ad1a0f
Revises: 4b7d8d6a1c2f
Create Date: 2026-04-21 12:09:05.351916
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f4a042ad1a0f'
down_revision = '4b7d8d6a1c2f'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('raw_files', sa.Column('progress_percentage', sa.Integer(), nullable=False, server_default='0'))


def downgrade() -> None:
    op.drop_column('raw_files', 'progress_percentage')
