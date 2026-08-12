# -*- coding: utf-8 -*-
"""
price_fetcher.py —— 行情拉取模块（全部使用免费公开接口，无需 API Key）
========================================================================
1. 美股价格   ：Yahoo Finance 公开行情接口
2. A 股价格  ：腾讯行情接口
3. 美元汇率   ：open.er-api.com 免费汇率接口
4. CS2 饰品价：MarketCSGO 全量价格导出（公开 JSON，无 Key）

所有接口失败都不抛异常，返回 None，保证 APP 不闪退。
"""

import json
import os
import re
import datetime

import requests

# 全局请求头，模拟浏览器，避免被部分接口拒绝
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
}

# 缓存目录（保存 CS2 价格表和汇率）
CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache")
os.makedirs(CACHE_DIR, exist_ok=True)

# CS2 精简价格表：优先从公网更新源下载，其次用内置 assets 兜底
CS2_PRICE_URL = "https://aka.doubaocdn.com/s/MK7tn7yPqU"  # 公网更新源（合并脚本上传后更新此地址）
CS2_PRICE_CACHE = os.path.join(CACHE_DIR, "cs2_prices_usd.json")
CS2_PRICE_BUILTIN = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                 "assets", "cs2_prices_usd.json")

USD_CNY_URL = "https://open.er-api.com/v6/latest/USD"


# ============================================================
# 汇率
# ============================================================
def get_usd_cny(use_cache=True):
    """获取 1 美元 = ? 人民币。失败返回 None。"""
    cache_file = os.path.join(CACHE_DIR, "usd_cny.json")
    # 有缓存且是当天的话直接用，节省流量
    if use_cache and os.path.exists(cache_file):
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data.get("date") == datetime.date.today().strftime("%Y-%m-%d"):
                return data["rate"]
        except Exception:
            pass
    try:
        r = requests.get(USD_CNY_URL, headers=HEADERS, timeout=10)
        data = r.json()
        rate = data["rates"]["CNY"]
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump({"rate": rate, "date": datetime.date.today().strftime("%Y-%m-%d")}, f)
        return rate
    except Exception:
        return None


# ============================================================
# 美股（腾讯行情接口，国内直连稳定，免费无需 Key）
# ============================================================
def fetch_us_stock_price(symbol):
    """
    获取美股最新价（美元）。
    symbol 例：AAPL / TSLA / NVDA
    使用腾讯行情接口：https://qt.gtimg.cn/q=usAAPL
    """
    symbol = symbol.strip().upper().split(".")[0]  # 去掉 .OQ 等后缀
    url = f"https://qt.gtimg.cn/q=us{symbol}"
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        r.encoding = "gbk"
        text = r.text
        m = re.search(r'="([^"]+)"', text)
        if not m:
            return None
        fields = m.group(1).split("~")
        # 腾讯美股格式：v_usAAPL="200~苹果~AAPL.OQ~当前价~..."
        if len(fields) > 3:
            price = float(fields[3])
            if price > 0:
                return round(price, 2)
        return None
    except Exception:
        return None


# ============================================================
# A 股（腾讯行情接口，免费无需 Key）
# ============================================================
def fetch_cn_stock_price(code):
    """
    获取 A 股最新价（人民币）。
    code 例：600519 / 000001；自动补市场前缀。
    """
    code = code.strip()
    if code.startswith(("sh", "sz", "bj")):
        full_code = code.lower()
    elif code.startswith("6") or code.startswith("5") or code.startswith("9"):
        full_code = "sh" + code
    else:
        full_code = "sz" + code
    url = f"https://qt.gtimg.cn/q={full_code}"
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        r.encoding = "gbk"
        text = r.text
        # 返回格式：v_sh600519="1~贵州茅台~600519~...~当前价~...";
        m = re.search(r'="([^"]+)"', text)
        if not m:
            return None
        fields = m.group(1).split("~")
        if len(fields) > 3:
            return round(float(fields[3]), 2)
        return None
    except Exception:
        return None


def fetch_stock_price(market, code):
    """统一入口：根据市场拉取股票价格（返回人民币元）"""
    if market == "us":
        usd = fetch_us_stock_price(code)
        if usd is None:
            return None
        rate = get_usd_cny()
        if rate is None:
            return None
        return round(usd * rate, 2)
    else:
        return fetch_cn_stock_price(code)


# ============================================================
# CS2 饰品价格（精简价格表：公网更新源 / 内置兜底）
# ============================================================
# 磨损缩写 -> 标准写法
WEAR_FULL = {
    "FN": "Factory New",
    "MW": "Minimal Wear",
    "FT": "Field-Tested",
    "WW": "Well-Worn",
    "BS": "Battle-Scarred",
}


def build_market_hash_name(name, wear, stattrak):
    """把用户录入的信息拼成 MarketCSGO 的标准物品名（英文）"""
    full = name.strip()
    if stattrak:
        full = "StatTrak™ " + full
    w = wear.strip().upper()
    if w in WEAR_FULL:
        full += f" ({WEAR_FULL[w]})"
    return full


def load_json_file(path):
    """读取 JSON 文件，失败返回 {}"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def get_price_table():
    """
    获取 CS2 价格表（dict: name -> USD 价格）。
    优先级：本地缓存（24h 内）> 公网更新源 > 内置基准表。
    """
    now = datetime.date.today().strftime("%Y-%m-%d")
    # 1. 本地缓存
    if os.path.exists(CS2_PRICE_CACHE):
        meta = load_json_file(CS2_PRICE_CACHE)
        if meta.get("date") == now and isinstance(meta.get("prices"), dict):
            return meta["prices"]
    # 2. 公网更新源
    try:
        r = requests.get(CS2_PRICE_URL, headers=HEADERS, timeout=60)
        data = r.json()
        # 兼容两种格式：直接 dict / {"prices": dict}
        if isinstance(data, dict) and "prices" in data and isinstance(data["prices"], dict):
            prices = data["prices"]
        elif isinstance(data, dict):
            prices = data
        else:
            prices = {}
        if prices:
            with open(CS2_PRICE_CACHE, "w", encoding="utf-8") as f:
                json.dump({"date": now, "prices": prices}, f)
            return prices
    except Exception:
        pass
    # 3. 内置基准表兜底
    builtin = load_json_file(CS2_PRICE_BUILTIN)
    if isinstance(builtin, dict) and "prices" in builtin and isinstance(builtin["prices"], dict):
        return builtin["prices"]
    return builtin if isinstance(builtin, dict) else {}


def match_cs2_price(name, wear, stattrak, price_table):
    """
    在价格表中查找指定饰品价格（美元）。
    先精确匹配，再归一化匹配，再试非暗金版本。
    返回价格(美元)或 None。
    """
    key = build_market_hash_name(name, wear, stattrak)
    # 1. 精确匹配
    if key in price_table:
        return float(price_table[key])
    # 2. 大小写/空格归一化匹配
    norm = re.sub(r"\s+", " ", key).strip().lower()
    for k, v in price_table.items():
        if re.sub(r"\s+", " ", k).strip().lower() == norm:
            return float(v)
    # 3. 尝试非暗金版本
    if stattrak:
        key2 = build_market_hash_name(name, wear, False)
        if key2 in price_table:
            return float(price_table[key2])
    return None


def refresh_cs2_prices(items, usd_cny=None):
    """
    批量刷新饰品价格。
    items: 数据库中的饰品记录列表（需含 name/wear/stattrak/id）
    返回 (结果列表, 美元汇率)。
    """
    price_table = get_price_table()
    if usd_cny is None:
        usd_cny = get_usd_cny()

    results = []
    for it in items:
        price_usd = match_cs2_price(it["name"], it["wear"], it["stattrak"], price_table)
        if price_usd and usd_cny:
            price_cny = round(price_usd * usd_cny, 2)
            results.append({
                "id": it["id"],
                "found": True,
                "price_cny": price_cny,
                "text": f"¥{price_cny:.2f}",
            })
        else:
            results.append({
                "id": it["id"],
                "found": False,
                "price_cny": None,
                "text": "未找到",
            })
    return results, usd_cny


if __name__ == "__main__":
    # 本地自测
    print("美元汇率:", get_usd_cny())
    print("AAPL:", fetch_us_stock_price("AAPL"))
    print("贵州茅台:", fetch_cn_stock_price("600519"))
    table = get_price_table()
    print("CS2 价格表条目数:", len(table))
    print("AK-47 | Redline (Field-Tested):", match_cs2_price("AK-47 | Redline", "FT", False, table))
    print("CS2 价格表条目数:", len(t))
