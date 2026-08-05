"""
ProviderRouter
================
Implements ILanguageModel. This is the ONLY language-model class
Core's default composition ever talks to — it is itself just another
ILanguageModel, so Planner/Orchestrator code needs zero awareness that
routing, retries, or fallback exist underneath it.

Responsibilities:
    1. Pick the provider order PURELY from configuration
       (JarvisConfig.llm_provider + llm_fallback_providers) — no
       hardcoded provider preference anywhere in this file.
    2. Retry a given provider a few times (exponential backoff) on
       transient failures (ProviderError / ProviderTimeoutError).
    3. Skip straight to the next provider on
       ProviderUnavailableError (retrying an unreachable/unconfigured
       service wastes time).
    4. Always fall back to MockProvider as the final safety net, so
       JARVIS degrades gracefully instead of raising an exception the
       Orchestrator would have to handle.

Strategy Pattern: each entry in `_PROVIDER_FACTORIES` is an
interchangeable provider strategy. Adding provider #6 later = one new
adapter class + one new dict entry here. Nothing above this file
(Planner, Executor, Verifier, Orchestrator) ever changes.
"""

import time
from typing import Callable, Dict, List, Optional

from core.interfaces import ILanguageModel
from core.config import JarvisConfig, get_config
from core.logger import get_logger
from providers.exceptions import ProviderError, ProviderTimeoutError, ProviderUnavailableError
from providers.claude_adapter import ClaudeAdapter
from providers.openai_adapter import GPTAdapter
from providers.gemini_adapter import GeminiAdapter
from providers.openrouter_adapter import OpenRouterAdapter
from providers.local_adapter import LocalAdapter
from providers.mock_provider import MockProvider

log = get_logger("providers.router")

_PROVIDER_FACTORIES: Dict[str, Callable[[JarvisConfig], ILanguageModel]] = {
    "claude": lambda c: ClaudeAdapter(
        api_key=c.anthropic_api_key, timeout=c.llm_timeout_seconds
    ),
    "openai": lambda c: GPTAdapter(
        api_key=c.openai_api_key, timeout=c.llm_timeout_seconds
    ),
    "gemini": lambda c: GeminiAdapter(
        api_key=c.gemini_api_key, timeout=c.llm_timeout_seconds
    ),
    "openrouter": lambda c: OpenRouterAdapter(
        api_key=c.openrouter_api_key, model=c.openrouter_model, timeout=c.llm_timeout_seconds
    ),
    "local": lambda c: LocalAdapter(timeout=c.llm_timeout_seconds),
    "mock": lambda c: MockProvider(),
}


class ProviderRouter(ILanguageModel):
    def __init__(self, config: Optional[JarvisConfig] = None):
        self._config = config or get_config()
        self._order = self._build_provider_order()
        log.info("Provider routing order: %s", self._order)

    def _build_provider_order(self) -> List[str]:
        primary = self._config.llm_provider.strip().lower()
        fallbacks = [
            p.strip().lower()
            for p in self._config.llm_fallback_providers.split(",")
            if p.strip()
        ]
        order = [primary] + [p for p in fallbacks if p != primary]
        if "mock" not in order:
            order.append("mock")  # always-on safety net
        return order

    def ask(self, user_text: str, context: str = "") -> dict:
        for provider_name in self._order:
            factory = _PROVIDER_FACTORIES.get(provider_name)
            if factory is None:
                log.warning("Unknown provider '%s' in routing order — skipping.", provider_name)
                continue

            try:
                provider = factory(self._config)
            except Exception:
                log.exception("Failed to construct provider '%s' — skipping.", provider_name)
                continue

            result = self._ask_with_retries(provider, provider_name, user_text, context)
            if result is not None:
                return result

            log.warning("Provider '%s' exhausted, falling back to next provider.", provider_name)

        # Should be unreachable — "mock" is always in `_order` and never fails —
        # but kept as an absolute last resort so `ask()` never raises.
        log.error("All providers in the routing order failed, including mock.")
        return {
            "intent": "chat",
            "action_params": {},
            "reply": "I'm having trouble reaching any AI provider right now. Please try again shortly.",
        }

    def _ask_with_retries(
        self, provider: ILanguageModel, name: str, user_text: str, context: str
    ) -> Optional[dict]:
        attempts = max(1, self._config.llm_max_retries + 1)

        for attempt in range(1, attempts + 1):
            try:
                result = provider.ask(user_text, context=context)
                if attempt > 1:
                    log.info("Provider '%s' succeeded on retry %d.", name, attempt)
                return result

            except ProviderUnavailableError as e:
                log.warning("Provider '%s' unavailable: %s", name, e)
                return None  # no point retrying — go straight to next provider

            except ProviderTimeoutError as e:
                log.warning("Provider '%s' timed out (attempt %d/%d): %s", name, attempt, attempts, e)

            except ProviderError as e:
                log.warning("Provider '%s' failed (attempt %d/%d): %s", name, attempt, attempts, e)

            except Exception:
                log.exception("Provider '%s' raised an unexpected error (attempt %d/%d).", name, attempt, attempts)

            if attempt < attempts:
                backoff_seconds = min(2 ** (attempt - 1), 8)
                time.sleep(backoff_seconds)

        return None
