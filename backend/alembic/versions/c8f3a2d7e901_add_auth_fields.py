"""add auth fields to users table

Revision ID: c8f3a2d7e901
Revises: b6f2d4c9e8a1
Create Date: 2026-05-04 10:00:00.000000+05:30
"""

from alembic import op
import sqlalchemy as sa

revision = 'c8f3a2d7e901'
down_revision = 'b6f2d4c9e8a1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add username column — backfill from email, then make NOT NULL
    op.add_column(
        'users',
        sa.Column('username', sa.String(150), nullable=True),
    )
    op.execute("UPDATE users SET username = split_part(email, '@', 1) WHERE username IS NULL")
    op.alter_column('users', 'username', nullable=False)
    op.create_index('ix_users_username', 'users', ['username'], unique=True)

    # Add hashed_password column
    op.add_column(
        'users',
        sa.Column('hashed_password', sa.String(255), nullable=False, server_default=''),
    )

    # Add display_name column
    op.add_column(
        'users',
        sa.Column('display_name', sa.String(255), nullable=False, server_default=''),
    )

    # Add created_at column
    op.add_column(
        'users',
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.execute("UPDATE users SET created_at = NOW() WHERE created_at IS NULL")


def downgrade() -> None:
    op.drop_column('users', 'created_at')
    op.drop_column('users', 'display_name')
    op.drop_column('users', 'hashed_password')
    op.drop_index('ix_users_username', table_name='users')
    op.drop_column('users', 'username')
