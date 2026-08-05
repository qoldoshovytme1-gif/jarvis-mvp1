# JARVIS MVP — Development Handover

Date of this pass: continuation session (Cody/Claude), following the
original architecture-approved brief. **Architecture was NOT changed.**
Everything below is additive, using the same patterns that already
existed (Adapter, Strategy, DI, Repository, Event Bus).

## 1. What was ALREADY done before this session

Core, Planner, Executor, Verifier, EventBus, Gateway (CLI), Provider
Router + 5 provider adapters (Claude/OpenAI/Gemini/OpenRouter/Local) +
Mock fallback, Config, Logging, SQLite Memory (facts + conversation),
basic Android abstraction (open_app, set_alarm, notify), Kivy UI,
Buildozer config. Desktop CLI (`python run_cli.py`) worked end-to-end
with a real LLM provider.

## 2. What THIS session added

| Area | File(s) | Status |
|---|---|---|
| Native STT (SpeechRecognizer bridge) | `android_layer/voice.py` | Written, **not yet run on a real device** |
| Wake word loop ("Jarvis") | `android_layer/voice.py: listen_for_wake_word()` | Written, session-restart approach (see limitation below) |
| Conversation Gateway | `gateway/voice_gateway.py` | New `IGateway` implementation, wake word -> greet -> command -> reply -> repeat |
| Foreground Service | `service/main.py`, `android_layer/service_manager.py`, `buildozer.spec` (`services=` line) | Written, **class name needs on-device verification** (see §4) |
| App auto-start, no mic button | `main.py` | Rewritten: starts the service after permissions are granted, chat box is now a fallback/debug surface only |
| Android Controller expansion | `android_layer/actions.py` | `dial_number`, `send_sms`, `open_settings`, `set_flashlight`, `adjust_volume`, `media_control`, `get_device_contacts`, `launch_intent`, known-app package map |
| New action executors | `core/adapters.py` | `call_contact`, `send_sms`, `open_settings`, `flashlight`, `volume`, `media_control`, `remember_contact`, `import_contacts`, `control_app` (stub) |
| LLM intent prompt | `providers/prompts.py` (+ `core/llm_client.py` now imports it instead of duplicating) | Extended with all new intents + guidance text |
| Memory | `core/memory.py`, `core/interfaces.py`, `core/adapters.py` | Added `contacts` table + `command_history` table; `build_context_string()` now includes both |
| Orchestrator | `core/orchestrator.py` | Logs every non-chat step to `command_history`; passes `memory` into the action registry factory |
| Accessibility seam | `core/interfaces.py: IUIController`, `android_layer/accessibility.py` | Interface + stub only — real impl needs a custom Java class (see §5) |
| Permissions | `android_layer/actions.py: request_android_permissions()` | Added CALL_PHONE, SEND_SMS, READ_CONTACTS, CAMERA, FOREGROUND_SERVICE |
| Correctness fix | `core/adapters.py` (`CallContactActionExecutor`, `SendSmsActionExecutor`) | Raise on unresolved contact instead of returning a string, so a failed action can't be reported as a false success (Orchestrator prefers the LLM's `reply_hint` for successful action steps — a soft-fail string would have been overridden by an optimistic "Calling X." reply) |

### Verified in this session (desktop, no Android device available)
- `python3 -m py_compile` on every changed/added `.py` file: **passes**.
- Full Orchestrator pipeline exercised with a fake `ILanguageModel`
  injected via constructor (bypassing the Mock provider, which always
  returns `intent: "chat"`), covering: `open_app`, `remember_contact`,
  `call_contact` (known + unknown), `flashlight`, `volume`, `send_sms`,
  `open_settings`, `media_control`, `control_app` stub. All routed to
  the correct executor and produced the expected reply/failure
  behavior.
- Could **not** verify: anything requiring `pyjnius`/an Android
  runtime (no network in this sandbox to install Kivy/build tools, no
  physical device). That is 100% of the Android-native voice/service
  code — it is written to the documented, standard p4a/pyjnius API
  shapes but is unverified on-device.

## 3. What is STILL NOT implemented (by original scope)

- **Accessibility Service** (app-level automation: "open Telegram,
  search Asad, write Hello") — see §5, deliberately scoped as a stub
  this session per "ignore complex Automation" in the brief, but the
  interface (`IUIController`) and action-type seam (`control_app`) are
  in place so it's a pure addition later.
- Internet search, Vision, Smart Watch/Glasses, RAG — explicitly out
  of scope per the brief, untouched.
- Fuzzy contact name matching (currently exact, case-insensitive name
  match only — "call mom" works if the contact is literally named
  "mom"/"Mom", not nickname inference).

## 4. MUST-DO on-device verification checklist (next session or user)

1. **Build**: `buildozer android debug` (needs network — cannot run in
   this sandbox). Watch for `services=` line parsing errors first.
2. **Service class name**: after first build, check
   `<build>/dists/jarvis/src/main/java/org/jarvis/jarvis/` (or wherever
   p4a places generated service classes) for the actual generated
   class name and compare against `_SERVICE_CLASS` in
   `android_layer/service_manager.py`. Fix that one constant if it
   doesn't match.
3. **Permissions flow**: confirm the Android 13+ runtime permission
   dialog actually fires for RECORD_AUDIO/CALL_PHONE/SEND_SMS/
   READ_CONTACTS/CAMERA/POST_NOTIFICATIONS, and that
   `_on_permissions_result` in `main.py` fires afterward (plyer/p4a's
   `request_permissions` callback signature has changed across
   versions — if it doesn't fire, fall back to starting the service
   unconditionally after a short delay instead).
4. **Wake word loop responsiveness**: `listen_for_wake_word()`
   currently restarts a fresh ~8s `SpeechRecognizer` session in a tight
   loop. Confirm on-device that (a) this doesn't drain battery
   unacceptably, (b) the sub-second gap between sessions doesn't cause
   too many missed wake-word utterances in practice. If it's bad,
   swap this one function for an offline wake-word engine (Porcupine,
   Vosk) — nothing else needs to change.
5. **Foreground notification**: confirm p4a's default foreground
   notification actually appears (Android 8+ requires a notification
   channel for foreground services; some p4a versions need a manual
   `NotificationChannel` created in `service/main.py` on API 26+ if the
   default doesn't work).
6. **`dial_number` / `send_sms` silent paths**: both default to the
   safer `ACTION_DIAL`/`ACTION_SENDTO` (user must tap to confirm), NOT
   the permission-gated silent versions. Once tested and confirmed
   safe/desired, flip `direct_call=True` / `silent=True` at the call
   sites in `core/adapters.py` if fully hands-free calling/texting is
   wanted (be deliberate here — this is exactly the kind of action a
   misheard wake-word command could trigger unwantedly).

## 5. Accessibility Service — concrete next-iteration plan

(Also documented inline in `android_layer/accessibility.py`.)

1. Add a real Java class,
   `java_src/org/jarvis/jarvis/JarvisAccessibilityService.java`,
   extending `android.accessibilityservice.AccessibilityService`.
2. Add `android.add_src = java_src` to `buildozer.spec`, plus the
   `<service>` manifest block (BIND_ACCESSIBILITY_SERVICE permission)
   and an `accessibility_service_config.xml` resource.
3. Bridge Java event callbacks -> Python (local socket, or reuse
   pyjnius's existing activity bridge) so `onAccessibilityEvent`
   payloads reach Python.
4. Implement `AccessibilityUIController(IUIController)` in
   `android_layer/accessibility.py` for real (currently raises
   `NotImplementedError`).
5. Register a `control_app` `IActionExecutor` in `core/adapters.py`
   that uses it (the registry entry already exists as a stub —
   replace `ControlAppActionExecutor`'s body).
6. Remember: Android will NOT let the app silently enable this
   service — the user must toggle it on once in Settings >
   Accessibility. `open_settings("apps")` can help point them there.

## 6. File map of everything touched this session

```
main.py                              (rewritten: no mic button, auto-starts service)
service/main.py                      (NEW: foreground service entry point)
gateway/voice_gateway.py             (NEW: wake-word/conversation Gateway)
android_layer/voice.py               (rewritten: real STT bridge + wake word loop)
android_layer/actions.py             (expanded: call/sms/settings/flashlight/volume/media/contacts)
android_layer/service_manager.py     (NEW: start/stop foreground service)
android_layer/accessibility.py       (NEW: IUIController seam/stub)
core/interfaces.py                   (added contact/command-history methods, IUIController)
core/adapters.py                     (new IActionExecutor classes + registry wiring)
core/memory.py                       (contacts + command_history tables)
core/orchestrator.py                 (records command_history; passes memory into registry)
core/llm_client.py                   (now imports shared SYSTEM_PROMPT instead of duplicating)
providers/prompts.py                 (SYSTEM_PROMPT extended with new intents)
buildozer.spec                       (new permissions + services= line)
README.md                            (updated status)
HANDOVER.md                          (this file)
```

## 7. How to sanity-check without a device (what the next session can
   immediately do, no build required)

```bash
pip install -r requirements.txt --break-system-packages
export JARVIS_LLM_PROVIDER=mock   # or claude, with ANTHROPIC_API_KEY set
python run_cli.py
```
Everything except the wake-word/service/native-Android pieces (which
require pyjnius + a real device) is exercisable this way, since
`android_layer/*` all detect `IS_ANDROID=False` and fall back to
desktop-safe stand-ins.
