[app]
title = SecureChat
package.name = securechat
package.domain = com.securechat
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,pem
source.include_patterns = cert.pem
version = 1.0.0

# Requirements
requirements = python3,kivy==2.3.0,kivymd==1.2.0,pillow,certifi,openssl

# Android permissions
android.permissions = INTERNET,ACCESS_NETWORK_STATE,ACCESS_WIFI_STATE

# Entry point
entrypoint = android_app.py

# Presplash and icon (optional, customize later)
# presplash.filename = %(source.dir)s/data/presplash.png
# icon.filename = %(source.dir)s/data/icon.png

# Android config
android.api = 33
android.minapi = 21
android.ndk_api = 21
android.archs = arm64-v8a, armeabi-v7a

# Orientation
orientation = portrait

# Fullscreen
fullscreen = 0

# Build mode
# p4a.branch = master

[buildozer]
log_level = 2
warn_on_root = 1
