"""
Core Interfaces (Contracts)
=============================
This file defines the abstract contracts every module must satisfy to
plug into the Core. The Core NEVER imports a concrete implementation
directly (e.g. `LLMClient`, `Memory`) — it only depends on these
interfaces. Concrete classes are wired in at startup via Dependency
Injection (see `core/composition.py`, added when we wire the Gateway).

This is what makes the system provider-agnostic and future-proof:
- Swapping Claude -> GPT -> a local model = new class implementing
  `ILanguageModel`. Core code does not change.
- Swapping SQLite -> Postgres = new class implementing
  `IMemoryRepository`. Core code does not change.
- Adding Windows control later = new class implementing
  `IActionExecutor`, registered in the Executor's registry. Core code
  does not change.

Design pattern: Strategy Pattern (interchangeable algorithms/behavior)
+ Repository Pattern (IMemoryRepository abstracts data access).
"""

from abc import ABC, abstractmethod
from typing import Optional, Protocol, runtime_checkable, Callable, Any


@runtime_checkable
class ILanguageModel(Protocol):
    """Contract for any AI provider (Claude, GPT, Gemini, local model...).

    Must return a dict shaped like:
        {"intent": str, "action_params": dict, "reply": str}
    """

    def ask(self, user_text: str, context: str = "") -> dict:
        ...


@runtime_checkable
class IMemoryRepository(Protocol):
    """Contract for long-term + short-term memory storage.

    Repository Pattern: Core never writes SQL / touches storage
    directly. It only calls these methods.
    """

    def add_message(self, role: str, content: str) -> None:
        ...

    def get_recent_history(self, limit: int = 10) -> list:
        ...

    def build_context_string(self, history_limit: int = 6) -> str:
        ...

    def set_fact(self, key: str, value: str) -> None:
        ...

    def get_fact(self, key: str) -> Optional[str]:
        ...

    def get_contact(self, name: str) -> Optional[dict]:
        """Returns {"display_name": str, "phone": str} or None."""
        ...

    def set_contact(self, name: str, phone: str) -> None:
        ...

    def add_command(self, action_type: str, params: dict, result: str, success: bool) -> None:
        """Records an executed device action so future LLM context and
        the Verifier's audit trail both have visibility into what JARVIS
        actually did (separate from the plain chat transcript)."""
        ...

    def bulk_import_contacts(self, contacts: list) -> int:
        """Imports [{"display_name", "phone"}, ...] from the device's
        contact book, skipping names already known. Returns the count
        of newly-added contacts."""
        ...


@runtime_checkable
class ISearchProvider(Protocol):
    """Contract for internet search capability."""

    def search(self, query: str) -> str:
        ...


class IActionExecutor(ABC):
    """Contract for any executable action (open_app, set_alarm, notify,
    web_search, and later: windows_control, phone_control actions...).

    Each concrete action is its own class (Single Responsibility) and
    is registered into the Executor's registry under an `action_type`
    key — see `core/executor.py`.
    """

    @abstractmethod
    def execute(self, params: dict) -> str:
        """Runs the action and returns a human-readable result string."""
        ...


class IUIController(ABC):
    """Contract for controlling OTHER apps' UI (tap a button, type into
    a field, read what's on screen) via Android's Accessibility API --
    what "Open Telegram, search Asad, write Hello" needs.

    NOT implemented in this MVP (the project brief explicitly scopes
    complex automation out of this phase). This interface exists now,
    ahead of the implementation, specifically so the architecture
    already supports it per the project rules ("architecture must
    already support this") -- a concrete `AccessibilityUIController`
    can be added later and registered as an IActionExecutor exactly
    like every other action, with zero changes to Planner, Executor,
    Verifier, or Orchestrator.

    Implementing this for real requires a custom Java
    AccessibilityService class (python-for-android cannot define one
    in pure Python), declared in AndroidManifest.xml with
    BIND_ACCESSIBILITY_SERVICE + an accessibility_service_config.xml
    resource, and the user manually enabling it in Android's
    Accessibility settings (Android does not allow silently
    self-enabling this permission). See HANDOVER.md for the concrete
    next-session plan.
    """

    @abstractmethod
    def find_and_tap(self, label: str) -> bool:
        """Finds an on-screen element whose text/description matches
        `label` in the currently foregrounded app and taps it."""
        ...

    @abstractmethod
    def type_text(self, text: str) -> bool:
        """Types `text` into the currently focused input field."""
        ...

    @abstractmethod
    def read_screen(self) -> str:
        """Returns a plain-text dump of the current screen's visible
        text nodes, for the Planner/LLM to reason over."""
        ...


class IEventBus(ABC):
    """Contract for the internal event bus.

    MVP implementation is in-process/in-memory (see `core/event_bus.py`).
    Because Core only depends on this interface, the in-memory bus can
    be swapped for Redis Streams / NATS later (for a real distributed
    deployment) without touching Planner, Executor, Verifier, or
    Orchestrator code.
    """

    @abstractmethod
    def publish(self, event_type: str, payload: dict) -> None:
        ...

    @abstractmethod
    def subscribe(self, event_type: str, handler: Callable[[dict], Any]) -> None:
        ...
