# 我的资产账本（本地手机 APP）

一个**纯本地、不用服务器**的个人记账+资产统计 APP，用 Kivy 编写，可打包成安卓 APK。

## 功能
- **日常记账**：收入/支出、分类、支付方式（现金/微信/支付宝/银行卡）、备注、按月查看、删除
- **月度预算**：按类别设置月预算（住房/通讯/交通/饮食/衣物/医疗/娱乐/学习/健身/其他），实时显示已花/剩余进度条
- **工资计算器**：输入基本工资/学历补贴/从教津贴，自动算五险一金、个税、到手现金
- **现金资产**：银行卡/支付宝/微信/公积金等账户余额
- **股票持仓**：美股+A股，一键刷新最新价（腾讯行情接口，免费无 Key），自动算盈亏（人民币）
- **CS2 饰品库存**：记录饰品（英文名+磨损+是否暗金），一键刷新市场价，自动算盈亏（人民币）
- **仪表盘**：总资产、资产分类卡片、本月收支结余、每日净值快照走势
- 所有数据存在手机本地 SQLite，隐私安全，无云端

> 记账类别、月度预算、工资参数均对齐你的 `个人收支规划表.xlsx`。

## 数据接口（全部免费、无需 API Key）
| 数据 | 接口 | 说明 |
|---|---|---|
| 美股 | 腾讯行情 `qt.gtimg.cn/q=usXXXX` | 国内直连 |
| A 股 | 腾讯行情 `qt.gtimg.cn/q=sh/szXXXX` | 国内直连 |
| 美元汇率 | `open.er-api.com` | 每日缓存 |
| CS2 饰品 | 精简价格表（公网更新源）+ 内置基准表兜底 | 美元价×汇率转人民币 |

## 目录结构
```
cs_asset_app/
├── main.py            # Kivy 主程序（6 个页面 + 底部导航）
├── database.py        # SQLite 数据层（记账/预算/股票/饰品/现金/快照）
├── price_fetcher.py   # 行情拉取（股票/汇率/CS2）
├── merge_cs2.py       # [电脑端] 合并 MarketCSGO 全量分片生成精简价格表
├── assets/
│   └── cs2_prices_usd.json   # 内置基准价格表（打包进 APK）
├── buildozer.spec     # 安卓打包配置
└── requirements.txt
```

## 本地运行（调试）
```bash
pip install -r requirements.txt
python main.py
```

## 打包安卓 APK（两种方式）

### 方式 A：GitHub Actions 云端打包（推荐，免费、无需本地环境）
项目里已带好 `.github/workflows/build.yml`：
1. 把整个 `cs_asset_app` 项目推到你的 GitHub 仓库（保留 `buildozer.spec`）
2. 打开仓库 **Actions** 页面 → 左侧选 **Build APK** → 右侧 **Run workflow** → 运行
3. 几分钟后展开该次运行，在底部 **Artifacts** 下载 `assetbook-apk.zip`，里面就是 APK
4. 把 APK 传到手机安装（记得在手机设置里允许"安装未知来源应用"）

### 方式 B：本机 Buildozer 打包
```bash
# 1. 安装 buildozer
pip install buildozer cython
# 2. 安装系统依赖（Ubuntu）
sudo apt install -y git zip unzip openjdk-17-jdk autoconf libtool \
  pkg-config zlib1g-dev libncurses5-dev libncursesw5-dev libtinfo5 \
  cmake libffi-dev libssl-dev python3-pip
# 3. 打包
cd cs_asset_app
buildozer android debug
# 产物：bin/*.apk
```
首次打包会自动下载 Android SDK/NDK，需要较长时间和网络。

## CS2 价格表如何更新
1. 电脑端跑 `python3 merge_cs2.py` 生成最新精简价格表（约几分钟）
2. 将 `assets/cs2_prices_usd.json` 重新上传到公网（如对象存储），得到新 URL
3. 把新 URL 填到 `price_fetcher.py` 的 `CS2_PRICE_URL`，重新打包
4. 手机端每次点「刷新价」会先尝试下载公网更新源（24 小时缓存），失败则用内置基准表兜底

## 使用提示
- **股票代码**：美股填代码如 `AAPL`；A 股填 `600519`/`000001`
- **饰品名称**：请填英文全名（如 `AK-47 | Redline`），配合磨损（FN/MW/FT/WW/BS）和是否暗金，匹配最准
- 价格表是"市场参考价"，非即时成交价，变现时以实际成交为准
