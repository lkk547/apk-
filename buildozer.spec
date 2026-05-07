[app]
title = 手机炒股模拟器
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

# 支持的架构（根据需要可以只保留 armeabi-v7a 或 arm64-v8a）
android.arch = armeabi-v7a,arm64-v8a

[buildozer]
log_level = 2
warn_on_root = 1

[android]
# 指定 API/NDK 版本以提高兼容性（容器/CI 中通常由镜像提供 SDK/NDK）
android.api = 29
android.ndk = 21b

# 如果你有自定义的图标或启动图，可设置以下项
# icon.filename = %(source.dir)s/icon.png
# presplash.filename = %(source.dir)s/presplash.png
