"""
JARVIS Foreground Service Entry Point
========================================
python-for-android service process, declared in buildozer.spec:

    services = jarvisvoice:service/main.py:foreground

The ":foreground" suffix tells p4a to call startForeground() and post
the required persistent notification automatically -- this is what
lets JARVIS keep listening after the user leaves the app UI or the
screen locks, satisfying the MVP requirement: "no microphone button,
no manual activation, the assistant must stay alive."

This file contains ZERO business logic, same as run_cli.py: it is a
Composition Root. Build an Orchestrator, hand it to a Gateway
(VoiceGateway instead of CLIGateway), run it. Core is never touched.
"""

import traceback

from core.orchestrator import Orchestrator
from gateway.voice_gateway import VoiceGateway
from core.logger import get_logger

log = get_logger("service.main")


def _configure_service():
    """Best-effort: survive being killed under memory pressure. Import
    of jnius/android is done here (not at module top-level) so this
    file can still be syntax/unit-tested on desktop without pyjnius
    installed.
    """
    try:
        from jnius import autoclass

        PythonService = autoclass("org.kivy.android.PythonService")
        PythonService.mService.setAutoRestartService(True)
    except Exception:
        log.warning("Could not configure service auto-restart (expected on desktop).")


def main():
    _configure_service()

    orchestrator = Orchestrator()
    gateway = VoiceGateway(orchestrator)

    log.info("JARVIS foreground service starting voice loop.")
    try:
        gateway.start()
    except Exception:
        log.error("Voice loop crashed:\n%s", traceback.format_exc())


if __name__ == "__main__":
    main()
