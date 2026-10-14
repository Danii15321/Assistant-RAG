from uuid import UUID, uuid4

from sqlalchemy import Engine, text

from app.models.document import DocumentError
from app.models.llm import OpenAIModel

# Conservative per-attempt ceilings, not an invoice. Includes failed/unknown calls.
# See ADR 0011 for input/output limits, reviewed prices and safety margin.
RESERVATION_MICROUSD: dict[OpenAIModel, int] = {"gpt-6-luna": 10_000, "gpt-6.1-sol": 120_000}
LIMIT_MICROUSD = 1_000_000


class OpenAIBudgetRepository:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def remaining_microusd(self) -> int:
        with self.engine.connect() as c:
            spent = c.execute(
                text("SELECT reserved_microusd FROM openai_trial_budget WHERE id=1")
            ).scalar_one()
            return max(0, LIMIT_MICROUSD - int(spent))

    def reserve(self, model: OpenAIModel) -> UUID:
        amount = RESERVATION_MICROUSD[model]
        attempt = uuid4()
        with self.engine.begin() as c:
            updated = c.execute(
                text(
                    "UPDATE openai_trial_budget SET "
                    "reserved_microusd=reserved_microusd+:amount WHERE id=1 AND "
                    "reserved_microusd+:amount<=:limit RETURNING id"
                ),
                {"amount": amount, "limit": LIMIT_MICROUSD},
            ).scalar_one_or_none()
            if updated is None:
                raise DocumentError(429, "openai_budget_exhausted")
            c.execute(
                text(
                    "INSERT INTO openai_trial_attempts(id,model,reserved_microusd) "
                    "VALUES(:id,:model,:amount)"
                ),
                {"id": attempt, "model": model, "amount": amount},
            )
        # Commit before any outbound call. Never release an ambiguous reservation.
        return attempt
