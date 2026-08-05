"""
Claude Adapter
================
Implements ILanguageModel using Anthropic's API. This is one
interchangeable Strategy among several (see providers/router.py) —
Core never imports this class directly.
"""

from core.interfaces import ILanguageModel
from providers.prompts import SYSTEM_PROMPT, parse_json_safe
from providers.exceptions import ProviderError, ProviderTimeoutError, ProviderUnavailableError


class ClaudeAdapter(ILanguageModel):
    def __init__(self, api_key: str, model: str = "claude-sonnet-4-6", timeout: float = 20.0):
        self._api_key = api_key
        self._model = model
        self._timeout = timeout

    def ask(self, user_text: str, context: str = "") -> dict:
        if not self._api_key:
            raise ProviderUnavailableError("Claude: ANTHROPIC_API_KEY is not configured.")

        try:
            import anthropic
        except ImportError as e:
            raise ProviderUnavailableError("Claude: 'anthropic' package is not installed.") from e

        full_prompt = f"{context}\n\nUser: {user_text}" if context else user_text

        try:
            client = anthropic.Anthropic(api_key=self._api_key, timeout=self._timeout)
            response = client.messages.create(
                model=self._model,
                max_tokens=500,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": full_prompt}],
            )
            return parse_json_safe(response.content[0].text)

        except anthropic.APITimeoutError as e:
            raise ProviderTimeoutError(f"Claude request timed out: {e}") from e
        except anthropic.APIConnectionError as e:
            raise ProviderUnavailableError(f"Claude unreachable: {e}") from e
        except anthropic.AuthenticationError as e:
            raise ProviderUnavailableError(f"Claude authentication failed: {e}") from e
        except Exception as e:
            raise ProviderError(f"Claude request failed: {e}") from e
