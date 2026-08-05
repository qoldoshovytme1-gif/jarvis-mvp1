"""
GPT Adapter (OpenAI)
=======================
Implements ILanguageModel using OpenAI's API.
"""

from core.interfaces import ILanguageModel
from providers.prompts import SYSTEM_PROMPT, parse_json_safe
from providers.exceptions import ProviderError, ProviderTimeoutError, ProviderUnavailableError


class GPTAdapter(ILanguageModel):
    def __init__(self, api_key: str, model: str = "gpt-4o", timeout: float = 20.0):
        self._api_key = api_key
        self._model = model
        self._timeout = timeout

    def ask(self, user_text: str, context: str = "") -> dict:
        if not self._api_key:
            raise ProviderUnavailableError("OpenAI: OPENAI_API_KEY is not configured.")

        try:
            from openai import OpenAI, APITimeoutError, APIConnectionError, AuthenticationError
        except ImportError as e:
            raise ProviderUnavailableError("OpenAI: 'openai' package is not installed.") from e

        full_prompt = f"{context}\n\nUser: {user_text}" if context else user_text

        try:
            client = OpenAI(api_key=self._api_key, timeout=self._timeout)
            response = client.chat.completions.create(
                model=self._model,
                max_tokens=500,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": full_prompt},
                ],
            )
            return parse_json_safe(response.choices[0].message.content)

        except APITimeoutError as e:
            raise ProviderTimeoutError(f"OpenAI request timed out: {e}") from e
        except APIConnectionError as e:
            raise ProviderUnavailableError(f"OpenAI unreachable: {e}") from e
        except AuthenticationError as e:
            raise ProviderUnavailableError(f"OpenAI authentication failed: {e}") from e
        except Exception as e:
            raise ProviderError(f"OpenAI request failed: {e}") from e
