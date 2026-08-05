"""
JARVIS Android Actions Module
-------------------------------
Real device actions via pyjnius (only works when running ON Android,
inside the built APK — will raise ImportError on desktop, which is
caught gracefully so you can still test the rest of the app on PC).

DESIGN NOTE (keeps the architecture's "Android has zero business
logic" rule): every function here is a dumb I/O primitive — given a
resolved phone number, dial it; given a package name, launch it. They
never decide WHICH contact "mom" refers to, or WHETHER a request is
allowed. That resolution logic lives in the IActionExecutor classes in
`core/adapters.py`, which call these primitives with already-resolved
values. This file may be swapped entirely (e.g. an iOS layer) without
Core changing a single line.
"""

IS_ANDROID = True
try:
    from jnius import autoclass, cast
    from android.permissions import request_permissions, Permission
except ImportError:
    IS_ANDROID = False


# Common app name -> Android package name. Lets "open telegram" /
# "open chrome" resolve instantly and reliably instead of depending on
# a fuzzy match against getInstalledApplications() (which is slow and
# can pick the wrong app when labels are ambiguous, e.g. multiple
# "Messages" apps). Falls back to the label-search below if the app
# isn't in this map or isn't installed under the expected package.
KNOWN_APP_PACKAGES = {
    "telegram": "org.telegram.messenger",
    "whatsapp": "com.whatsapp",
    "chrome": "com.android.chrome",
    "camera": "com.android.camera2",
    "settings": "com.android.settings",
    "gmail": "com.google.android.gm",
    "youtube": "com.google.android.youtube",
    "maps": "com.google.android.apps.maps",
    "google maps": "com.google.android.apps.maps",
    "phone": "com.android.dialer",
    "dialer": "com.android.dialer",
    "messages": "com.google.android.apps.messaging",
    "sms": "com.google.android.apps.messaging",
    "spotify": "com.spotify.music",
    "instagram": "com.instagram.android",
    "facebook": "com.facebook.katana",
    "gallery": "com.google.android.apps.photos",
    "photos": "com.google.android.apps.photos",
    "calculator": "com.google.android.calculator",
    "calendar": "com.google.android.calendar",
    "clock": "com.google.android.deskclock",
    "play store": "com.android.vending",
}


def _get_activity_and_context():
    PythonActivity = autoclass("org.kivy.android.PythonActivity")
    activity = PythonActivity.mActivity
    return activity, activity


def open_app(app_name: str) -> str:
    """Opens an installed app by name. Tries the known-package map
    first (fast, unambiguous), then falls back to scanning installed
    app labels for a case-insensitive substring match."""
    if not IS_ANDROID:
        return f"[DESKTOP MODE] Would open app: {app_name}"

    context, _ = _get_activity_and_context()
    pm = context.getPackageManager()
    key = app_name.strip().lower()

    known_pkg = KNOWN_APP_PACKAGES.get(key)
    if known_pkg:
        intent = pm.getLaunchIntentForPackage(known_pkg)
        if intent is not None:
            context.startActivity(intent)
            return f"Opening {app_name}."
        # Known package not installed on this device -- fall through to
        # the label search below in case it's installed under a
        # different/regional package id.

    packages = pm.getInstalledApplications(0)
    target_pkg = None
    for pkg in packages.toArray():
        label = pm.getApplicationLabel(pkg).toString()
        if key in label.lower():
            target_pkg = pkg.packageName
            break

    if not target_pkg:
        return f"Could not find an app matching '{app_name}'."

    intent = pm.getLaunchIntentForPackage(target_pkg)
    if intent is None:
        return f"Found '{app_name}' but it cannot be launched."

    context.startActivity(intent)
    return f"Opening {app_name}."


def open_settings(section: str = "") -> str:
    """Opens Android Settings, optionally a specific section
    ('wifi', 'bluetooth', 'display', ...). Unknown/blank section ->
    the main Settings screen."""
    if not IS_ANDROID:
        return f"[DESKTOP MODE] Would open settings: {section or 'main'}"

    Intent = autoclass("android.content.Intent")
    Settings = autoclass("android.provider.Settings")
    context, _ = _get_activity_and_context()

    section_actions = {
        "wifi": Settings.ACTION_WIFI_SETTINGS,
        "bluetooth": Settings.ACTION_BLUETOOTH_SETTINGS,
        "display": Settings.ACTION_DISPLAY_SETTINGS,
        "sound": Settings.ACTION_SOUND_SETTINGS,
        "apps": Settings.ACTION_APPLICATION_SETTINGS,
        "location": Settings.ACTION_LOCATION_SOURCE_SETTINGS,
        "battery": Settings.ACTION_BATTERY_SAVER_SETTINGS,
    }
    action = section_actions.get(section.strip().lower(), Settings.ACTION_SETTINGS)

    intent = Intent(action)
    intent.setFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
    context.startActivity(intent)
    return f"Opening settings{': ' + section if section else ''}."


def dial_number(phone_number: str, direct_call: bool = True) -> str:
    """Places (or prepares) a phone call to an already-resolved phone
    number. `direct_call=True` uses ACTION_CALL (requires CALL_PHONE
    permission, dials immediately). Falls back to ACTION_DIAL (opens
    the dialer pre-filled, no permission needed, user taps to confirm)
    if CALL_PHONE isn't granted -- safer default for an MVP so a
    misheard command can't place an unwanted call silently.
    """
    if not IS_ANDROID:
        return f"[DESKTOP MODE] Would call: {phone_number}"

    Intent = autoclass("android.content.Intent")
    Uri = autoclass("android.net.Uri")
    context, _ = _get_activity_and_context()

    action = Intent.ACTION_CALL if direct_call else Intent.ACTION_DIAL
    intent = Intent(action)
    intent.setData(Uri.parse(f"tel:{phone_number}"))
    intent.setFlags(Intent.FLAG_ACTIVITY_NEW_TASK)

    try:
        context.startActivity(intent)
        return f"Calling {phone_number}." if direct_call else f"Dialing {phone_number}."
    except Exception as e:
        # Most common cause: CALL_PHONE permission not granted yet.
        # Degrade to ACTION_DIAL instead of failing outright.
        if direct_call:
            return dial_number(phone_number, direct_call=False)
        return f"Could not start a call: {e}"


def send_sms(phone_number: str, message: str, silent: bool = False) -> str:
    """Sends an SMS to an already-resolved phone number.
    `silent=True` uses SmsManager to send directly in the background
    (requires SEND_SMS permission). Default is `silent=False`, which
    opens the native Messages app pre-filled instead -- an MVP-safe
    default so JARVIS never sends a message the user didn't see and
    confirm, until the permission + intent flow has been tested.
    """
    if not IS_ANDROID:
        return f"[DESKTOP MODE] Would text {phone_number}: {message}"

    if silent:
        try:
            SmsManager = autoclass("android.telephony.SmsManager")
            sms_manager = SmsManager.getDefault()
            sms_manager.sendTextMessage(phone_number, None, message, None, None)
            return f"Message sent to {phone_number}."
        except Exception as e:
            return f"Could not send SMS directly ({e}); opening Messages instead."

    Intent = autoclass("android.content.Intent")
    Uri = autoclass("android.net.Uri")
    context, _ = _get_activity_and_context()

    intent = Intent(Intent.ACTION_SENDTO)
    intent.setData(Uri.parse(f"smsto:{phone_number}"))
    intent.putExtra("sms_body", message)
    intent.setFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
    context.startActivity(intent)
    return f"Opening Messages to {phone_number} with your text ready."


def set_flashlight(on: bool) -> str:
    """Toggles the rear camera's torch via CameraManager (Android 6+).
    No dedicated permission needed for torch mode."""
    if not IS_ANDROID:
        return f"[DESKTOP MODE] Would turn flashlight {'on' if on else 'off'}"

    try:
        Context = autoclass("android.content.Context")
        context, _ = _get_activity_and_context()
        camera_manager = context.getSystemService(Context.CAMERA_SERVICE)
        camera_ids = camera_manager.getCameraIdList()
        if len(camera_ids) == 0:
            return "No camera with a flashlight was found."
        # Rear camera is conventionally id "0".
        camera_manager.setTorchMode(camera_ids[0], on)
        return f"Flashlight {'enabled' if on else 'disabled'}."
    except Exception as e:
        return f"Could not toggle flashlight: {e}"


def adjust_volume(direction: str, stream: str = "media") -> str:
    """Adjusts device volume. `direction`: 'up' | 'down' | 'mute' | 'max'.
    `stream`: 'media' | 'ring' | 'alarm' | 'call'."""
    if not IS_ANDROID:
        return f"[DESKTOP MODE] Would set {stream} volume: {direction}"

    Context = autoclass("android.content.Context")
    AudioManager = autoclass("android.media.AudioManager")
    context, _ = _get_activity_and_context()
    audio_manager = context.getSystemService(Context.AUDIO_SERVICE)

    stream_map = {
        "media": AudioManager.STREAM_MUSIC,
        "ring": AudioManager.STREAM_RING,
        "alarm": AudioManager.STREAM_ALARM,
        "call": AudioManager.STREAM_VOICE_CALL,
    }
    stream_type = stream_map.get(stream.strip().lower(), AudioManager.STREAM_MUSIC)

    try:
        if direction == "up":
            audio_manager.adjustStreamVolume(stream_type, AudioManager.ADJUST_RAISE, AudioManager.FLAG_SHOW_UI)
        elif direction == "down":
            audio_manager.adjustStreamVolume(stream_type, AudioManager.ADJUST_LOWER, AudioManager.FLAG_SHOW_UI)
        elif direction == "mute":
            audio_manager.adjustStreamVolume(stream_type, AudioManager.ADJUST_MUTE, AudioManager.FLAG_SHOW_UI)
        elif direction == "max":
            max_vol = audio_manager.getStreamMaxVolume(stream_type)
            audio_manager.setStreamVolume(stream_type, max_vol, AudioManager.FLAG_SHOW_UI)
        else:
            return f"Unknown volume direction '{direction}'."
        return f"{stream.capitalize()} volume set to {direction}."
    except Exception as e:
        return f"Could not adjust volume: {e}"


def media_control(action: str) -> str:
    """Sends a media-key event (play/pause/next/previous/stop) to
    whatever app currently holds media focus (Spotify, YouTube Music,
    etc.) via AudioManager.dispatchMediaKeyEvent -- works without
    needing to know which media app is active."""
    if not IS_ANDROID:
        return f"[DESKTOP MODE] Would send media control: {action}"

    Context = autoclass("android.content.Context")
    AudioManager = autoclass("android.media.AudioManager")
    KeyEvent = autoclass("android.view.KeyEvent")
    context, _ = _get_activity_and_context()
    audio_manager = context.getSystemService(Context.AUDIO_SERVICE)

    key_map = {
        "play": KeyEvent.KEYCODE_MEDIA_PLAY,
        "pause": KeyEvent.KEYCODE_MEDIA_PAUSE,
        "play_pause": KeyEvent.KEYCODE_MEDIA_PLAY_PAUSE,
        "next": KeyEvent.KEYCODE_MEDIA_NEXT,
        "previous": KeyEvent.KEYCODE_MEDIA_PREVIOUS,
        "stop": KeyEvent.KEYCODE_MEDIA_STOP,
    }
    keycode = key_map.get(action.strip().lower())
    if keycode is None:
        return f"Unknown media action '{action}'."

    try:
        down_event = KeyEvent(KeyEvent.ACTION_DOWN, keycode)
        up_event = KeyEvent(KeyEvent.ACTION_UP, keycode)
        audio_manager.dispatchMediaKeyEvent(down_event)
        audio_manager.dispatchMediaKeyEvent(up_event)
        return f"Media: {action}."
    except Exception as e:
        return f"Could not send media control: {e}"


def get_device_contacts(limit: int = 500):
    """Reads the phone's contact book via ContactsContract (requires
    READ_CONTACTS). Returns a list of {"display_name", "phone"} dicts
    for a ONE-TIME import into Memory's contacts cache (see
    Memory.bulk_import_contacts) -- Core never queries
    ContactsContract directly, keeping that Android-specific API
    isolated to this file.
    """
    if not IS_ANDROID:
        return []

    try:
        Context = autoclass("android.content.Context")
        ContactsContract = autoclass("android.provider.ContactsContract$CommonDataKinds$Phone")
        context, _ = _get_activity_and_context()
        resolver = context.getContentResolver()

        cursor = resolver.query(ContactsContract.CONTENT_URI, None, None, None, None)
        results = []
        if cursor is None:
            return results

        name_idx = cursor.getColumnIndex(ContactsContract.DISPLAY_NAME)
        number_idx = cursor.getColumnIndex(ContactsContract.NUMBER)

        count = 0
        while cursor.moveToNext() and count < limit:
            name = cursor.getString(name_idx)
            number = cursor.getString(number_idx)
            if name and number:
                results.append({"display_name": name, "phone": number})
                count += 1
        cursor.close()
        return results
    except Exception:
        return []


def launch_intent(action: str, data_uri: str = "", extras: dict = None, package: str = "") -> str:
    """Generic escape hatch: fires an arbitrary Android Intent by
    action string (e.g. "android.intent.action.VIEW"). Lets the
    Executor's action registry support one-off intents (open a maps
    URL, open a web link, open the camera in video mode, etc.) without
    needing a dedicated primitive function for every possible intent.
    """
    if not IS_ANDROID:
        return f"[DESKTOP MODE] Would launch intent: {action} {data_uri} {extras or {}}"

    Intent = autoclass("android.content.Intent")
    Uri = autoclass("android.net.Uri")
    context, _ = _get_activity_and_context()

    intent = Intent(action)
    if data_uri:
        intent.setData(Uri.parse(data_uri))
    if package:
        intent.setPackage(package)
    if extras:
        for k, v in extras.items():
            if isinstance(v, bool):
                intent.putExtra(k, v)
            elif isinstance(v, int):
                intent.putExtra(k, v)
            else:
                intent.putExtra(k, str(v))
    intent.setFlags(Intent.FLAG_ACTIVITY_NEW_TASK)

    try:
        context.startActivity(intent)
        return "Done."
    except Exception as e:
        return f"Could not launch intent: {e}"


def set_alarm(hour: int, minute: int, label: str = "JARVIS Alarm") -> str:
    """Uses Android's native AlarmClock intent (shows in the Clock app)."""
    if not IS_ANDROID:
        return f"[DESKTOP MODE] Would set alarm: {hour:02d}:{minute:02d} ({label})"

    Intent = autoclass("android.content.Intent")
    AlarmClock = autoclass("android.provider.AlarmClock")
    PythonActivity = autoclass("org.kivy.android.PythonActivity")

    intent = Intent(AlarmClock.ACTION_SET_ALARM)
    intent.putExtra(AlarmClock.EXTRA_HOUR, hour)
    intent.putExtra(AlarmClock.EXTRA_MINUTES, minute)
    intent.putExtra(AlarmClock.EXTRA_MESSAGE, label)
    intent.setFlags(Intent.FLAG_ACTIVITY_NEW_TASK)

    PythonActivity.mActivity.startActivity(intent)
    return f"Alarm set for {hour:02d}:{minute:02d}."


def notify(title: str, message: str) -> str:
    """Native Android notification via plyer (works cross-platform incl. desktop test)."""
    try:
        from plyer import notification as plyer_notify

        plyer_notify.notify(title=title, message=message, timeout=5)
        return "Notification sent."
    except Exception as e:
        return f"[DESKTOP MODE] Notification: {title} - {message} ({e})"


def request_android_permissions(on_complete=None):
    """Call once at app startup (inside main.py) before using actions
    above. Requests every permission the MVP's action set needs;
    individual actions still degrade gracefully (see dial_number,
    send_sms) if the user denies one of these at the OS prompt.
    `on_complete(permissions, results)` is an optional callback fired
    once the user has answered the permission dialog.
    """
    if IS_ANDROID:
        request_permissions([
            Permission.RECORD_AUDIO,
            Permission.INTERNET,
            Permission.POST_NOTIFICATIONS,
            Permission.CALL_PHONE,
            Permission.SEND_SMS,
            Permission.READ_CONTACTS,
            Permission.CAMERA,
            Permission.FOREGROUND_SERVICE,
        ], on_complete)
