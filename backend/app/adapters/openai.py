import json
import time
from datetime import date, datetime, timezone
from typing import Protocol
from uuid import UUID

import httpx

from app.adapters.groq import Completion, ProviderError
from app.config import Settings
from app.models.llm import OpenAIModel
from app.services.generation import FORMAT

# Stop until prices are reviewed again; never silently increase the trial budget.
PRICING_VALID_UNTIL = date(2026, 11, 14)
MAX_REQUEST_BYTES = 16_000


class TrialBudget(Protocol):
    def reserve(self, model: OpenAIModel) -> UUID: ...


class OpenAIProvider:
    def __init__(
        self,
        settings: Settings,
        model: OpenAIModel,
        budget: TrialBudget,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.settings, self.model, self.budget, self.transport = settings, model, budget, transport

    def _key(self) -> str:
        if self.settings.cloud_runtime:
            key = self.settings.openai_api_key
            return key.get_secret_value().strip() if key else ""
        try:
            return self.settings.openai_api_key_file.read_text().strip()
        except (OSError, UnicodeError):
            return ""

    def ready(self) -> bool:
        return bool(self.settings.openai_enabled and self._key())

    def generate(self, messages: list[dict[str, str]], deadline: float) -> Completion:
        if not self.ready():
            raise ProviderError("llm_not_configured")
        if datetime.now(timezone.utc).date() > PRICING_VALID_UNTIL:
            raise ProviderError("openai_pricing_review_required")
        output_limit = 1200 if self.model == "gpt-6-luna" else 4096
        payload = {
            "model": self.model,
            "messages": messages,
            "store": False,
            "service_tier": "default",
            "response_format": FORMAT,
            "reasoning_effort": "none" if self.model == "gpt-6-luna" else "low",
            "max_completion_tokens": output_limit,
        }
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        if len(body) > MAX_REQUEST_BYTES:
            raise ProviderError("context_budget")
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ProviderError("generation_timeout")
        self.budget.reserve(self.model)
        try:
            with httpx.Client(
                transport=self.transport,
                timeout=min(35, remaining),
                follow_redirects=False,
                trust_env=False,
            ) as client:
                with client.stream(
                    "POST",
                    "https://api.openai.com/v1/chat/completions",
                    content=body,
                    headers={
                        "authorization": "Bearer " + self._key(),
                        "content-type": "application/json",
                    },
                ) as response:
                    if response.status_code == 429:
                        raise ProviderError("openai_provider_quota")
                    if response.status_code != 200:
                        raise ProviderError("llm_unavailable")
                    raw = bytearray()
                    for chunk in response.iter_bytes():
                        if time.monotonic() >= deadline:
                            raise ProviderError("generation_timeout")
                        raw.extend(chunk)
                        if len(raw) > 65536:
                            raise ProviderError("invalid_llm_output")
            result = json.loads(raw)
            choice, usage = result["choices"][0], result["usage"]
            prompt, completion = usage["prompt_tokens"], usage["completion_tokens"]
            content = choice["message"]["content"]
            if (
                choice["finish_reason"] != "stop"
                or not isinstance(content, str)
                or not all(type(n) is int and n >= 0 for n in [prompt, completion])
                or prompt > MAX_REQUEST_BYTES + 4096
                or completion > output_limit
            ):
                raise ProviderError("invalid_llm_output")
            return Completion(content, prompt, completion)
        except httpx.TimeoutException:
            raise ProviderError("generation_timeout") from None
        except httpx.HTTPError:
            raise ProviderError("llm_unavailable") from None
        except (ValueError, KeyError, IndexError, TypeError):
            raise ProviderError("invalid_llm_output") from None
