"""Private conversations, idempotent exchanges and removable citation snapshots."""

from pathlib import Path

from alembic import op

revision = "0007_conversations"
down_revision = "0006_generation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    source = (Path(__file__).resolve().parents[1] / "sql/0007_conversations.sql").read_text()
    op.get_bind().exec_driver_sql(source)


def downgrade() -> None:
    op.execute("DROP TRIGGER conversations_document_excluded ON documents")
    op.execute("DROP TRIGGER conversations_document_deleted ON documents")
    op.execute("DROP FUNCTION scrub_conversation_sources()")
    for table in ["conversation_sources", "conversation_exchanges", "conversations"]:
        op.drop_table(table)
