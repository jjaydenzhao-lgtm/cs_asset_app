# -*- coding: utf-8 -*-
"""
database.py —— 本地 SQLite 数据层
==================================
这是整个记账资产 APP 的"账本"，所有数据都存在手机本地数据库，
不需要服务器，隐私安全。

表结构：
1. transactions  日常收支流水
2. stocks        股票持仓
3. cs2_items     CS2 饰品持仓
4. cash_assets   现金/存款/公积金等固定资产
5. snapshots     每日资产快照（用于净值走势图）
"""

import os
import sqlite3
import datetime

# 数据库文件放在 APP 私有目录（Kivy 打包后可用 get_app_dir）
try:
    from kivy.utils import get_color_from_hex
    from kivy.app import App
    DB_PATH = os.path.join(App.get_running_app().user_data_dir, "asset.db")
except Exception:
    # 本地桌面调试时用项目目录下的 db
    DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "asset.db")


def get_conn():
    """获取数据库连接（每次操作都新建，避免多线程问题）"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """初始化所有表结构（首次运行自动建表）"""
    conn = get_conn()
    c = conn.cursor()
    # 1. 日常收支表
    c.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,          -- 日期 YYYY-MM-DD
            type TEXT NOT NULL,          -- income 收入 / expense 支出
            category TEXT NOT NULL,      -- 分类：餐饮/交通/房租/工资/其他...
            amount REAL NOT NULL,        -- 金额（元）
            note TEXT DEFAULT ''         -- 备注
        )
    """)
    # 2. 股票持仓表
    c.execute("""
        CREATE TABLE IF NOT EXISTS stocks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL,          -- 代码，如 AAPL / 600519
            market TEXT NOT NULL,        -- us 美股 / cn A股
            name TEXT NOT NULL,          -- 名称
            shares REAL NOT NULL,        -- 持仓股数
            cost_price REAL NOT NULL,    -- 成本价（对应币种）
            current_price REAL DEFAULT 0 -- 最新价（脚本刷新）
        )
    """)
    # 3. CS2 饰品持仓表
    c.execute("""
        CREATE TABLE IF NOT EXISTS cs2_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,          -- 饰品英文全名（用于匹配价格）
            wear TEXT NOT NULL DEFAULT '',  -- 磨损: FN/MW/FT/WW/BS
            stattrak INTEGER DEFAULT 0,  -- 是否暗金 0否 1是
            quantity INTEGER NOT NULL,   -- 数量
            cost_price REAL NOT NULL,    -- 购入单价（元）
            current_price REAL DEFAULT 0 -- 最新单价（元，刷新）
        )
    """)
    # 4. 现金/存款/公积金等固定资产表
    c.execute("""
        CREATE TABLE IF NOT EXISTS cash_assets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,          -- 账户名：银行卡/零钱/公积金...
            amount REAL NOT NULL,        -- 当前余额（元）
            updated_date TEXT NOT NULL   -- 最后更新日期
        )
    """)
    # 5. 每日资产快照表（净值走势用）
    c.execute("""
        CREATE TABLE IF NOT EXISTS snapshots (
            date TEXT PRIMARY KEY,       -- 日期
            stock_value REAL DEFAULT 0,  -- 股票市值（元）
            cs2_value REAL DEFAULT 0,    -- 饰品市值（元）
            cash_value REAL DEFAULT 0,   -- 现金资产（元）
            total REAL DEFAULT 0         -- 总资产（元）
        )
    """)
    conn.commit()
    conn.close()


# ============================================================
# 记账部分
# ============================================================
def add_transaction(date, ttype, category, amount, note=""):
    """新增一条收支记录"""
    conn = get_conn()
    conn.execute(
        "INSERT INTO transactions(date,type,category,amount,note) VALUES(?,?,?,?,?)",
        (date, ttype, category, float(amount), note),
    )
    conn.commit()
    conn.close()


def delete_transaction(tid):
    """删除一条记录"""
    conn = get_conn()
    conn.execute("DELETE FROM transactions WHERE id=?", (tid,))
    conn.commit()
    conn.close()


def get_transactions(month=None):
    """按月份查询流水；month=None 返回全部，month='2026-08' 按月份"""
    conn = get_conn()
    if month:
        rows = conn.execute(
            "SELECT * FROM transactions WHERE substr(date,1,7)=? ORDER BY date DESC, id DESC",
            (month,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM transactions ORDER BY date DESC, id DESC"
        ).fetchall()
    conn.close()
    return rows


def get_month_summary(month=None):
    """统计某月（默认当月）收入/支出总和"""
    if month is None:
        month = datetime.date.today().strftime("%Y-%m")
    conn = get_conn()
    row = conn.execute(
        """SELECT
             COALESCE(SUM(CASE WHEN type='income' THEN amount END),0) AS income,
             COALESCE(SUM(CASE WHEN type='expense' THEN amount END),0) AS expense
           FROM transactions WHERE substr(date,1,7)=?""",
        (month,),
    ).fetchone()
    conn.close()
    return row["income"], row["expense"]


# ============================================================
# 股票持仓
# ============================================================
def add_stock(code, market, name, shares, cost_price):
    conn = get_conn()
    conn.execute(
        "INSERT INTO stocks(code,market,name,shares,cost_price) VALUES(?,?,?,?,?)",
        (code, market, name, float(shares), float(cost_price)),
    )
    conn.commit()
    conn.close()


def delete_stock(sid):
    conn = get_conn()
    conn.execute("DELETE FROM stocks WHERE id=?", (sid,))
    conn.commit()
    conn.close()


def get_stocks():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM stocks ORDER BY id").fetchall()
    conn.close()
    return rows


def update_stock_price(sid, price):
    conn = get_conn()
    conn.execute("UPDATE stocks SET current_price=? WHERE id=?", (float(price), sid))
    conn.commit()
    conn.close()


def get_stock_total_value():
    """全部股票当前市值（元）"""
    conn = get_conn()
    rows = conn.execute("SELECT * FROM stocks").fetchall()
    conn.close()
    return sum(r["shares"] * r["current_price"] for r in rows)


# ============================================================
# CS2 饰品持仓
# ============================================================
def add_cs2_item(name, wear, stattrak, quantity, cost_price):
    conn = get_conn()
    conn.execute(
        """INSERT INTO cs2_items(name,wear,stattrak,quantity,cost_price)
           VALUES(?,?,?,?,?)""",
        (name, wear, 1 if stattrak else 0, int(quantity), float(cost_price)),
    )
    conn.commit()
    conn.close()


def delete_cs2_item(iid):
    conn = get_conn()
    conn.execute("DELETE FROM cs2_items WHERE id=?", (iid,))
    conn.commit()
    conn.close()


def get_cs2_items():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM cs2_items ORDER BY id").fetchall()
    conn.close()
    return rows


def update_cs2_price(iid, price):
    conn = get_conn()
    conn.execute("UPDATE cs2_items SET current_price=? WHERE id=?", (float(price), iid))
    conn.commit()
    conn.close()


def get_cs2_total_value():
    """全部饰品当前市值（元）"""
    conn = get_conn()
    rows = conn.execute("SELECT * FROM cs2_items").fetchall()
    conn.close()
    return sum(r["quantity"] * r["current_price"] for r in rows)


# ============================================================
# 现金资产
# ============================================================
def get_cash_assets():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM cash_assets ORDER BY id").fetchall()
    conn.close()
    return rows


def add_cash_asset(name, amount):
    conn = get_conn()
    today = datetime.date.today().strftime("%Y-%m-%d")
    conn.execute(
        "INSERT INTO cash_assets(name,amount,updated_date) VALUES(?,?,?)",
        (name, float(amount), today),
    )
    conn.commit()
    conn.close()


def update_cash_asset(aid, amount):
    conn = get_conn()
    today = datetime.date.today().strftime("%Y-%m-%d")
    conn.execute(
        "UPDATE cash_assets SET amount=?, updated_date=? WHERE id=?",
        (float(amount), today, aid),
    )
    conn.commit()
    conn.close()


def delete_cash_asset(aid):
    conn = get_conn()
    conn.execute("DELETE FROM cash_assets WHERE id=?", (aid,))
    conn.commit()
    conn.close()


def get_cash_total():
    conn = get_conn()
    row = conn.execute(
        "SELECT COALESCE(SUM(amount),0) AS t FROM cash_assets"
    ).fetchone()
    conn.close()
    return row["t"]


# ============================================================
# 每日资产快照
# ============================================================
def save_snapshot():
    """把当前各类资产总值存为一条快照（每天一条，覆盖当天）"""
    stock_val = get_stock_total_value()
    cs2_val = get_cs2_total_value()
    cash_val = get_cash_total()
    total = stock_val + cs2_val + cash_val
    today = datetime.date.today().strftime("%Y-%m-%d")
    conn = get_conn()
    conn.execute(
        """INSERT OR REPLACE INTO snapshots(date,stock_value,cs2_value,cash_value,total)
           VALUES(?,?,?,?,?)""",
        (today, stock_val, cs2_val, cash_val, total),
    )
    conn.commit()
    conn.close()
    return total


def get_snapshots():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM snapshots ORDER BY date").fetchall()
    conn.close()
    return rows


if __name__ == "__main__":
    # 本地自测
    init_db()
    print("数据库初始化成功:", DB_PATH)
