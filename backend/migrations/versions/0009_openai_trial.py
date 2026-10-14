"""Local prepaid OpenAI trial; retain the spending ledger across rollbacks."""

from alembic import op

revision = "0009_openai_trial"
down_revision = "0008_cloud_wakeups"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE conversation_exchanges ADD COLUMN model text NOT NULL DEFAULT 'groq'")
    op.execute(
        "CREATE TABLE IF NOT EXISTS openai_trial_budget (id integer PRIMARY KEY CHECK (id=1), "
        "reserved_microusd integer NOT NULL DEFAULT 0 CHECK (reserved_microusd BETWEEN 0 AND "
        "1000000))"
    )
    op.execute("INSERT INTO openai_trial_budget(id) VALUES(1) ON CONFLICT DO NOTHING")
    op.execute(
        "CREATE TABLE IF NOT EXISTS openai_trial_attempts (id uuid PRIMARY KEY, model text "
        "NOT NULL CHECK (model IN ('gpt-6-luna','gpt-6.1-sol')), reserved_microusd integer "
        "NOT NULL CHECK (reserved_microusd>0), created_at timestamptz NOT NULL DEFAULT now())"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE conversation_exchanges DROP COLUMN model")
    # Never reset money already committed. A later upgrade reuses this ledger.
