import json
import math
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Protocol

import httpx
from sqlalchemy.engine import make_url

from app.config import Settings
from app.services.generation import FORMAT


@dataclass
class Completion:
    content: str
    prompt_tokens: int
    completion_tokens: int


class ProviderError(Exception):
    def __init__(self, code: str, transient: bool = False, retry_after: int = 1) -> None:
        self.code, self.transient, self.retry_after = code, transient, retry_after
        super().__init__(code)


class Provider(Protocol):
    def ready(self) -> bool: ...
    def generate(self, messages: list[dict[str, str]], deadline: float) -> Completion: ...


def retry_delay(value: str | None) -> int:
    try:
        seconds = float(value or "60")
    except ValueError:
        try:
            seconds = (
                parsedate_to_datetime(value or "") - datetime.now(timezone.utc)
            ).total_seconds()
        except (ValueError, TypeError):
            seconds = 60
    if not math.isfinite(seconds):
        seconds = 60
    return max(1, min(86400, int(seconds)))


class GroqProvider:
    def __init__(self, settings: Settings, transport: httpx.BaseTransport | None = None) -> None:
        self.settings, self.transport = settings, transport

    def _key(self) -> str:
        if self.settings.groq_api_key:
            return self.settings.groq_api_key.get_secret_value()
        try:
            return self.settings.groq_api_key_file.read_text().strip()
        except (OSError, UnicodeError):
            return ""

    def ready(self) -> bool:
        return bool(self.settings.llm_free_plan_confirmed and self._key())

    def generate(self, messages: list[dict[str, str]], deadline: float) -> Completion:
        if not self.ready():
            raise ProviderError("llm_not_configured")
        endpoint = "https://api.groq.com/openai/v1/chat/completions"
        if self.settings.llm_test_endpoint:
            url = make_url(self.settings.database_url or "")
            if (
                url.database != "assistant_rag_test"
                or self.settings.llm_test_endpoint
                != "http://llm-test:8000/openai/v1/chat/completions"
            ):
                raise ProviderError("llm_not_configured")
            endpoint = self.settings.llm_test_endpoint
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ProviderError("generation_timeout")
        payload = {
            "model": self.settings.llm_model,
            "temperature": 0,
            "max_completion_tokens": 600,
            "reasoning_effort": "low",
            "response_format": FORMAT,
            "messages": messages,
        }
        try:
            with httpx.Client(
                transport=self.transport,
                timeout=min(15, remaining),
                follow_redirects=False,
                trust_env=False,
            ) as client:
                with client.stream(
                    "POST",
                    endpoint,
                    json=payload,
                    headers={
                        "authorization": "Bearer " + self._key(),
                        "user-agent": "assistant-rag-v1",
                    },
                ) as response:
                    if response.status_code == 429:
                        raise ProviderError(
                            "provider_quota",
                            retry_after=retry_delay(response.headers.get("retry-after")),
                        )
                    if response.status_code != 200:
                        raise ProviderError(
                            "llm_unavailable",
                            transient=response.status_code in {500, 502, 503, 504},
                            retry_after=retry_delay(response.headers.get("retry-after", "1")),
                        )
                    raw = bytearray()
                    for chunk in response.iter_bytes():
                        if time.monotonic() >= deadline:
                            raise ProviderError("generation_timeout")
                        raw.extend(chunk)
                        if len(raw) > 32768:
                            raise ProviderError("invalid_llm_output")
            result = json.loads(raw)
            choice = result["choices"][0]
            usage = result["usage"]
            content = choice["message"]["content"]
            prompt, completion = usage["prompt_tokens"], usage["completion_tokens"]
            if (
                choice["finish_reason"] != "stop"
                or not isinstance(content, str)
                or not all(type(n) is int and n >= 0 for n in [prompt, completion])
                or prompt > 2500
                or completion > 600
            ):
                raise ProviderError("invalid_llm_output")
            return Completion(content, prompt, completion)
        except httpx.TimeoutException:
            raise ProviderError("generation_timeout", transient=True) from None
        except httpx.HTTPError:
            raise ProviderError("llm_unavailable", transient=True) from None
        except (ValueError, KeyError, IndexError, TypeError):
            raise ProviderError("invalid_llm_output") from None
