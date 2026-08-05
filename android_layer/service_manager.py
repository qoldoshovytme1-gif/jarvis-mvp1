"""
Foreground Service Manager
=============================
Starts/stops the JARVIS background voice service (service/main.py)
from the main Activity (main.py). This is the only file that needs to
know the generated Android service class name -- everything else just
calls `start_voice_service()` / `stop_voice_service()`.

IMPORTANT (needs on-device verification -- see HANDOVER.md):
python-for-android auto-generates a Java Service class from the
`services =` line in buildozer.spec. The generated class name follows
the pattern:
    <package.domain>.<package.name>.Service<ServiceNameCapitalized>

For this project's buildozer.spec (package.domain=org.jarvis,
package.name=jarvis, services=jarvisvoice:service/main.py:foreground),
that resolves to `org.jarvis.jarvis.ServiceJarvisvoice`. p4a's exact
capitalization rule has varied slightly across versions -- if
`start_voice_service()` logs a ClassNotFoundException on first device
run, check `<build>/dists/jarvis/src/main/java/org/jarvis/jarvis/`
for the actual generated class name and update `_SERVICE_CLASS` below.
That is the ONLY file that needs to change.
"""

IS_ANDROID = True
try:
    from jnius import autoclass
except ImportError:
    IS_ANDROID = False

_SERVICE_CLASS = "org.jarvis.jarvis.ServiceJarvisvoice"


def start_voice_service(argument: str = "") -> None:
    """Launches the foreground service that runs the wake-word +
    conversation loop (gateway.voice_gateway.VoiceGateway) so it keeps
    running after the user backgrounds the app."""
    if not IS_ANDROID:
        print("[DESKTOP MODE] Would start JARVIS foreground service.")
        return

    try:
        service = autoclass(_SERVICE_CLASS)
        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        service.start(PythonActivity.mActivity, argument)
    except Exception as e:
        print(f"[service_manager] Could not start foreground service: {e}")


def stop_voice_service() -> None:
    if not IS_ANDROID:
        print("[DESKTOP MODE] Would stop JARVIS foreground service.")
        return

    try:
        service = autoclass(_SERVICE_CLASS)
        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        service.stop(PythonActivity.mActivity)
    except Exception as e:
        print(f"[service_manager] Could not stop foreground service: {e}")
