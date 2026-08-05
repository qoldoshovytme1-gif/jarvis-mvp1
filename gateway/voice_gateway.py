"""
Voice Gateway
===============
The real "JARVIS experience" described in the project brief:

    1. Always listen for the wake word ("Jarvis").
    2. On hearing it, greet the user ("Yes?" / "I'm listening.").
    3. Listen for one command, hand it to the Orchestrator.
    4. Speak the reply out loud.
    5. Go back to step 1 -- forever, with no button press required.

Same shape as CLIGateway (see gateway/cli_gateway.py): this class
knows nothing about Planner/Executor/Memory/LLM internals. It only
calls `orchestrator.handle(text)`. Its only two dependencies beyond
that are the STT/TTS I/O primitives in android_layer.voice -- it never
touches jnius/pyjnius directly, keeping Android-specific APIs isolated
to android_layer as the architecture requires.

This Gateway is meant to run inside the Foreground Service
(see service/main.py) so it keeps running after the user leaves the
app UI, per the "no microphone button, no manual activation" MVP
requirement.
"""

import random
import threading

from gateway.interfaces import IGateway
from core.orchestrator import Orchestrator
from core.logger import get_logger
from android_layer import voice as android_voice

log = get_logger("gateway.voice")

WAKE_WORDS = ("jarvis",)
GREETINGS = ("Yes?", "I'm listening.", "Go ahead.")
NO_INPUT_REPLY = "I didn't catch a command, going back to sleep."


class VoiceGateway(IGateway):
    def __init__(self, orchestrator: Orchestrator, stop_event: threading.Event = None):
        self._orchestrator = orchestrator
        self._tts = android_voice.TextToSpeech()
        # Shared with whoever owns this Gateway's lifecycle (e.g. the
        # Service) so it can be told to stop cleanly instead of being
        # killed mid-recognition.
        self._stop_event = stop_event or threading.Event()

    def stop(self) -> None:
        self._stop_event.set()

    def start(self) -> None:
        log.info("Voice Gateway started -- listening for wake word.")

        while not self._stop_event.is_set():
            heard_wake_word = android_voice.listen_for_wake_word(
                wake_words=WAKE_WORDS, stop_event=self._stop_event
            )
            if not heard_wake_word:
                continue  # stop_event was set mid-loop

            log.info("Wake word detected.")
            self._tts.speak(random.choice(GREETINGS))

            command_text = android_voice.listen_once(timeout_seconds=8)
            if not command_text:
                log.info("No command heard after wake word.")
                self._tts.speak(NO_INPUT_REPLY)
                continue

            log.info("Command heard: %s", command_text)
            try:
                reply = self._orchestrator.handle(command_text)
            except Exception:
                log.exception("Orchestrator failed to handle voice command.")
                reply = "Something went wrong handling that."

            self._tts.speak(reply)

        log.info("Voice Gateway stopped.")
