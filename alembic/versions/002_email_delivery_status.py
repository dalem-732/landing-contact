"""Add email_owner_sent and email_user_sent delivery flags."""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "contact_requests",
        sa.Column("email_owner_sent", sa.Boolean(), nullable=True),
    )
    op.add_column(
        "contact_requests",
        sa.Column("email_user_sent", sa.Boolean(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("contact_requests", "email_user_sent")
    op.drop_column("contact_requests", "email_owner_sent")
