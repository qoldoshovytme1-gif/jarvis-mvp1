"""
JARVIS MVP - Main App (Kivy)
------------------------------
Minimal UI: a chat log + a text input (works everywhere, including
desktop, before/without native voice). There is intentionally NO mic
button and NO manual "start listening" action -- per the MVP UX spec,
JARVIS starts a foreground background service on launch that
continuously listens for the wake word ("Jarvis") and handles full
conversations hands-free (see service/main.py + gateway/voice_gateway.py).
This screen is a status/typing-fallback surface, not the primary input.

Run on desktop for fast testing:
    python main.py
(On desktop, the background voice service doesn't start -- pyjnius
isn't available -- so use the text box to test the Core/LLM/Memory
pipeline. The full hands-free loop only runs inside the built APK.)

Build as Android APK:
    buildozer android debug
"""

import threading

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.scrollview import ScrollView
from kivy.clock import mainthread

from core.orchestrator import Orchestrator
from android_layer.voice import TextToSpeech, IS_ANDROID
from android_layer.actions import request_android_permissions
from android_layer import service_manager


class JarvisRoot(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(orientation="vertical", **kwargs)

        self.orchestrator = Orchestrator()
        self.tts = TextToSpeech()

        self.scroll = ScrollView(size_hint=(1, 0.9))
        status = (
            "JARVIS ready. Listening in the background for \"Jarvis\"...\n"
            if IS_ANDROID
            else "JARVIS ready (desktop mode -- type below to test).\n"
        )
        self.log_label = Label(
            text=status, size_hint_y=None, valign="top", halign="left"
        )
        self.log_label.bind(texture_size=self._update_label_height)
        self.scroll.add_widget(self.log_label)
        self.add_widget(self.scroll)

        input_row = BoxLayout(size_hint=(1, 0.1))
        self.text_input = TextInput(multiline=False)
        self.text_input.bind(on_text_validate=self.on_submit)
        input_row.add_widget(self.text_input)

        send_btn = Button(text="Send", size_hint=(0.2, 1))
        send_btn.bind(on_press=self.on_submit)
        input_row.add_widget(send_btn)
        self.add_widget(input_row)

    def _update_label_height(self, instance, size):
        instance.height = size[1]
        instance.text_size = (instance.width, None)

    def on_submit(self, *args):
        text = self.text_input.text.strip()
        if not text:
            return
        self.text_input.text = ""
        self._append_log(f"You: {text}")
        threading.Thread(target=self._process, args=(text,), daemon=True).start()

    def _process(self, text: str):
        reply = self.orchestrator.handle(text)
        self._append_log(f"JARVIS: {reply}")
        self.tts.speak(reply)

    @mainthread
    def _append_log(self, line: str):
        self.log_label.text += f"\n{line}"


class JarvisApp(App):
    def build(self):
        # Permission callback starts the background voice service only
        # AFTER the user has answered the permission dialog -- starting
        # it before RECORD_AUDIO is granted would just loop on silent
        # failures.
        request_android_permissions(on_complete=self._on_permissions_result)
        return JarvisRoot()

    def _on_permissions_result(self, permissions, grant_results):
        # Runs on Android regardless of whether every permission was
        # granted -- the voice loop itself degrades per-feature (e.g.
        # dial_number falls back to ACTION_DIAL if CALL_PHONE was
        # denied), so we still start the hands-free service.
        service_manager.start_voice_service()

    def on_stop(self):
        service_manager.stop_voice_service()


if __name__ == "__main__":
    JarvisApp().run()
