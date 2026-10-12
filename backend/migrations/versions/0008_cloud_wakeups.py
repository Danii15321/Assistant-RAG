"""Shared throttle for durable cloud job notifications."""

from alembic import op

revision = "0008_cloud_wakeups"
down_revision = "0007_conversations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "CREATE TABLE cloud_wakeups (id integer PRIMARY KEY CHECK (id=1), "
        "next_at timestamptz NOT NULL DEFAULT now())"
    )
    op.execute("INSERT INTO cloud_wakeups(id) VALUES(1)")


def downgrade() -> None:
    op.execute("DROP TABLE cloud_wakeups")
