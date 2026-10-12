"""Private uploads, canonical text and transactional durable local jobs."""

from pathlib import Path

import sqlalchemy as sa
from alembic import op

revision = "0003_documents"
down_revision = "0002_identity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    source = (Path(__file__).resolve().parents[1] / "sql/0003_documents.sql").read_text()
    for statement in source.split(";"):
        if statement.strip():
            op.execute(sa.text(statement))


def downgrade() -> None:
    for table in ["ingestion_jobs", "extracted_units", "documents"]:
        op.drop_table(table)
