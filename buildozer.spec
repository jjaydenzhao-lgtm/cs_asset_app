[app]
# 应用名（手机桌面显示的名称）
title = 我的资产账本

# 包名（唯一标识，最好用你的域名反写）
package.name = assetbook
package.domain = com.assetbook

# 源代码入口
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json
source.include_patterns = assets/*,cache/*.json

# 版本
version = 0.1.0

# 依赖库（Kivy + 网络请求；sqlite3 是 Python 内置，p4a 自动带）
requirements = python3,kivy,requests

# Android 权限：需要联网拉行情
android.permissions = INTERNET,ACCESS_NETWORK_STATE
android.api = 33
android.minapi = 21
android.ndk = 25b
android.archs = arm64-v8a,armeabi-v7a

# 图标（可选，没有就用默认）
# icon.filename = %(source.dir)s/assets/icon.png

[buildozer]
log_level = 2
warn_on_root = 1
