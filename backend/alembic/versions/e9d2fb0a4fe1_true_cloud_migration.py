"""baseline relational schema

Revision ID: e9d2fb0a4fe1
Revises:
Create Date: 2026-04-15 09:39:03.285227
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "e9d2fb0a4fe1"
down_revision = None
branch_labels = None
depends_on = None


property_type_enum = postgresql.ENUM(
    "SALE",
    "RENT",
    "OTHER",
    "RESIDENTIAL",
    "COMMERCIAL",
    "PLOT",
    "LAND",
    "UNKNOWN",
    name="property_type_enum",
    create_type=False,
)
furnished_type_enum = postgresql.ENUM(
    "FULLY_FURNISHED",
    "SEMI_FURNISHED",
    "FURNISHED",
    "UNFURNISHED",
    "UNKNOWN",
    name="furnished_type_enum",
    create_type=False,
)
listing_status_enum = postgresql.ENUM("PENDING", "EXTRACTED", "FAILED", name="listing_status_enum", create_type=False)


def upgrade() -> None:
    bind = op.get_bind()
    
    bind.execute(sa.text("""
        DO $$ BEGIN
            CREATE TYPE property_type_enum AS ENUM ('SALE', 'RENT', 'OTHER', 'RESIDENTIAL', 'COMMERCIAL', 'PLOT', 'LAND', 'UNKNOWN');
        EXCEPTION WHEN duplicate_object THEN null;
        END $$;
    """))
        
    bind.execute(sa.text("""
        DO $$ BEGIN
            CREATE TYPE furnished_type_enum AS ENUM ('FULLY_FURNISHED', 'SEMI_FURNISHED', 'FURNISHED', 'UNFURNISHED', 'UNKNOWN');
        EXCEPTION WHEN duplicate_object THEN null;
        END $$;
    """))
        
    bind.execute(sa.text("""
        DO $$ BEGIN
            CREATE TYPE listing_status_enum AS ENUM ('PENDING', 'EXTRACTED', 'FAILED');
        EXCEPTION WHEN duplicate_object THEN null;
        END $$;
    """))

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "raw_files",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("file", sa.String(length=1024), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("content", sa.Text(), nullable=False, server_default=""),
        sa.Column("source", sa.String(length=255), nullable=True),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("processed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("process_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("process_finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("dedupe_stats", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="PENDING"),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
    )
    op.create_index("ix_raw_files_uploaded_at", "raw_files", ["uploaded_at"])
    op.create_index("ix_raw_files_status", "raw_files", ["status"])

    op.create_table(
        "raw_message_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "rawfile_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("raw_files.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("message_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sender", sa.String(length=255), nullable=True),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("cleaned_text", sa.Text(), nullable=True),
        sa.Column("split_into", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="NEW"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
    )
    op.create_index("ix_raw_message_chunks_message_start", "raw_message_chunks", ["message_start"])
    op.create_index("ix_raw_message_chunks_sender", "raw_message_chunks", ["sender"])
    op.create_index("ix_raw_message_chunks_status", "raw_message_chunks", ["status"])
    op.create_index("ix_raw_message_chunks_created_at", "raw_message_chunks", ["created_at"])

    op.create_table(
        "file_processes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("file", sa.String(length=1024), nullable=False),
        sa.Column("status", sa.String(length=255), nullable=False, server_default="Queued"),
        sa.Column("progress", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_file_processes_created_at", "file_processes", ["created_at"])

    op.create_table(
        "property_listings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "raw_chunk_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("raw_message_chunks.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("property_type", property_type_enum, nullable=False, server_default="OTHER"),
        sa.Column("bhk", sa.Float(), nullable=True),
        sa.Column("price", sa.BigInteger(), nullable=True),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("contact_number", sa.String(length=64), nullable=True),
        sa.Column("sender", sa.String(length=255), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("furnished", furnished_type_enum, nullable=True),
        sa.Column("floor_number", sa.Integer(), nullable=True),
        sa.Column("total_floors", sa.Integer(), nullable=True),
        sa.Column("area_sqft", sa.Integer(), nullable=True),
        sa.Column("landmark", sa.String(length=255), nullable=True),
        sa.Column("is_verified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("confidence_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("status", listing_status_enum, nullable=False, server_default="PENDING"),
        sa.Column("raw_llm_output", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_property_listings_raw_chunk_id", "property_listings", ["raw_chunk_id"])
    op.create_index("ix_property_listings_property_type", "property_listings", ["property_type"])
    op.create_index("ix_property_listings_price", "property_listings", ["price"])
    op.create_index("ix_property_listings_status", "property_listings", ["status"])

    op.create_table(
        "listing_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "listing_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("property_listings.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("chunk_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_listing_chunks_listing_id", "listing_chunks", ["listing_id"])


def downgrade() -> None:
    op.drop_index("ix_listing_chunks_listing_id", table_name="listing_chunks")
    op.drop_table("listing_chunks")
    op.drop_index("ix_property_listings_status", table_name="property_listings")
    op.drop_index("ix_property_listings_price", table_name="property_listings")
    op.drop_index("ix_property_listings_property_type", table_name="property_listings")
    op.drop_index("ix_property_listings_raw_chunk_id", table_name="property_listings")
    op.drop_table("property_listings")
    op.drop_index("ix_file_processes_created_at", table_name="file_processes")
    op.drop_table("file_processes")
    op.drop_index("ix_raw_message_chunks_created_at", table_name="raw_message_chunks")
    op.drop_index("ix_raw_message_chunks_status", table_name="raw_message_chunks")
    op.drop_index("ix_raw_message_chunks_sender", table_name="raw_message_chunks")
    op.drop_index("ix_raw_message_chunks_message_start", table_name="raw_message_chunks")
    op.drop_table("raw_message_chunks")
    op.drop_index("ix_raw_files_status", table_name="raw_files")
    op.drop_index("ix_raw_files_uploaded_at", table_name="raw_files")
    op.drop_table("raw_files")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")

    bind = op.get_bind()
    listing_status_enum.drop(bind, checkfirst=True)
    furnished_type_enum.drop(bind, checkfirst=True)
    property_type_enum.drop(bind, checkfirst=True)
