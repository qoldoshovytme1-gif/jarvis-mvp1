"""
Gemini Adapter (Google)
==========================
Implements ILanguageModel using Google's Generative Language REST API
directly (via `requests`) rather than the `google-generativeai` SDK —
one less dependency to install, and it keeps every adapter's shape
consistent (plain HTTP + timeout + JSON parsing).
"""

import requests

from core.interfaces import ILanguageModel
from providers.prompts import SYSTEM_PROMPT, parse_json_safe
from providers.exceptions import ProviderError, ProviderTimeoutError, ProviderUnavailableError

API_URL_TEMPLATE = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
)


class GeminiAdapter(ILanguageModel):
    def __init__(self, api_key: str, model: str = "gemini-2.0-flash", timeout: float = 20.0):
        self._api_key = api_key
        self._model = model
        self._timeout = timeout

    def ask(self, user_text: str, context: str = "") -> dict:
        if not self._api_key:
            raise ProviderUnavailableError("Gemini: GEMINI_API_KEY is not configured.")

        full_prompt = f"{context}\n\nUser: {user_text}" if context else user_text
        url = API_URL_TEMPLATE.format(model=self._model, key=self._api_key)

        payload = {
            "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
            "contents": [{"parts": [{"text": full_prompt}]}],
        }

        try:
            resp = requests.post(url, json=payload, timeout=self._timeout)
        except requests.Timeout as e:
            raise ProviderTimeoutError(f"Gemini request timed out: {e}") from e
        except requests.ConnectionError as e:
            raise ProviderUnavailableError(f"Gemini unreachable: {e}") from e

        if resp.status_code in (401, 403):
            raise ProviderUnavailableError(f"Gemini authentication failed: {resp.text}")
        if resp.status_code >= 500:
            raise ProviderError(f"Gemini server error ({resp.status_code}): {resp.text}")
        if resp.status_code != 200:
            raise ProviderError(f"Gemini request failed ({resp.status_code}): {resp.text}")

        try:
            data = resp.json()
            text = data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError, ValueError) as e:
            raise ProviderError(f"Gemini returned an unexpected response shape: {e}") from e

        return parse_json_safe(text)
