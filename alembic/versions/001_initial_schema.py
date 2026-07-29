"""Initial schema: contact_requests, idempotency_keys, app_stats."""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "contact_requests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("request_id", sa.String(length=12), nullable=False),
        sa.Column("client_ip", sa.String(length=45), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("phone", sa.String(length=20), nullable=False),
        sa.Column("comment", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="processing"),
        sa.Column("sentiment", sa.String(length=20), nullable=True),
        sa.Column("category", sa.String(length=30), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("ai_used", sa.Boolean(), nullable=True),
        sa.Column("ai_provider", sa.String(length=20), nullable=True),
        sa.Column("email_queued", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("request_id"),
    )
    op.create_index("ix_contact_requests_request_id", "contact_requests", ["request_id"])
    op.create_index("ix_contact_requests_email", "contact_requests", ["email"])
    op.create_index("ix_contact_requests_created_at", "contact_requests", ["created_at"])
    op.create_index("ix_contact_requests_sentiment", "contact_requests", ["sentiment"])
    op.create_index("ix_contact_requests_category", "contact_requests", ["category"])

    op.create_table(
        "idempotency_keys",
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("body_hash", sa.String(length=64), nullable=False),
        sa.Column("response", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("key"),
    )
    op.create_index("ix_idempotency_keys_expires_at", "idempotency_keys", ["expires_at"])

    op.create_table(
        "app_stats",
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("value", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("key"),
    )


def downgrade() -> None:
    op.drop_table("app_stats")
    op.drop_index("ix_idempotency_keys_expires_at", table_name="idempotency_keys")
    op.drop_table("idempotency_keys")
    op.drop_index("ix_contact_requests_category", table_name="contact_requests")
    op.drop_index("ix_contact_requests_sentiment", table_name="contact_requests")
    op.drop_index("ix_contact_requests_created_at", table_name="contact_requests")
    op.drop_index("ix_contact_requests_email", table_name="contact_requests")
    op.drop_index("ix_contact_requests_request_id", table_name="contact_requests")
    op.drop_table("contact_requests")
