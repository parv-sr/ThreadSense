"""fastapi-users columns

Revision ID: 64562d44a07f
Revises: c8f3a2d7e901
Create Date: 2026-05-04 07:39:44.057479
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '64562d44a07f'
down_revision = 'c8f3a2d7e901'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('users', sa.Column('is_superuser', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('users', sa.Column('is_verified', sa.Boolean(), nullable=False, server_default='false'))
    
    # Ensure email is in place since we'll use it for fastapi-users (though we already had it in the past)
    # The previous migration c8f3a2d7e901 didn't drop it.


def downgrade() -> None:
    op.drop_column('users', 'is_verified')
    op.drop_column('users', 'is_superuser')
