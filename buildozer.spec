[app]
title = JARVIS
package.name = jarvis
package.domain = org.jarvis
source.dir = .
source.include_exts = py,png,jpg,kv,atlas
version = 0.1

requirements = python3,kivy,pyjnius,plyer,requests,anthropic

orientation = portrait
fullscreen = 0

# Foreground service that keeps the wake-word/conversation loop alive
# after the user leaves the app (see service/main.py). The
# ":foreground" suffix makes p4a call startForeground() + post the
# required persistent notification automatically.
services = jarvisvoice:service/main.py:foreground

android.permissions = INTERNET,RECORD_AUDIO,POST_NOTIFICATIONS,SET_ALARM,CALL_PHONE,SEND_SMS,READ_CONTACTS,CAMERA,FOREGROUND_SERVICE,MODIFY_AUDIO_SETTINGS
android.api = 33
android.minapi = 24
android.archs = arm64-v8a

[buildozer]
log_level = 2
