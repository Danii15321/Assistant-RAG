"""Enable pgvector; business tables arrive with their owning development steps."""

from alembic import op

revision: str = "0001_vector"
down_revision: str | None = None
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")


def downgrade() -> None:
    # PostgreSQL refuses this if vector columns depend on it. Never use CASCADE.
    op.execute("DROP EXTENSION IF EXISTS vector")
