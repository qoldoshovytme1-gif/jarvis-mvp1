"""
Gateway Interface
===================
Contract every Gateway implementation must satisfy — CLI today, then
Android, Telegram, WebSocket, and REST later. A Gateway's ONLY job is
translating its own I/O format (terminal text, a Telegram update, an
HTTP request, a WebSocket frame, an Android UI event) into a plain
string, handing it to the Orchestrator, and translating the plain
string reply back into whatever that channel needs.

A Gateway NEVER talks to Planner, Executor, Memory, or any other Core
internals directly — only to `Orchestrator.handle(text) -> str`. This
is what lets every future channel share one brain (per the project's
"one JARVIS, many interfaces" principle) without Core ever knowing
which channel a message came from.

Design pattern: this is the same Strategy Pattern used for
IActionExecutor and ILanguageModel — each Gateway is an interchangeable
strategy for "how input/output reaches the user."
"""

from abc import ABC, abstractmethod


class IGateway(ABC):
    @abstractmethod
    def start(self) -> None:
        """Begins listening for input on this channel. For request/response
        channels (REST) this may just register routes instead of blocking;
        for loop-based channels (CLI, Telegram polling) this blocks until
        the session ends.
        """
        ...
