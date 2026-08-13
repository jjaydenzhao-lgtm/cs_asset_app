# -*- coding: utf-8 -*-
"""
database.py —— 本地 SQLite 数据层
==================================
这是整个记账资产 APP 的"账本"，所有数据都存在手机本地数据库，
不需要服务器，隐私安全。

表结构：
1. transactions  日常收支流水（含支付方式）
2. budgets       月度支出预算（按类别）
3. stocks        股票持仓
4. cs2_items     CS2 饰品持仓
5. cash_assets   现金/存款/公积金等固定资产
6. snapshots     每日资产快照（用于净值走势图）
"""

import os
import sqlite3
import datetime


# ============================================================
# 数据库路径（延迟计算，兼容安卓只读目录）
# ============================================================
def get_db_path():
    """
    获取数据库文件路径。
    打包成安卓 APK 后，源码目录是只读的，必须写到 App 的 user_data_dir；
    桌面调试时退回到项目目录。这里用函数延迟计算，避免模块导入时
    App.get_running_app() 还是 None 导致拿到只读路径。
    """
    try:
        from kivy.app import App
        app = App.get_running_app()
        if app is not None and getattr(app, "user_data_dir", None):
            return os.path.join(app.user_data_dir, "asset.db")
    except Exception:
        pass
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "asset.db")


# 兼容旧代码里可能引用的 DB_PATH
DB_PATH = get_db_path()


def get_conn():
    """获取数据库连接（每次操作都新建，避免多线程问题）"""
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    return conn


def _column_exists(conn, table, column):
    """判断某表是否已有某列（用于旧库平滑升级）"""
    cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]
    return column in cols


def init_db():
    """初始化所有表结构（首次运行自动建表，旧库自动补列）"""
    conn = get_conn()
    c = conn.cursor()
    # 1. 日常收支表
    c.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,          -- 日期 YYYY-MM-DD
            type TEXT NOT NULL,          -- income 收入 / expense 支出
            category TEXT NOT NULL,      -- 分类：住房/通讯/交通/饮食/...
            amount REAL NOT NULL,        -- 金额（元）
            payment TEXT DEFAULT '',     -- 支付方式：现金/微信/支付宝/银行卡
            note TEXT DEFAULT ''         -- 备注
        )
    """)
    # 旧库平滑升级：补 payment 列
    if not _column_exists(conn, "transactions", "payment"):
        c.execute("ALTER TABLE transactions ADD COLUMN payment TEXT DEFAULT ''")

    # 2. 月度支出预算表
    c.execute("""
        CREATE TABLE IF NOT EXISTS budgets (
            category TEXT PRIMARY KEY,   -- 类别
            monthly REAL NOT NULL DEFAULT 0  -- 月预算（元）
        )
    """)

    # 3. 股票持仓表
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
    # 4. CS2 饰品持仓表
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
    # 5. 现金/存款/公积金等固定资产表
    c.execute("""
        CREATE TABLE IF NOT EXISTS cash_assets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,          -- 账户名：银行卡/零钱/公积金...
            amount REAL NOT NULL,        -- 当前余额（元）
            updated_date TEXT NOT NULL   -- 最后更新日期
        )
    """)
    # 6. 每日资产快照表（净值走势用）
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
    seed_budgets()


# ============================================================
# 记账部分
# ============================================================
def add_transaction(date, ttype, category, amount, payment="", note=""):
    """新增一条收支记录"""
    conn = get_conn()
    conn.execute(
        """INSERT INTO transactions(date,type,category,amount,payment,note)
           VALUES(?,?,?,?,?,?)""",
        (date, ttype, category, float(amount), payment, note),
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


def get_category_spending(month=None):
    """统计某月各支出类别的花费，返回 {类别: 金额}"""
    if month is None:
        month = datetime.date.today().strftime("%Y-%m")
    conn = get_conn()
    rows = conn.execute(
        """SELECT category, COALESCE(SUM(amount),0) AS s
           FROM transactions WHERE type='expense' AND substr(date,1,7)=?
           GROUP BY category""",
        (month,),
    ).fetchall()
    conn.close()
    return {r["category"]: r["s"] for r in rows}


# ============================================================
# 月度预算
# ============================================================
# 预置预算（来自「个人收支规划表」基础参数，合计 3680 元/月）
DEFAULT_BUDGETS = {
    "住房": 1800,   # 房租1500 + 水电燃气200 + 住房杂费100
    "通讯": 80,     # 手机话费
    "交通": 200,    # 地铁+公交
    "饮食": 1100,   # 基本900 + 享受100 + 社交100
    "衣物": 150,
    "医疗": 50,
    "娱乐": 200,    # 个人娱乐50 + 社交娱乐150
    "学习": 0,      # 书籍、课程
    "健身": 100,
    "其他": 0,
}


def seed_budgets():
    """首次运行时写入预置预算（只在预算表为空时执行）"""
    conn = get_conn()
    count = conn.execute("SELECT COUNT(*) AS c FROM budgets").fetchone()["c"]
    if count == 0:
        for cat, amt in DEFAULT_BUDGETS.items():
            conn.execute(
                "INSERT OR REPLACE INTO budgets(category,monthly) VALUES(?,?)",
                (cat, float(amt)),
            )
        conn.commit()
    conn.close()


def get_budgets():
    """返回所有预算 {类别: 月预算}"""
    conn = get_conn()
    rows = conn.execute("SELECT * FROM budgets ORDER BY monthly DESC").fetchall()
    conn.close()
    return {r["category"]: r["monthly"] for r in rows}


def set_budget(category, monthly):
    """设置/更新某类别的月预算"""
    conn = get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO budgets(category,monthly) VALUES(?,?)",
        (category, float(monthly)),
    )
    conn.commit()
    conn.close()


# ============================================================
# 工资计算（参数来自「个人收支规划表」基础参数）
# ============================================================
SALARY_DEFAULTS = {
    "base": 7900,        # 月基本工资（元）
    "edu": 500,          # 学历补贴（元/月，不计社保基数，计入个税）
    "teach": 0,          # 从教津贴（元/月，满1年后 600）
    "pension": 0.08,     # 养老保险个人比例
    "medical": 0.02,     # 医疗保险个人比例
    "unemployment": 0.002,  # 失业保险个人比例
    "fund": 0.12,        # 公积金个人比例（单位同比例）
    "tax_threshold": 5000,  # 个税起征点
}


def calc_salary(base=7900, edu=500, teach=0):
    """
    计算月度工资明细（人民币）。
    返回 dict：
      gross          税前总收入（含补贴津贴）
      pension/medical/unemployment  五险一金各项个人扣款
      fund_personal  公积金个人
      fund_company   公积金单位（账户入账）
      social_total   五险一金个人合计
      tax            个人所得税（按3%简化，未考虑专项附加扣除）
      net            到手现金
    """
    base = float(base)
    edu = float(edu)
    teach = float(teach)
    gross = base + edu + teach
    pension = base * SALARY_DEFAULTS["pension"]
    medical = base * SALARY_DEFAULTS["medical"]
    unemployment = base * SALARY_DEFAULTS["unemployment"]
    fund = base * SALARY_DEFAULTS["fund"]
    social = pension + medical + unemployment + fund
    taxable = gross - social - SALARY_DEFAULTS["tax_threshold"]
    tax = max(0.0, taxable) * 0.03
    net = gross - social - tax
    return {
        "gross": round(gross, 2),
        "pension": round(pension, 2),
        "medical": round(medical, 2),
        "unemployment": round(unemployment, 2),
        "fund_personal": round(fund, 2),
        "fund_company": round(fund, 2),
        "social_total": round(social, 2),
        "tax": round(tax, 2),
        "net": round(net, 2),
    }


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
    print("数据库初始化成功:", get_db_path())
    s = calc_salary()
    print("到手现金:", s["net"], "个税:", s["tax"], "五险一金:", s["social_total"])
    print("预算:", get_budgets())
