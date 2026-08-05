"""
JARVIS Voice Module
---------------------
Low-level Speech-to-Text / Text-to-Speech I/O primitives ONLY. This
file follows the same rule as android_layer/actions.py: no business
logic, no calls into core.orchestrator. It exposes:

    - TextToSpeech            : speak(text)
    - listen_once()           : one blocking STT capture -> str
    - listen_for_wake_word()  : blocking loop, returns True as soon as
                                 one of `wake_words` is heard (or False
                                 on timeout/stop)

The actual "listen for wake word -> greet -> listen for command ->
run it -> speak reply -> repeat" conversation loop is a Gateway
(see gateway/voice_gateway.py), exactly like CLIGateway is for the
terminal -- Gateways are allowed to call the Orchestrator, Android
primitives are not.

On Android (built APK): uses native android.speech.SpeechRecognizer +
android.speech.tts.TextToSpeech via pyjnius.
On Desktop (fast iteration before building the APK): falls back to
`speech_recognition` (mic) + `pyttsx3` (offline TTS), if installed.
"""

import threading
import time

IS_ANDROID = True
try:
    from jnius import autoclass, PythonJavaClass, java_method
except ImportError:
    IS_ANDROID = False


# ---------------- Text to Speech ----------------

class TextToSpeech:
    def __init__(self):
        if IS_ANDROID:
            TTS = autoclass("android.speech.tts.TextToSpeech")
            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            self._tts = TTS(PythonActivity.mActivity, None)
        else:
            try:
                import pyttsx3
                self._engine = pyttsx3.init()
            except Exception:
                self._engine = None

    def speak(self, text: str):
        if not text:
            return
        if IS_ANDROID:
            Locale = autoclass("java.util.Locale")
            self._tts.setLanguage(Locale.US)
            self._tts.speak(text, 0, None, None)  # 0 = QUEUE_FLUSH
        else:
            if self._engine:
                self._engine.say(text)
                self._engine.runAndWait()
            else:
                print(f"[TTS not available] JARVIS would say: {text}")


# ---------------- Android native STT bridge ----------------

def _run_on_ui_thread(fn):
    """SpeechRecognizer MUST be created/started/stopped on the main UI
    thread, but our wake-word loop runs on a background thread (so it
    doesn't block the Kivy UI or the foreground Service). This posts
    `fn` onto the UI thread via Activity.runOnUiThread and blocks the
    caller until it has run, using a tiny Runnable bridge class.
    """
    PythonActivity = autoclass("org.kivy.android.PythonActivity")
    activity = PythonActivity.mActivity

    class _Runnable(PythonJavaClass):
        __javainterfaces__ = ["java/lang/Runnable"]
        __javacontext__ = "app"

        def __init__(self, target):
            super().__init__()
            self._target = target

        @java_method("()V")
        def run(self):
            self._target()

    activity.runOnUiThread(_Runnable(fn))


if IS_ANDROID:
    class _RecognitionListener(PythonJavaClass):
        """Bridges Java's RecognitionListener callbacks back into Python.
        One instance is used per recognition session (see
        `_android_recognize`)."""

        __javainterfaces__ = ["android/speech/RecognitionListener"]
        __javacontext__ = "app"

        def __init__(self, on_result, on_error, on_partial=None):
            super().__init__()
            self._on_result = on_result
            self._on_error = on_error
            self._on_partial = on_partial

        @java_method("(Landroid/os/Bundle;)V")
        def onReadyForSpeech(self, params):
            pass

        @java_method("()V")
        def onBeginningOfSpeech(self):
            pass

        @java_method("(F)V")
        def onRmsChanged(self, rmsdB):
            pass

        @java_method("([B)V")
        def onBufferReceived(self, buffer):
            pass

        @java_method("()V")
        def onEndOfSpeech(self):
            pass

        @java_method("(I)V")
        def onError(self, error):
            self._on_error(error)

        @java_method("(Landroid/os/Bundle;)V")
        def onResults(self, results):
            SpeechRecognizer = autoclass("android.speech.SpeechRecognizer")
            matches = results.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
            text = matches.get(0) if matches is not None and matches.size() > 0 else ""
            self._on_result(text)

        @java_method("(Landroid/os/Bundle;)V")
        def onPartialResults(self, partialResults):
            if self._on_partial is None:
                return
            SpeechRecognizer = autoclass("android.speech.SpeechRecognizer")
            matches = partialResults.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
            if matches is not None and matches.size() > 0:
                self._on_partial(matches.get(0))

        @java_method("(ILandroid/os/Bundle;)V")
        def onEvent(self, eventType, params):
            pass


def _android_recognize(timeout_seconds: float, partial_callback=None) -> str:
    """Runs exactly one native SpeechRecognizer session and blocks until
    it finishes (result, error, or timeout). Safe to call from any
    thread -- internally hops to the UI thread as required by the
    Android Speech API.
    """
    SpeechRecognizer = autoclass("android.speech.SpeechRecognizer")
    RecognizerIntent = autoclass("android.speech.RecognizerIntent")
    Intent = autoclass("android.content.Intent")
    Locale = autoclass("java.util.Locale")
    PythonActivity = autoclass("org.kivy.android.PythonActivity")

    done = threading.Event()
    result_holder = {"text": "", "error": None}

    def on_result(text):
        result_holder["text"] = text
        done.set()

    def on_error(error_code):
        result_holder["error"] = error_code
        done.set()

    listener = _RecognitionListener(on_result, on_error, partial_callback)
    recognizer_holder = {}

    def start_session():
        recognizer = SpeechRecognizer.createSpeechRecognizer(PythonActivity.mActivity)
        recognizer.setRecognitionListener(listener)
        recognizer_holder["recognizer"] = recognizer

        intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH)
        intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
        intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE, Locale.getDefault())
        intent.putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, partial_callback is not None)
        intent.putExtra(RecognizerIntent.EXTRA_CALLING_PACKAGE, PythonActivity.mActivity.getPackageName())
        recognizer.startListening(intent)

    _run_on_ui_thread(start_session)

    finished_in_time = done.wait(timeout_seconds)

    def stop_session():
        recognizer = recognizer_holder.get("recognizer")
        if recognizer is not None:
            try:
                recognizer.stopListening()
                recognizer.destroy()
            except Exception:
                pass

    _run_on_ui_thread(stop_session)

    if not finished_in_time:
        return ""
    if result_holder["error"] is not None:
        # Common non-fatal codes: ERROR_NO_MATCH(7), ERROR_SPEECH_TIMEOUT(6).
        return ""
    return result_holder["text"]


# ---------------- Public STT API ----------------

def listen_once(timeout_seconds: int = 6) -> str:
    """Blocking call: listens once and returns transcribed text (empty
    string if nothing was understood or the mic timed out)."""
    if IS_ANDROID:
        try:
            return _android_recognize(timeout_seconds)
        except Exception as e:
            print(f"[STT error] {e}")
            return ""
    else:
        try:
            import speech_recognition as sr

            recognizer = sr.Recognizer()
            with sr.Microphone() as source:
                print("Listening...")
                audio = recognizer.listen(source, timeout=timeout_seconds)
            return recognizer.recognize_google(audio)
        except Exception as e:
            print(f"[STT not available] {e}")
            return ""


def listen_for_wake_word(wake_words=("jarvis",), session_seconds: int = 8, stop_event: threading.Event = None) -> bool:
    """Blocking loop of short recognition sessions, checking each
    transcript for any of `wake_words` (case-insensitive substring
    match). Returns True the moment a wake word is heard, False if
    `stop_event` is set (used to cleanly shut the loop down, e.g. when
    the Service is stopped).

    NOTE (honest MVP limitation, documented for the next session too):
    Android's SpeechRecognizer is not a true always-on/offline wake
    word engine like Porcupine/Snowboy -- each session opens the mic
    for a few seconds, transcribes, and must be restarted. This loop
    restarts it back-to-back so listening is continuous from the
    user's perspective, but there are brief (sub-second) gaps between
    sessions where speech could theoretically be missed. Swapping in a
    dedicated offline wake-word engine is the natural next iteration
    and would only require replacing this one function.
    """
    stop_event = stop_event or threading.Event()

    while not stop_event.is_set():
        if IS_ANDROID:
            try:
                text = _android_recognize(session_seconds)
            except Exception as e:
                print(f"[wake word listener error] {e}")
                time.sleep(1)
                continue
        else:
            text = listen_once(timeout_seconds=session_seconds)

        if text and any(w.lower() in text.lower() for w in wake_words):
            return True

        # No match this round -- loop immediately restarts listening.
        # Tiny sleep only when nothing was heard at all, to avoid a
        # tight spin loop against a broken/unavailable recognizer.
        if not text:
            time.sleep(0.2)

    return False
