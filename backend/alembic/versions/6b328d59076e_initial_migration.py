"""initial_migration

Revision ID: 6b328d59076e
Revises:
Create Date: 2026-04-14 18:19:08.070909
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '6b328d59076e'
down_revision = None
branch_labels = None
depends_on = None


property_type_enum = sa.Enum('SALE', 'RENT', 'OTHER', name='property_type_enum')
furnished_type_enum = sa.Enum(
    'FULLY_FURNISHED',
    'SEMI_FURNISHED',
    'UNFURNISHED',
    'UNKNOWN',
    name='furnished_type_enum',
)
listing_status_enum = sa.Enum('PENDING', 'EXTRACTED', 'FAILED', name='listing_status_enum')


def upgrade() -> None:
    op.create_table(
        'users',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_users_email', 'users', ['email'], unique=True)

    op.create_table(
        'file_processes',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('file', sa.String(length=1024), nullable=False),
        sa.Column('status', sa.String(length=255), nullable=False),
        sa.Column('progress', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_file_processes_created_at', 'file_processes', ['created_at'], unique=False)

    op.create_table(
        'raw_files',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('file', sa.String(length=1024), nullable=False),
        sa.Column('file_name', sa.String(length=255), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('source', sa.String(length=255), nullable=True),
        sa.Column('uploaded_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('processed', sa.Boolean(), nullable=False),
        sa.Column('process_started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('process_finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('dedupe_stats', sa.JSON(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('owner_id', sa.UUID(), nullable=True),
        sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_raw_files_status', 'raw_files', ['status'], unique=False)
    op.create_index('ix_raw_files_uploaded_at', 'raw_files', ['uploaded_at'], unique=False)

    op.create_table(
        'raw_message_chunks',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('rawfile_id', sa.UUID(), nullable=False),
        sa.Column('message_start', sa.DateTime(timezone=True), nullable=True),
        sa.Column('sender', sa.String(length=255), nullable=True),
        sa.Column('raw_text', sa.Text(), nullable=False),
        sa.Column('cleaned_text', sa.Text(), nullable=True),
        sa.Column('split_into', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=True),
        sa.ForeignKeyConstraint(['rawfile_id'], ['raw_files.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'ix_raw_message_chunks_created_at',
        'raw_message_chunks',
        ['created_at'],
        unique=False,
    )
    op.create_index(
        'ix_raw_message_chunks_message_start',
        'raw_message_chunks',
        ['message_start'],
        unique=False,
    )
    op.create_index('ix_raw_message_chunks_sender', 'raw_message_chunks', ['sender'], unique=False)
    op.create_index('ix_raw_message_chunks_status', 'raw_message_chunks', ['status'], unique=False)

    op.create_table(
        'property_listings',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('raw_chunk_id', sa.UUID(), nullable=False),
        sa.Column('property_type', property_type_enum, nullable=False),
        sa.Column('bhk', sa.Float(), nullable=True),
        sa.Column('price', sa.Integer(), nullable=True),
        sa.Column('location', sa.String(length=255), nullable=True),
        sa.Column('contact_number', sa.String(length=64), nullable=True),
        sa.Column('sender', sa.String(length=255), nullable=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=True),
        sa.Column('furnished', furnished_type_enum, nullable=True),
        sa.Column('floor_number', sa.Integer(), nullable=True),
        sa.Column('total_floors', sa.Integer(), nullable=True),
        sa.Column('area_sqft', sa.Integer(), nullable=True),
        sa.Column('landmark', sa.String(length=255), nullable=True),
        sa.Column('is_verified', sa.Boolean(), nullable=False),
        sa.Column('confidence_score', sa.Float(), nullable=False),
        sa.Column('status', listing_status_enum, nullable=False),
        sa.Column('raw_llm_output', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['raw_chunk_id'], ['raw_message_chunks.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('raw_chunk_id'),
    )
    op.create_index(
        'ix_property_listings_property_type',
        'property_listings',
        ['property_type'],
        unique=False,
    )
    op.create_index('ix_property_listings_price', 'property_listings', ['price'], unique=False)
    op.create_index(
        'ix_property_listings_raw_chunk_id',
        'property_listings',
        ['raw_chunk_id'],
        unique=False,
    )
    op.create_index('ix_property_listings_status', 'property_listings', ['status'], unique=False)

    op.create_table(
        'listing_chunks',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('listing_id', sa.UUID(), nullable=False),
        sa.Column('chunk_index', sa.Integer(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('qdrant_point_id', sa.String(length=128), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['listing_id'], ['property_listings.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_listing_chunks_listing_id', 'listing_chunks', ['listing_id'], unique=False)
    op.create_index(
        'ix_listing_chunks_qdrant_point_id',
        'listing_chunks',
        ['qdrant_point_id'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index('ix_listing_chunks_qdrant_point_id', table_name='listing_chunks')
    op.drop_index('ix_listing_chunks_listing_id', table_name='listing_chunks')
    op.drop_table('listing_chunks')

    op.drop_index('ix_property_listings_status', table_name='property_listings')
    op.drop_index('ix_property_listings_raw_chunk_id', table_name='property_listings')
    op.drop_index('ix_property_listings_price', table_name='property_listings')
    op.drop_index('ix_property_listings_property_type', table_name='property_listings')
    op.drop_table('property_listings')

    op.drop_index('ix_raw_message_chunks_status', table_name='raw_message_chunks')
    op.drop_index('ix_raw_message_chunks_sender', table_name='raw_message_chunks')
    op.drop_index('ix_raw_message_chunks_message_start', table_name='raw_message_chunks')
    op.drop_index('ix_raw_message_chunks_created_at', table_name='raw_message_chunks')
    op.drop_table('raw_message_chunks')

    op.drop_index('ix_raw_files_uploaded_at', table_name='raw_files')
    op.drop_index('ix_raw_files_status', table_name='raw_files')
    op.drop_table('raw_files')

    op.drop_index('ix_file_processes_created_at', table_name='file_processes')
    op.drop_table('file_processes')

    op.drop_index('ix_users_email', table_name='users')
    op.drop_table('users')

    listing_status_enum.drop(op.get_bind(), checkfirst=True)
    furnished_type_enum.drop(op.get_bind(), checkfirst=True)
    property_type_enum.drop(op.get_bind(), checkfirst=True)
