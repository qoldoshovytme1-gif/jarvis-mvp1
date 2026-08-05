"""
CLI Gateway
=============
First concrete Gateway implementation. Reads text from the terminal,
hands it to the Orchestrator, prints the reply, and loops until the
user exits.

This class knows NOTHING about Planner, Executor, Memory, or the LLM —
it only calls `orchestrator.handle(text)`. That single dependency is
what makes it trivial to write `TelegramGateway`, `RestGateway`,
`WebSocketGateway`, and `AndroidGateway` later: same shape, different
transport, same one line calling into Core.
"""

from gateway.interfaces import IGateway
from core.orchestrator import Orchestrator
from core.logger import get_logger

log = get_logger("gateway.cli")

EXIT_COMMANDS = {"exit", "quit"}


class CLIGateway(IGateway):
    def __init__(self, orchestrator: Orchestrator):
        self._orchestrator = orchestrator

    def start(self) -> None:
        log.info("CLI Gateway started.")
        print("JARVIS ready. Type 'exit' to quit.\n")

        while True:
            try:
                user_text = input("You: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nJARVIS: Shutting down.")
                break

            if not user_text:
                continue

            if user_text.lower() in EXIT_COMMANDS:
                print("JARVIS: Shutting down.")
                break

            reply = self._orchestrator.handle(user_text)
            print(f"JARVIS: {reply}\n")

        log.info("CLI Gateway stopped.")
