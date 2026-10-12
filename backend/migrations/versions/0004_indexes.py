"""Versioned private passages, resumable vectors and atomic publication."""

from pathlib import Path

import sqlalchemy as sa
from alembic import op

revision = "0004_indexes"
down_revision = "0003_documents"
branch_labels = None
depends_on = None


def upgrade() -> None:
    source = (Path(__file__).resolve().parents[1] / "sql/0004_indexes.sql").read_text()
    for statement in source.split(";"):
        if statement.strip():
            op.execute(sa.text(statement))


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM ingestion_jobs WHERE kind='index'"))
    op.execute(
        sa.text(
            "UPDATE documents SET state='processing',stage='extracted',error_code=NULL "
            "WHERE state<>'deleting' AND (state='ready' OR stage IN ('indexed','indexing'))"
        )
    )
    op.drop_table("index_chunks")
    op.drop_table("index_runs")
    op.drop_constraint("ingestion_jobs_kind_check", "ingestion_jobs", type_="check")
    op.create_check_constraint(
        "ingestion_jobs_kind_check", "ingestion_jobs", "kind IN ('extract','delete')"
    )
    for column in ["embedded_count", "chunk_count", "index_version"]:
        op.drop_column("documents", column)
