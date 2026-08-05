"""
JARVIS LLM Client
------------------
Provider-agnostic wrapper. Core never imports Anthropic/OpenAI directly —
it only talks to `LLMClient`. Swapping providers = editing this file only.

Set env vars before running:
    export JARVIS_LLM_PROVIDER=claude   # or "openai"
    export ANTHROPIC_API_KEY=...
    export OPENAI_API_KEY=...
"""

import os
import json

# Single source of truth for the intent-classification prompt lives in
# providers/prompts.py (shared by every ProviderRouter adapter). This
# legacy single-provider client re-uses it so the two never drift out
# of sync when new intents/actions are added.
from providers.prompts import SYSTEM_PROMPT


class LLMClient:
    def __init__(self, provider: str = None):
        self.provider = provider or os.environ.get("JARVIS_LLM_PROVIDER", "claude")

    def ask(self, user_text: str, context: str = "") -> dict:
        if self.provider == "claude":
            raw = self._ask_claude(user_text, context)
        elif self.provider == "openai":
            raw = self._ask_openai(user_text, context)
        else:
            raise ValueError(f"Unknown LLM provider: {self.provider}")

        return self._parse_json_safe(raw)

    # ---------------- Providers ----------------

    def _ask_claude(self, user_text: str, context: str) -> str:
        import anthropic

        client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        full_prompt = f"{context}\n\nUser: {user_text}" if context else user_text

        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=500,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": full_prompt}],
        )
        return response.content[0].text

    def _ask_openai(self, user_text: str, context: str) -> str:
        from openai import OpenAI

        client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        full_prompt = f"{context}\n\nUser: {user_text}" if context else user_text

        response = client.chat.completions.create(
            model="gpt-4o",
            max_tokens=500,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": full_prompt},
            ],
        )
        return response.choices[0].message.content

    # ---------------- Helpers ----------------

    def _parse_json_safe(self, raw: str) -> dict:
        cleaned = raw.strip().replace("```json", "").replace("```", "").strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            # Fallback: treat the whole thing as plain chat so JARVIS never crashes
            return {"intent": "chat", "action_params": {}, "reply": raw}
