"""
OpenRouter Adapter
=====================
OpenRouter exposes an OpenAI-compatible REST endpoint that proxies to
many models (Claude, GPT, Llama, Mistral...) behind one API key —
useful as a broad fallback tier. Implemented via plain `requests`
(no SDK needed since the API is just OpenAI-shaped JSON over HTTP).
"""

import requests

from core.interfaces import ILanguageModel
from providers.prompts import SYSTEM_PROMPT, parse_json_safe
from providers.exceptions import ProviderError, ProviderTimeoutError, ProviderUnavailableError

API_URL = "https://openrouter.ai/api/v1/chat/completions"


class OpenRouterAdapter(ILanguageModel):
    def __init__(self, api_key: str, model: str = "openai/gpt-4o", timeout: float = 20.0):
        self._api_key = api_key
        self._model = model
        self._timeout = timeout

    def ask(self, user_text: str, context: str = "") -> dict:
        if not self._api_key:
            raise ProviderUnavailableError("OpenRouter: OPENROUTER_API_KEY is not configured.")

        full_prompt = f"{context}\n\nUser: {user_text}" if context else user_text

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self._model,
            "max_tokens": 500,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": full_prompt},
            ],
        }

        try:
            resp = requests.post(API_URL, headers=headers, json=payload, timeout=self._timeout)
        except requests.Timeout as e:
            raise ProviderTimeoutError(f"OpenRouter request timed out: {e}") from e
        except requests.ConnectionError as e:
            raise ProviderUnavailableError(f"OpenRouter unreachable: {e}") from e

        if resp.status_code in (401, 403):
            raise ProviderUnavailableError(f"OpenRouter authentication failed: {resp.text}")
        if resp.status_code >= 500:
            raise ProviderError(f"OpenRouter server error ({resp.status_code}): {resp.text}")
        if resp.status_code != 200:
            raise ProviderError(f"OpenRouter request failed ({resp.status_code}): {resp.text}")

        try:
            data = resp.json()
            text = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, ValueError) as e:
            raise ProviderError(f"OpenRouter returned an unexpected response shape: {e}") from e

        return parse_json_safe(text)
