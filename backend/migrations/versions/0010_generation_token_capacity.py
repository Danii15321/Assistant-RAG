"""Allow bounded OpenAI token reservations without changing daily or dollar caps."""

from alembic import op

revision = "0010_generation_token_capacity"
down_revision = "0009_openai_trial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE generation_attempts DROP CONSTRAINT generation_attempts_reserved_tokens_check"
    )
    op.execute(
        "ALTER TABLE generation_attempts ADD CONSTRAINT "
        "generation_attempts_reserved_tokens_check CHECK (reserved_tokens BETWEEN 1 AND 24576)"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE generation_attempts DROP CONSTRAINT generation_attempts_reserved_tokens_check"
    )
    # Preserve prior OpenAI attempts in the daily counters. Older code only inserts <=3100.
    op.execute(
        "ALTER TABLE generation_attempts ADD CONSTRAINT "
        "generation_attempts_reserved_tokens_check "
        "CHECK (reserved_tokens BETWEEN 1 AND 3100) NOT VALID"
    )
