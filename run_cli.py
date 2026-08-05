"""
JARVIS Entry Point — CLI Gateway
===================================
Composition Root for running JARVIS via the terminal (works on
desktop AND inside Termux — no Android-only dependencies here).

Run:
    python run_cli.py

Swapping channels later means adding `run_telegram.py`,
`run_rest.py`, `run_websocket.py`, each doing the same two things:
build an Orchestrator, hand it to that channel's Gateway. Core
(`core/orchestrator.py` and everything it depends on) is never
touched.
"""

from core.orchestrator import Orchestrator
from gateway.cli_gateway import CLIGateway


def main():
    orchestrator = Orchestrator()
    gateway = CLIGateway(orchestrator)
    gateway.start()


if __name__ == "__main__":
    main()
