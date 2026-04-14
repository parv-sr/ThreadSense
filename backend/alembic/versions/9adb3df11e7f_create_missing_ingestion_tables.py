"""create missing ingestion tables

Revision ID: 9adb3df11e7f
Revises: 6b328d59076e
Create Date: 2026-04-14 19:55:06.873648
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9adb3df11e7f'
down_revision = '6b328d59076e'
branch_labels = None
depends_on = None


def _has_index(insp: sa.Inspector, table_name: str, index_name: str) -> bool:
    return any(index["name"] == index_name for index in insp.get_indexes(table_name))


def _has_fk(insp: sa.Inspector, table_name: str, fk_name: str) -> bool:
    return any(fk["name"] == fk_name for fk in insp.get_foreign_keys(table_name))


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if not insp.has_table("users"):
        op.create_table(
            "users",
            sa.Column("id", sa.UUID(), nullable=False),
            sa.Column("email", sa.String(), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_users_email", "users", ["email"], unique=True)
    elif not _has_index(insp, "users", "ix_users_email"):
        op.create_index("ix_users_email", "users", ["email"], unique=True)

    if not insp.has_table("raw_files"):
        op.create_table(
            "raw_files",
            sa.Column("id", sa.UUID(), nullable=False),
            sa.Column("file", sa.String(length=1024), nullable=False),
            sa.Column("file_name", sa.String(length=255), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("source", sa.String(length=255), nullable=True),
            sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("processed", sa.Boolean(), nullable=False),
            sa.Column("process_started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("process_finished_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("dedupe_stats", sa.JSON(), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("owner_id", sa.UUID(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )

    if insp.has_table("raw_files"):
        if not _has_index(insp, "raw_files", "ix_raw_files_status"):
            op.create_index("ix_raw_files_status", "raw_files", ["status"], unique=False)
        if not _has_index(insp, "raw_files", "ix_raw_files_uploaded_at"):
            op.create_index(
                "ix_raw_files_uploaded_at",
                "raw_files",
                ["uploaded_at"],
                unique=False,
            )
        if insp.has_table("users") and not _has_fk(
            insp,
            "raw_files",
            "fk_raw_files_owner_id_users",
        ):
            op.create_foreign_key(
                "fk_raw_files_owner_id_users",
                "raw_files",
                "users",
                ["owner_id"],
                ["id"],
                ondelete="SET NULL",
            )

    if not insp.has_table("raw_message_chunks"):
        op.create_table(
            "raw_message_chunks",
            sa.Column("id", sa.UUID(), nullable=False),
            sa.Column("rawfile_id", sa.UUID(), nullable=False),
            sa.Column("message_start", sa.DateTime(timezone=True), nullable=True),
            sa.Column("sender", sa.String(length=255), nullable=True),
            sa.Column("raw_text", sa.Text(), nullable=False),
            sa.Column("cleaned_text", sa.Text(), nullable=True),
            sa.Column("split_into", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("user_id", sa.UUID(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )

    if insp.has_table("raw_message_chunks"):
        if not _has_index(insp, "raw_message_chunks", "ix_raw_message_chunks_created_at"):
            op.create_index(
                "ix_raw_message_chunks_created_at",
                "raw_message_chunks",
                ["created_at"],
                unique=False,
            )
        if not _has_index(insp, "raw_message_chunks", "ix_raw_message_chunks_message_start"):
            op.create_index(
                "ix_raw_message_chunks_message_start",
                "raw_message_chunks",
                ["message_start"],
                unique=False,
            )
        if not _has_index(insp, "raw_message_chunks", "ix_raw_message_chunks_sender"):
            op.create_index(
                "ix_raw_message_chunks_sender",
                "raw_message_chunks",
                ["sender"],
                unique=False,
            )
        if not _has_index(insp, "raw_message_chunks", "ix_raw_message_chunks_status"):
            op.create_index(
                "ix_raw_message_chunks_status",
                "raw_message_chunks",
                ["status"],
                unique=False,
            )

        if insp.has_table("raw_files") and not _has_fk(
            insp,
            "raw_message_chunks",
            "fk_raw_message_chunks_rawfile_id_raw_files",
        ):
            op.create_foreign_key(
                "fk_raw_message_chunks_rawfile_id_raw_files",
                "raw_message_chunks",
                "raw_files",
                ["rawfile_id"],
                ["id"],
                ondelete="CASCADE",
            )

        if insp.has_table("users") and not _has_fk(
            insp,
            "raw_message_chunks",
            "fk_raw_message_chunks_user_id_users",
        ):
            op.create_foreign_key(
                "fk_raw_message_chunks_user_id_users",
                "raw_message_chunks",
                "users",
                ["user_id"],
                ["id"],
                ondelete="SET NULL",
            )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if insp.has_table("raw_message_chunks"):
        if _has_fk(insp, "raw_message_chunks", "fk_raw_message_chunks_user_id_users"):
            op.drop_constraint("fk_raw_message_chunks_user_id_users", "raw_message_chunks", type_="foreignkey")
        if _has_fk(insp, "raw_message_chunks", "fk_raw_message_chunks_rawfile_id_raw_files"):
            op.drop_constraint(
                "fk_raw_message_chunks_rawfile_id_raw_files",
                "raw_message_chunks",
                type_="foreignkey",
            )
        if _has_index(insp, "raw_message_chunks", "ix_raw_message_chunks_status"):
            op.drop_index("ix_raw_message_chunks_status", table_name="raw_message_chunks")
        if _has_index(insp, "raw_message_chunks", "ix_raw_message_chunks_sender"):
            op.drop_index("ix_raw_message_chunks_sender", table_name="raw_message_chunks")
        if _has_index(insp, "raw_message_chunks", "ix_raw_message_chunks_message_start"):
            op.drop_index("ix_raw_message_chunks_message_start", table_name="raw_message_chunks")
        if _has_index(insp, "raw_message_chunks", "ix_raw_message_chunks_created_at"):
            op.drop_index("ix_raw_message_chunks_created_at", table_name="raw_message_chunks")
        op.drop_table("raw_message_chunks")

    if insp.has_table("raw_files"):
        if _has_fk(insp, "raw_files", "fk_raw_files_owner_id_users"):
            op.drop_constraint("fk_raw_files_owner_id_users", "raw_files", type_="foreignkey")
        if _has_index(insp, "raw_files", "ix_raw_files_uploaded_at"):
            op.drop_index("ix_raw_files_uploaded_at", table_name="raw_files")
        if _has_index(insp, "raw_files", "ix_raw_files_status"):
            op.drop_index("ix_raw_files_status", table_name="raw_files")
        op.drop_table("raw_files")

    # Keep users only if it was already present before this repair migration.
