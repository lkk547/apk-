[app]
[应用程序]
package.name = stocksim
package.domain = org.example
source.dir = .
source.include_exts = py,kv,png,jpg,ttf
version = 0.1
requirements = python3,kivy==2.1.0,pandas,baostock
orientation = portrait
fullscreen = 0
# Android 权限
android.permissions = INTERNET,WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE

# 支持的架构（根据新格式使用 android.archs）
android.archs = armeabi-v7a,arm64-v8a

[buildozer]
log_level = 2
warn_on_root = 1

[android]
# 指定 API/NDK 版本以提高兼容性（容器/CI 中通常由镜像提供 SDK/NDK）
android.api = 29
android.ndk = 21b
android.minapi = 21
android.build_tools_version = 34.0.0
android.accept_sdk_license = True

# 如果你有自定义的图标或启动图，可设置以下项
# icon.filename = %(source.dir)s/icon.png
# presplash.filename = %(source.dir)s/icon.png
