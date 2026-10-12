"""Short-lived private query jobs sharing the ingestion CPU worker."""

from pathlib import Path

import sqlalchemy as sa
from alembic import op

revision = "0005_search"
down_revision = "0004_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    source = (Path(__file__).resolve().parents[1] / "sql/0005_search.sql").read_text()
    for statement in source.split(";"):
        if statement.strip():
            op.execute(sa.text(statement))


def downgrade() -> None:
    op.drop_table("search_jobs")
