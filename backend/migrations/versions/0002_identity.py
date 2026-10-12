"""Better Auth credentials/sessions/JWKS and private business identities.

Revision ID: 0002_identity
Revises: 0001_vector
"""

from pathlib import Path

import sqlalchemy as sa
from alembic import op

revision = "0002_identity"
down_revision = "0001_vector"
branch_labels = None
depends_on = None


def upgrade() -> None:
    source = (Path(__file__).resolve().parents[1] / "sql/0002_better_auth.sql").read_text()
    sql = "\n".join(line for line in source.splitlines() if not line.startswith("--"))
    for statement in sql.split(";"):
        if statement.strip():
            op.execute(sa.text(statement))
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "auth_user_id", sa.Text(), sa.ForeignKey("auth_user.id"), nullable=False, unique=True
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )


def downgrade() -> None:
    op.drop_table("users")
    for table in [
        "auth_rate_limit",
        "auth_jwks",
        "auth_verification",
        "auth_account",
        "auth_session",
        "auth_user",
    ]:
        op.drop_table(table)
