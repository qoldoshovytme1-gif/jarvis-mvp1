"""
Mock Provider
===============
No network calls, no API key, always succeeds. Two jobs:

1. Offline development/testing — set JARVIS_LLM_PROVIDER=mock and the
   whole Core/Gateway pipeline runs without any real API.
2. The Router's last-resort safety net — automatically appended to
   the end of the fallback chain (see providers/router.py) so JARVIS
   never hard-crashes even if every real provider is unreachable.
"""

from core.interfaces import ILanguageModel


class MockProvider(ILanguageModel):
    def ask(self, user_text: str, context: str = "") -> dict:
        return {
            "intent": "chat",
            "action_params": {},
            "reply": f"[MOCK] You said: {user_text}",
        }
