"""
Adapters
==========
Adapter Pattern: wraps EXISTING, already-working modules (Memory,
LLMClient, search.search, android_layer.actions) so they satisfy the
new Core interfaces — WITHOUT modifying those modules' source code.

This file is the only place that imports the concrete implementations.
Core (Planner/Executor/Verifier/Orchestrator) never imports
`core.memory.Memory` or `core.llm_client.LLMClient` directly — it
receives them through these adapters via Dependency Injection.

If Memory or LLMClient's public methods ever change shape, this is
also the only file that needs to change to keep Core working.
"""

from typing import Optional

from core.interfaces import ILanguageModel, IMemoryRepository, ISearchProvider, IActionExecutor
from core.memory import Memory
from core.llm_client import LLMClient
from core import search as internet_search
from android_layer import actions as android_actions


# ---------------- LLM ----------------

class LLMClientAdapter(ILanguageModel):
    """The ILanguageModel instance Orchestrator's default composition
    injects into Planner. As of the Provider Layer, this delegates to
    `ProviderRouter` by default — which selects/retries/falls back
    across Claude, OpenAI, Gemini, OpenRouter, Local, and Mock purely
    from configuration (see core/config.py + providers/router.py).

    The old single-provider `core.llm_client.LLMClient` still exists
    untouched and can still be passed in explicitly (`client=...`) if
    ever needed — this adapter just no longer uses it by default, so
    Planner/Executor/Verifier/Orchestrator required ZERO changes to
    gain multi-provider routing.

    Import of ProviderRouter is local (inside __init__) to avoid a
    module-load-time dependency from core/ -> providers/ — the
    dependency only exists at composition time, not at import time.
    """

    def __init__(self, client: Optional[ILanguageModel] = None):
        if client is None:
            from providers.router import ProviderRouter
            client = ProviderRouter()
        self._client = client

    def ask(self, user_text: str, context: str = "") -> dict:
        return self._client.ask(user_text, context=context)


# ---------------- Memory ----------------

class MemoryRepositoryAdapter(IMemoryRepository):
    """Wraps the existing SQLite-backed Memory class."""

    def __init__(self, memory: Optional[Memory] = None):
        self._memory = memory or Memory()

    def add_message(self, role: str, content: str) -> None:
        self._memory.add_message(role, content)

    def get_recent_history(self, limit: int = 10) -> list:
        return self._memory.get_recent_history(limit)

    def build_context_string(self, history_limit: int = 6) -> str:
        return self._memory.build_context_string(history_limit)

    def set_fact(self, key: str, value: str) -> None:
        self._memory.set_fact(key, value)

    def get_fact(self, key: str) -> Optional[str]:
        return self._memory.get_fact(key)

    def get_contact(self, name: str) -> Optional[dict]:
        return self._memory.get_contact(name)

    def set_contact(self, name: str, phone: str) -> None:
        self._memory.set_contact(name, phone)

    def add_command(self, action_type: str, params: dict, result: str, success: bool) -> None:
        self._memory.add_command(action_type, params, result, success)

    def bulk_import_contacts(self, contacts: list) -> int:
        return self._memory.bulk_import_contacts(contacts)


# ---------------- Search ----------------

class SearchProviderAdapter(ISearchProvider):
    """Wraps the existing `core.search.search` function."""

    def search(self, query: str) -> str:
        return internet_search.search(query)


# ---------------- Action Executors ----------------
# Each concrete action gets its own class (Single Responsibility).
# All are registered into the Executor's action registry (see
# core/executor.py) keyed by the same `action_type` strings the LLM's
# SYSTEM_PROMPT already produces — nothing about the LLM prompt needs
# to change.

class ChatActionExecutor(IActionExecutor):
    """No real-world action — just passes the LLM's drafted reply
    straight through. Exists so "chat" is a first-class action_type
    like any other, keeping the Executor logic uniform.
    """

    def execute(self, params: dict) -> str:
        return params.get("reply", "")


class OpenAppActionExecutor(IActionExecutor):
    def execute(self, params: dict) -> str:
        return android_actions.open_app(params.get("app_name", ""))


class SetAlarmActionExecutor(IActionExecutor):
    def execute(self, params: dict) -> str:
        return android_actions.set_alarm(
            params.get("hour", 8),
            params.get("minute", 0),
            params.get("label", "JARVIS"),
        )


class NotifyActionExecutor(IActionExecutor):
    def execute(self, params: dict) -> str:
        return android_actions.notify(
            params.get("title", "JARVIS"), params.get("message", "")
        )


class WebSearchActionExecutor(IActionExecutor):
    def __init__(self, search_provider: Optional[ISearchProvider] = None):
        self._search_provider = search_provider or SearchProviderAdapter()

    def execute(self, params: dict) -> str:
        return self._search_provider.search(params.get("query", ""))


class OpenSettingsActionExecutor(IActionExecutor):
    def execute(self, params: dict) -> str:
        return android_actions.open_settings(params.get("section", ""))


class FlashlightActionExecutor(IActionExecutor):
    def execute(self, params: dict) -> str:
        state = params.get("state", "on")
        return android_actions.set_flashlight(str(state).lower() in ("on", "true", "1"))


class VolumeActionExecutor(IActionExecutor):
    def execute(self, params: dict) -> str:
        return android_actions.adjust_volume(
            params.get("direction", "up"), params.get("stream", "media")
        )


class MediaControlActionExecutor(IActionExecutor):
    def execute(self, params: dict) -> str:
        return android_actions.media_control(params.get("action", "play_pause"))


def _resolve_contact(memory: IMemoryRepository, name: str) -> Optional[dict]:
    """Shared contact-resolution logic (business logic -> lives in Core,
    not in android_layer). Tries an exact learned/imported match first;
    a real fuzzy-matching pass is a natural next iteration (see
    architecture notes) but out of scope for the MVP.
    """
    if not name:
        return None
    return memory.get_contact(name)


class CallContactActionExecutor(IActionExecutor):
    """Resolves a contact name to a phone number via Memory, then
    dials it through the Android primitive. If the name isn't known
    yet, fails with a clear message instead of guessing -- the user
    can teach it via `set_contact` (e.g. "remember mom's number is
    ...", wired through the LLM intent `remember_contact`).
    """

    def __init__(self, memory: IMemoryRepository):
        self._memory = memory

    def execute(self, params: dict) -> str:
        name = params.get("contact_name", "")
        contact = _resolve_contact(self._memory, name)
        if contact is None:
            # Raise (rather than return a string) so the Executor marks
            # this step as FAILED. Otherwise the Orchestrator would
            # prefer the LLM's optimistic reply_hint ("Calling Asad.")
            # over this honest outcome, telling the user a call happened
            # when it didn't.
            raise LookupError(
                f"I don't have a number saved for '{name}'. Tell me their number and I'll remember it."
            )
        return android_actions.dial_number(contact["phone"])


class SendSmsActionExecutor(IActionExecutor):
    def __init__(self, memory: IMemoryRepository):
        self._memory = memory

    def execute(self, params: dict) -> str:
        name = params.get("contact_name", "")
        message = params.get("message", "")
        contact = _resolve_contact(self._memory, name)
        if contact is None:
            raise LookupError(
                f"I don't have a number saved for '{name}'. Tell me their number and I'll remember it."
            )
        return android_actions.send_sms(contact["phone"], message)


class RememberContactActionExecutor(IActionExecutor):
    """Lets the user explicitly teach JARVIS a contact ("remember that
    Asad's number is 998901234567"), independent of the one-time bulk
    import from the phone's contacts book."""

    def __init__(self, memory: IMemoryRepository):
        self._memory = memory

    def execute(self, params: dict) -> str:
        name = params.get("contact_name", "")
        phone = params.get("phone", "")
        if not name or not phone:
            return "I need both a name and a phone number to remember a contact."
        self._memory.set_contact(name, phone)
        return f"Got it, I'll remember {name}'s number."


class ImportContactsActionExecutor(IActionExecutor):
    """One-time (or on-demand) bulk import of the phone's contact book
    into Memory's local contacts cache, via android_layer's read-only
    ContactsContract primitive."""

    def __init__(self, memory: IMemoryRepository):
        self._memory = memory

    def execute(self, params: dict) -> str:
        device_contacts = android_actions.get_device_contacts()
        if not device_contacts:
            return "No contacts found (or permission not granted)."
        imported = self._memory.bulk_import_contacts(device_contacts)
        return f"Imported {imported} new contact(s)."


class ControlAppActionExecutor(IActionExecutor):
    """Placeholder for the future Accessibility-based "open Telegram,
    search Asad, write Hello" capability (see
    android_layer/accessibility.py + core.interfaces.IUIController).
    Registered now so the Executor never fails with "No executor
    registered" if a future/misrouted intent asks for it -- returns a
    clear, honest message instead of a stack trace.
    """

    def execute(self, params: dict) -> str:
        return (
            "App-level control (tapping buttons/typing inside other apps) "
            "isn't implemented yet in this MVP -- it needs the Accessibility "
            "Service, which is the next planned iteration."
        )


def build_default_action_registry(memory: Optional[IMemoryRepository] = None) -> dict:
    """Factory: the default action_type -> IActionExecutor mapping.
    Passed into the Executor at composition time. Adding a new action
    later (e.g. "windows_shutdown", "phone_call") = adding one entry
    here + one new IActionExecutor class. Nothing else changes.

    `memory` is optional so existing callers/tests that don't need
    contact-aware actions keep working unchanged; Orchestrator's
    default composition always passes its own memory instance in.
    """
    memory = memory or MemoryRepositoryAdapter()

    return {
        "chat": ChatActionExecutor(),
        "open_app": OpenAppActionExecutor(),
        "set_alarm": SetAlarmActionExecutor(),
        "notify": NotifyActionExecutor(),
        "web_search": WebSearchActionExecutor(),
        "open_settings": OpenSettingsActionExecutor(),
        "flashlight": FlashlightActionExecutor(),
        "volume": VolumeActionExecutor(),
        "media_control": MediaControlActionExecutor(),
        "call_contact": CallContactActionExecutor(memory),
        "send_sms": SendSmsActionExecutor(memory),
        "remember_contact": RememberContactActionExecutor(memory),
        "import_contacts": ImportContactsActionExecutor(memory),
        "control_app": ControlAppActionExecutor(),
    }
