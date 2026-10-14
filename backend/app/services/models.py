from datetime import datetime, timezone

from app.adapters.openai import PRICING_VALID_UNTIL, OpenAIProvider
from app.config import Settings
from app.repositories.openai_budget import RESERVATION_MICROUSD, OpenAIBudgetRepository


def model_catalog(settings: Settings, budget: OpenAIBudgetRepository) -> dict[str, object]:
    items: list[dict[str, object]] = [{"id": "groq", "label": "Groq · gratuit", "available": True}]
    if not settings.openai_enabled:
        return {"models": items}
    remaining = budget.remaining_microusd()
    for model, cost in RESERVATION_MICROUSD.items():
        available = OpenAIProvider(settings, model, budget).ready()
        reason = "Clé OpenAI à configurer" if not available else ""
        if datetime.now(timezone.utc).date() > PRICING_VALID_UNTIL:
            available, reason = False, "Tarifs OpenAI à vérifier"
        elif remaining < cost:
            available, reason = False, "Plafond d’essai atteint"
        items.append(
            {
                "id": model,
                "label": "GPT-6 Luna" if model == "gpt-6-luna" else "GPT-6.1 Sol",
                "available": available,
                "reason": reason,
            }
        )
    return {"models": items, "remaining_microusd": remaining, "limit_microusd": 1_000_000}
