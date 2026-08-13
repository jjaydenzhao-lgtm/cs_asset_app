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
# 锁定 python 3.11.9：新版 p4a 默认 hostpython3/python3 = 3.14.2，其 venv 的 pip 有缺陷
# （pip install -U pip 报 BuildDependencyInstallError），故统一锁回稳定的 3.11.9
requirements = python3==3.11.9,hostpython3==3.11.9,kivy==2.3.0,requests==2.31.0

# Android 权限：需要联网拉行情
android.permissions = INTERNET,ACCESS_NETWORK_STATE
android.api = 33
android.minapi = 21
android.ndk = 25b
android.archs = arm64-v8a,armeabi-v7a

# 接受 SDK 许可（CI 环境必须）
android.accept_sdk_license = True
android.skip_update = False

# 指定 build-tools 版本（匹配 API 33）
android.build_tools_version = 33.0.2

# 图标（可选，没有就用默认）
# icon.filename = %(source.dir)s/assets/icon.png

[buildozer]
log_level = 2
warn_on_root = 1
