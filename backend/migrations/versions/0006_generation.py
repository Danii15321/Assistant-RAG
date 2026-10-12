"""Shared generation budgets and fenced provider lease, no prompt/answer retention."""

from pathlib import Path

import sqlalchemy as sa
from alembic import op

revision = "0006_generation"
down_revision = "0005_search"
branch_labels = None
depends_on = None


def upgrade() -> None:
    source = (Path(__file__).resolve().parents[1] / "sql/0006_generation.sql").read_text()
    for statement in source.split(";"):
        if statement.strip():
            op.execute(sa.text(statement))


def downgrade() -> None:
    op.drop_table("generation_limits")
    op.drop_table("generation_attempts")
