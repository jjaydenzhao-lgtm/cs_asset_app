# -*- coding: utf-8 -*-
"""
merge_cs2.py —— 电脑端合并脚本（可选）
========================================
下载 MarketCSGO 全部分片，合并成精简价格表 cs2_prices_usd.json
格式：{ "物品名": 价格(美元) }

用法：
    python3 merge_cs2.py

生成文件放到 APP 的 assets/ 目录作为内置基准价格表。
之后可以定期重跑，把新文件通过 FileBatchUpload 上传公网，
让手机端 APP 直接下载更新（见 price_fetcher.py 的 CS2_PRICE_URL）。
"""

import json
import os
import re
import requests

SHARD_LIST_URL = "https://market.csgo.com/api/full-export/USD.json"
SHARD_URL = "https://market.csgo.com/api/full-export/{shard}"
HEADERS = {"User-Agent": "Mozilla/5.0", "Accept-Encoding": "gzip, deflate"}
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "cs2_prices_usd.json")

# 只保留带磨损的武器皮肤 + StatTrak 变体，砍掉贴纸/胶囊/音乐盒等
WEAR_PAT = re.compile(r"\((Factory New|Minimal Wear|Field-Tested|Well-Worn|Battle-Scarred)\)$")


def main():
    print("获取分片列表...")
    shards = requests.get(SHARD_LIST_URL, headers=HEADERS, timeout=30).json()["items"]
    print(f"共 {len(shards)} 个分片")

    prices = {}
    for i, shard in enumerate(shards):
        r = requests.get(SHARD_URL.format(shard=shard), headers=HEADERS, timeout=60)
        for rec in r.json():
            # rec = [price, id, market_hash_name, ...]
            if not isinstance(rec, list) or len(rec) < 3:
                continue
            name = rec[2]
            if not isinstance(name, str):
                continue
            # 过滤：必须含磨损后缀（武器皮肤），或 StatTrak
            if not (WEAR_PAT.search(name) or name.startswith("StatTrak™")):
                continue
            try:
                # MarketCSGO 的 price 单位是千分之一美元 -> /1000 得美元
                price = float(rec[0]) / 1000.0
            except Exception:
                continue
            if price > 0:
                # 同一物品多个挂单，取最低价（最贴近真实成交价）
                if name not in prices or price < prices[name]:
                    prices[name] = round(price, 2)
        if (i + 1) % 20 == 0:
            print(f"  已处理 {i+1}/{len(shards)}，累计 {len(prices)} 条")

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(prices, f, ensure_ascii=False)
    size_mb = os.path.getsize(OUT) / 1024 / 1024
    print(f"完成！共 {len(prices)} 条，输出 {OUT} ({size_mb:.1f} MB)")


if __name__ == "__main__":
    main()
