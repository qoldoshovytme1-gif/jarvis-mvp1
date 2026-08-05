"""
Local Adapter
===============
Talks to a locally-running model server (e.g. Ollama at
http://localhost:11434) instead of a cloud API — useful for
zero-cost testing, offline use, or privacy-sensitive requests.

If nothing is running locally this fails fast with
ProviderUnavailableError (connection refused), which the Router
treats as "skip to the next provider" rather than "retry a few
times" — retrying a server that isn't running wastes time.
"""

import requests

from core.interfaces import ILanguageModel
from providers.prompts import SYSTEM_PROMPT, parse_json_safe
from providers.exceptions import ProviderError, ProviderTimeoutError, ProviderUnavailableError


class LocalAdapter(ILanguageModel):
    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "llama3",
        timeout: float = 20.0,
    ):
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout = timeout

    def ask(self, user_text: str, context: str = "") -> dict:
        full_prompt = f"{SYSTEM_PROMPT}\n\n{context}\n\nUser: {user_text}"

        try:
            resp = requests.post(
                f"{self._base_url}/api/generate",
                json={"model": self._model, "prompt": full_prompt, "stream": False},
                timeout=self._timeout,
            )
        except requests.Timeout as e:
            raise ProviderTimeoutError(f"Local model timed out: {e}") from e
        except requests.ConnectionError as e:
            raise ProviderUnavailableError(f"Local model server unreachable: {e}") from e

        if resp.status_code != 200:
            raise ProviderError(f"Local model request failed ({resp.status_code}): {resp.text}")

        try:
            text = resp.json()["response"]
        except (KeyError, ValueError) as e:
            raise ProviderError(f"Local model returned an unexpected response shape: {e}") from e

        return parse_json_safe(text)
