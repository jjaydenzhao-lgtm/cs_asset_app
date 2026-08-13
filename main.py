# -*- coding: utf-8 -*-
"""
main.py —— 本地记账资产 APP 主程序
====================================
技术栈：Kivy（Python GUI 框架，可打包安卓 APK）
功能：
  1. 仪表盘：总资产、本月收支、资产分类卡片、净值走势
  2. 记账：日常收入/支出录入、按月查看、删除
  3. 股票：持仓管理 + 一键刷新最新价（自动算盈亏，人民币）
  4. CS2 饰品：持仓管理 + 一键刷新市场价（自动算盈亏，人民币）

运行：
  pip install kivy requests
  python main.py

打包安卓 APK：见 buildozer.spec 说明。
"""

import threading

from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.popup import Popup
from kivy.uix.spinner import Spinner
from kivy.clock import Clock
from kivy.metrics import dp

import database as db
import price_fetcher as pf


# ============================================================
# 通用小工具
# ============================================================
ACCENT = (0.24, 0.55, 0.91, 1)     # 蓝色主题
RED = (0.86, 0.26, 0.26, 1)        # 亏损/支出红
GREEN = (0.16, 0.67, 0.36, 1)      # 盈利/收入绿
BG = (0.96, 0.97, 0.99, 1)         # 页面底色

# 记账类别（来自「个人收支规划表」日常记账说明）
EXPENSE_CATEGORIES = ["住房", "通讯", "交通", "饮食", "衣物", "医疗",
                      "娱乐", "学习", "健身", "其他"]
INCOME_CATEGORIES = ["工资", "补贴", "津贴", "兼职", "红包", "其他"]
# 支付方式
PAY_METHODS = ["现金", "微信", "支付宝", "银行卡", "其他"]


def money(v):
    """格式化金额，带千分位"""
    try:
        return f"¥{float(v):,.2f}"
    except Exception:
        return "¥0.00"


def section(title):
    """小节标题"""
    return Label(
        text=title, bold=True, size_hint_y=None, height=dp(32),
        color=(0.2, 0.2, 0.25, 1), halign="left",
    )


def field_label(text):
    return Label(text=text, size_hint_y=None, height=dp(30),
                 halign="left", color=(0.2, 0.2, 0.25, 1))


def make_scroll(body, padding=12):
    """把内容放进可滚动容器"""
    root = ScrollView()
    inner = BoxLayout(orientation="vertical", size_hint_y=None, padding=dp(padding))
    inner.bind(minimum_height=inner.setter("height"))
    inner.add_widget(body)
    root.add_widget(inner)
    return root


# ============================================================
# 仪表盘页面
# ============================================================
class DashboardScreen(Screen):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.name = "dashboard"
        box = BoxLayout(orientation="vertical", spacing=dp(10), padding=dp(14))
        box.add_widget(Label(text="资产仪表盘", bold=True, size_hint_y=None, height=dp(40),
                             font_size=dp(18), color=(0.2, 0.2, 0.25, 1)))
        self.total_label = Label(text="", font_size=dp(28), bold=True,
                                 color=ACCENT, size_hint_y=None, height=dp(50))
        box.add_widget(self.total_label)

        self.grid = GridLayout(cols=2, spacing=dp(10), size_hint_y=None)
        self.grid.bind(minimum_height=self.grid.setter("height"))
        box.add_widget(self.grid)

        self.month_label = Label(text="", size_hint_y=None, height=dp(36),
                                 color=(0.3, 0.3, 0.35, 1))
        box.add_widget(self.month_label)

        self.trend_label = Label(text="（每日保存快照后显示净值走势）",
                                 size_hint_y=None, height=dp(40),
                                 color=(0.5, 0.5, 0.55, 1))
        box.add_widget(self.trend_label)

        btn = Button(text="🔄 保存今日快照", size_hint_y=None, height=dp(46),
                     background_color=ACCENT)
        btn.bind(on_press=lambda x: self.save_snapshot())
        box.add_widget(btn)

        salary_btn = Button(text="💰 工资计算", size_hint_y=None, height=dp(46),
                            background_color=(0.4, 0.35, 0.7, 1))
        salary_btn.bind(on_press=lambda x: self.open_salary())
        box.add_widget(salary_btn)

        self.add_widget(box)
        Clock.schedule_once(lambda dt: self.refresh())

    def open_salary(self):
        """打开工资计算器弹窗"""
        open_salary_calculator()

    def refresh(self, *args):
        """刷新所有资产汇总"""
        stock_val = db.get_stock_total_value()
        cs2_val = db.get_cs2_total_value()
        cash_val = db.get_cash_total()
        total = stock_val + cs2_val + cash_val
        self.total_label.text = f"总资产  {money(total)}"

        self.grid.clear_widgets()
        cards = [
            ("现金资产", cash_val, ACCENT),
            ("股票市值", stock_val, GREEN),
            ("CS2饰品", cs2_val, RED),
        ]
        for t, v, c in cards:
            b = BoxLayout(orientation="vertical", size_hint_y=None, height=dp(74),
                          padding=dp(8))
            b.add_widget(Label(text=t, color=(0.4, 0.4, 0.45, 1),
                               size_hint_y=None, height=dp(22)))
            b.add_widget(Label(text=money(v), bold=True, font_size=dp(18),
                               color=c, size_hint_y=None, height=dp(30)))
            self.grid.add_widget(b)

        # 本月收支
        month = __import__("datetime").date.today().strftime("%Y-%m")
        income, expense = db.get_month_summary(month)
        self.month_label.text = (f"{month}  收入 {money(income)}   支出 {money(expense)}"
                                 f"   结余 {money(income - expense)}")

        # 净值走势（最近7条）
        snaps = db.get_snapshots()[-7:]
        if snaps:
            lines = "  |  ".join(f"{s['date'][5:]} {s['total']:.0f}" for s in snaps)
            self.trend_label.text = "净值走势: " + lines
        else:
            self.trend_label.text = "（点击下方按钮保存今日快照后显示净值走势）"

    def save_snapshot(self):
        total = db.save_snapshot()
        from kivy.uix.popup import Popup
        p = Popup(title="已保存", content=Label(text=f"今日快照已保存\n总资产 {money(total)}"),
                  size_hint=(0.7, 0.35))
        p.open()
        Clock.schedule_once(lambda dt: self.refresh(), 0.1)


# ============================================================
# 记账页面
# ============================================================
class LedgerScreen(Screen):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.name = "ledger"
        self.month_selector = None
        self.box = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(6))
        self.box.add_widget(Label(text="日常记账", bold=True, size_hint_y=None,
                                  height=dp(36), font_size=dp(18)))
        # 顶部：添加按钮 + 月份选择
        top = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(8))
        add_btn = Button(text="＋ 记一笔", background_color=ACCENT)
        add_btn.bind(on_press=lambda x: self.open_add_form())
        self.month_selector = Spinner(
            text="本月", values=["本月", "全部"],
            size_hint_x=0.45, background_color=(0.9, 0.92, 0.97, 1),
            color=(0.2, 0.2, 0.25, 1))
        self.month_selector.bind(text=lambda *a: self.refresh())
        top.add_widget(add_btn)
        top.add_widget(self.month_selector)
        self.box.add_widget(top)

        self.body = BoxLayout(orientation="vertical", size_hint_y=None)
        self.box.add_widget(make_scroll(self.body))
        self.add_widget(self.box)
        Clock.schedule_once(lambda dt: self.refresh())

    def refresh(self, *args):
        self.body.clear_widgets()
        show_all = self.month_selector.text == "全部"
        month = None if show_all else __import__("datetime").date.today().strftime("%Y-%m")
        rows = db.get_transactions(month)
        if not rows:
            self.body.add_widget(Label(text="暂无记录，点上方＋记一笔",
                                       color=(0.5, 0.5, 0.55, 1), size_hint_y=None,
                                       height=dp(40)))
            return
        for r in rows:
            line = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(6))
            tag = "收" if r["type"] == "income" else "支"
            tag_color = GREEN if r["type"] == "income" else RED
            line.add_widget(Label(text=f"{r['date'][5:]}", size_hint_x=0.22,
                                  color=(0.4, 0.4, 0.45, 1)))
            pay = f" ·{r['payment']}" if r["payment"] else ""
            line.add_widget(Label(text=f"[{tag}] {r['category']}{pay}", size_hint_x=0.34,
                                  color=(0.25, 0.25, 0.3, 1)))
            line.add_widget(Label(text=f"{'＋' if r['type']=='income' else '－'}{money(r['amount'])}",
                                  size_hint_x=0.3, color=tag_color, bold=True))
            del_btn = Button(text="✕", size_hint_x=0.14, background_color=(0.9, 0.6, 0.6, 1),
                             color=(1, 1, 1, 1))
            del_btn.bind(on_press=lambda b, tid=r["id"]: self.confirm_delete(tid))
            line.add_widget(del_btn)
            self.body.add_widget(line)
            if r["note"]:
                self.body.add_widget(Label(text="    备注:" + r["note"],
                                           size_hint_y=None, height=dp(20),
                                           color=(0.6, 0.6, 0.65, 1),
                                           font_size=dp(12)))

    def open_add_form(self):
        box = BoxLayout(orientation="vertical", spacing=dp(8), padding=dp(10))
        box.add_widget(field_label("类型"))
        type_sp = Spinner(text="支出", values=["支出", "收入"], size_hint_y=None, height=dp(40))
        box.add_widget(type_sp)
        box.add_widget(field_label("分类"))
        cat_sp = Spinner(text="住房", values=EXPENSE_CATEGORIES,
                         size_hint_y=None, height=dp(40))
        box.add_widget(cat_sp)
        box.add_widget(field_label("金额（元）"))
        amt_in = TextInput(input_filter="float", size_hint_y=None, height=dp(40))
        box.add_widget(amt_in)
        box.add_widget(field_label("支付方式"))
        pay_sp = Spinner(text="微信", values=PAY_METHODS, size_hint_y=None, height=dp(40))
        box.add_widget(pay_sp)
        box.add_widget(field_label("备注"))
        note_in = TextInput(size_hint_y=None, height=dp(40))
        box.add_widget(note_in)
        popup = Popup(title="记一笔", content=box, size_hint=(0.85, 0.9))

        # 切换类型时联动分类
        def on_type(sp, text):
            cats = INCOME_CATEGORIES if text == "收入" else EXPENSE_CATEGORIES
            cat_sp.values = cats
            cat_sp.text = cats[0]
        type_sp.bind(text=on_type)

        def submit(btn):
            try:
                amt = float(amt_in.text)
            except ValueError:
                return
            ttype = "income" if type_sp.text == "收入" else "expense"
            today = __import__("datetime").date.today().strftime("%Y-%m-%d")
            db.add_transaction(today, ttype, cat_sp.text.strip() or "其他",
                               amt, pay_sp.text, note_in.text.strip())
            popup.dismiss()
            self.refresh()
        box.add_widget(Button(text="保存", background_color=ACCENT, size_hint_y=None,
                              height=dp(44), on_press=submit))
        popup.open()

    def confirm_delete(self, tid):
        p = Popup(title="删除这条记录？",
                  content=Button(text="确认删除", background_color=RED,
                                 color=(1, 1, 1, 1)),
                  size_hint=(0.7, 0.35))
        p.content.bind(on_press=lambda b: (db.delete_transaction(tid), p.dismiss(), self.refresh()))
        p.open()


# ============================================================
# 股票页面
# ============================================================
class StocksScreen(Screen):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.name = "stocks"
        self.box = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(6))
        top = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(8))
        top.add_widget(Label(text="股票持仓", bold=True, font_size=dp(18),
                             color=(0.2, 0.2, 0.25, 1)))
        add_btn = Button(text="＋ 加仓", background_color=ACCENT)
        add_btn.bind(on_press=lambda x: self.open_add_form())
        refresh_btn = Button(text="🔄 刷新价", background_color=GREEN)
        refresh_btn.bind(on_press=lambda x: self.refresh_prices())
        top.add_widget(add_btn)
        top.add_widget(refresh_btn)
        self.box.add_widget(top)

        self.body = BoxLayout(orientation="vertical", size_hint_y=None)
        self.box.add_widget(make_scroll(self.body))
        self.add_widget(self.box)
        Clock.schedule_once(lambda dt: self.refresh())

    def refresh(self, *args):
        self.body.clear_widgets()
        rows = db.get_stocks()
        if not rows:
            self.body.add_widget(Label(text="暂无持仓，点＋加仓", color=(0.5, 0.5, 0.55, 1),
                                       size_hint_y=None, height=dp(40)))
            return
        head = Label(text="名称       现价      盈亏     持仓市值", size_hint_y=None,
                     height=dp(26), bold=True, color=(0.3, 0.3, 0.35, 1))
        self.body.add_widget(head)
        for r in rows:
            market_val = r["shares"] * r["current_price"]
            cost_val = r["shares"] * r["cost_price"]
            pnl = market_val - cost_val
            pnl_color = GREEN if pnl >= 0 else RED
            line = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(4))
            line.add_widget(Label(text=f"{r['name']}\n({r['market'].upper()}:{r['code']})",
                                  size_hint_x=0.32, color=(0.25, 0.25, 0.3, 1),
                                  font_size=dp(12)))
            line.add_widget(Label(text=f"{r['current_price']:.2f}" if r["current_price"] else "--",
                                  size_hint_x=0.2, color=(0.3, 0.3, 0.35, 1)))
            line.add_widget(Label(text=f"{pnl:+.0f}" if r["current_price"] else "--",
                                  size_hint_x=0.18, color=pnl_color, bold=True))
            line.add_widget(Label(text=money(market_val), size_hint_x=0.22,
                                  color=(0.25, 0.25, 0.3, 1)))
            del_btn = Button(text="✕", size_hint_x=0.08, background_color=(0.9, 0.6, 0.6, 1),
                             color=(1, 1, 1, 1))
            del_btn.bind(on_press=lambda b, sid=r["id"]: self.delete_row(sid))
            line.add_widget(del_btn)
            self.body.add_widget(line)

    def open_add_form(self):
        box = BoxLayout(orientation="vertical", spacing=dp(6), padding=dp(10))
        box.add_widget(field_label("市场"))
        mk = Spinner(text="美股", values=["美股", "A股"], size_hint_y=None, height=dp(40))
        box.add_widget(mk)
        box.add_widget(field_label("代码（美股如 AAPL / A股如 600519）"))
        code_in = TextInput(size_hint_y=None, height=dp(40))
        box.add_widget(code_in)
        box.add_widget(field_label("名称"))
        name_in = TextInput(size_hint_y=None, height=dp(40))
        box.add_widget(name_in)
        box.add_widget(field_label("持仓股数"))
        sh_in = TextInput(input_filter="float", size_hint_y=None, height=dp(40))
        box.add_widget(sh_in)
        box.add_widget(field_label("成本单价（人民币）"))
        cost_in = TextInput(input_filter="float", size_hint_y=None, height=dp(40))
        box.add_widget(cost_in)
        popup = Popup(title="加仓", content=box, size_hint=(0.85, 0.9))

        def submit(btn):
            try:
                shares = float(sh_in.text)
                cost = float(cost_in.text)
            except ValueError:
                return
            market = "us" if mk.text == "美股" else "cn"
            db.add_stock(code_in.text.strip().upper(), market,
                         name_in.text.strip(), shares, cost)
            popup.dismiss()
            self.refresh()
        box.add_widget(Button(text="保存", background_color=ACCENT, size_hint_y=None,
                              height=dp(44), on_press=submit))
        popup.open()

    def delete_row(self, sid):
        p = Popup(title="删除该持仓？",
                  content=Button(text="确认删除", background_color=RED, color=(1, 1, 1, 1)),
                  size_hint=(0.7, 0.35))
        p.content.bind(on_press=lambda b: (db.delete_stock(sid), p.dismiss(), self.refresh()))
        p.open()

    def refresh_prices(self):
        """后台线程刷新所有股票价格，避免卡界面"""
        def work():
            rows = db.get_stocks()
            for r in rows:
                price = pf.fetch_stock_price(r["market"], r["code"])
                if price:
                    db.update_stock_price(r["id"], price)
            Clock.schedule_once(lambda dt: self.refresh())
        t = threading.Thread(target=work, daemon=True)
        t.start()
        # 简单提示
        p = Popup(title="刷新中", content=Label(text="正在拉取最新股价…"),
                  size_hint=(0.7, 0.3), auto_dismiss=False)
        p.open()
        Clock.schedule_once(lambda dt: p.dismiss(), 1.2)


# ============================================================
# CS2 饰品页面
# ============================================================
class CS2Screen(Screen):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.name = "cs2"
        self.box = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(6))
        top = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(8))
        top.add_widget(Label(text="CS2 饰品库存", bold=True, font_size=dp(18),
                             color=(0.2, 0.2, 0.25, 1)))
        add_btn = Button(text="＋ 录入", background_color=ACCENT)
        add_btn.bind(on_press=lambda x: self.open_add_form())
        refresh_btn = Button(text="🔄 刷新价", background_color=GREEN)
        refresh_btn.bind(on_press=lambda x: self.refresh_prices())
        top.add_widget(add_btn)
        top.add_widget(refresh_btn)
        self.box.add_widget(top)
        self.hint = Label(text="提示：饰品名称请用英文全名，便于匹配价格",
                          size_hint_y=None, height=dp(22), font_size=dp(12),
                          color=(0.6, 0.4, 0.2, 1))
        self.box.add_widget(self.hint)

        self.body = BoxLayout(orientation="vertical", size_hint_y=None)
        self.box.add_widget(make_scroll(self.body))
        self.add_widget(self.box)
        Clock.schedule_once(lambda dt: self.refresh())

    def refresh(self, *args):
        self.body.clear_widgets()
        rows = db.get_cs2_items()
        if not rows:
            self.body.add_widget(Label(text="暂无饰品，点＋录入", color=(0.5, 0.5, 0.55, 1),
                                       size_hint_y=None, height=dp(40)))
            return
        head = Label(text="饰品      单价      盈亏      总市值", size_hint_y=None,
                     height=dp(26), bold=True, color=(0.3, 0.3, 0.35, 1))
        self.body.add_widget(head)
        for r in rows:
            market_val = r["quantity"] * r["current_price"]
            cost_val = r["quantity"] * r["cost_price"]
            pnl = market_val - cost_val
            pnl_color = GREEN if pnl >= 0 else RED
            sk = "StatTrak " if r["stattrak"] else ""
            wear = r["wear"].upper() or "-"
            line = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(4))
            line.add_widget(Label(text=f"{sk}{r['name']}\n[{wear}] x{r['quantity']}",
                                  size_hint_x=0.42, color=(0.25, 0.25, 0.3, 1),
                                  font_size=dp(12), halign="left"))
            line.add_widget(Label(text=f"{r['current_price']:.2f}" if r["current_price"] else "--",
                                  size_hint_x=0.16, color=(0.3, 0.3, 0.35, 1)))
            line.add_widget(Label(text=f"{pnl:+.0f}" if r["current_price"] else "--",
                                  size_hint_x=0.18, color=pnl_color, bold=True))
            line.add_widget(Label(text=money(market_val), size_hint_x=0.2,
                                  color=(0.25, 0.25, 0.3, 1)))
            del_btn = Button(text="✕", size_hint_x=0.04, background_color=(0.9, 0.6, 0.6, 1),
                             color=(1, 1, 1, 1))
            del_btn.bind(on_press=lambda b, iid=r["id"]: self.delete_row(iid))
            line.add_widget(del_btn)
            self.body.add_widget(line)

    def open_add_form(self):
        box = BoxLayout(orientation="vertical", spacing=dp(6), padding=dp(10))
        box.add_widget(field_label("饰品英文全名（如 AK-47 | Redline）"))
        name_in = TextInput(size_hint_y=None, height=dp(40))
        box.add_widget(name_in)
        box.add_widget(field_label("磨损"))
        wear_sp = Spinner(text="FT", values=["FN", "MW", "FT", "WW", "BS", "无"],
                          size_hint_y=None, height=dp(40))
        box.add_widget(wear_sp)
        box.add_widget(field_label("是否暗金 StatTrak"))
        st_sp = Spinner(text="否", values=["否", "是"], size_hint_y=None, height=dp(40))
        box.add_widget(st_sp)
        box.add_widget(field_label("数量"))
        qty_in = TextInput(input_filter="int", text="1", size_hint_y=None, height=dp(40))
        box.add_widget(qty_in)
        box.add_widget(field_label("购入单价（人民币）"))
        cost_in = TextInput(input_filter="float", size_hint_y=None, height=dp(40))
        box.add_widget(cost_in)
        popup = Popup(title="录入饰品", content=box, size_hint=(0.85, 0.95))

        def submit(btn):
            try:
                qty = int(qty_in.text)
                cost = float(cost_in.text)
            except ValueError:
                return
            wear = "" if wear_sp.text == "无" else wear_sp.text
            st = 1 if st_sp.text == "是" else 0
            db.add_cs2_item(name_in.text.strip(), wear, st, qty, cost)
            popup.dismiss()
            self.refresh()
        box.add_widget(Button(text="保存", background_color=ACCENT, size_hint_y=None,
                              height=dp(44), on_press=submit))
        popup.open()

    def delete_row(self, iid):
        p = Popup(title="删除该饰品？",
                  content=Button(text="确认删除", background_color=RED, color=(1, 1, 1, 1)),
                  size_hint=(0.7, 0.35))
        p.content.bind(on_press=lambda b: (db.delete_cs2_item(iid), p.dismiss(), self.refresh()))
        p.open()

    def refresh_prices(self):
        """后台线程刷新所有饰品价格"""
        def work():
            items = [dict(r) for r in db.get_cs2_items()]
            results, _ = pf.refresh_cs2_prices(items)
            for res in results:
                if res["found"] and res["price_cny"]:
                    db.update_cs2_price(res["id"], res["price_cny"])
            Clock.schedule_once(lambda dt: self.refresh())
        t = threading.Thread(target=work, daemon=True)
        t.start()
        p = Popup(title="刷新中", content=Label(text="正在下载饰品行情表并匹配…\n首次约需1-2分钟"),
                  size_hint=(0.8, 0.35), auto_dismiss=False)
        p.open()
        Clock.schedule_once(lambda dt: p.dismiss(), 1.5)


# ============================================================
# 现金资产管理页面（简单内嵌在仪表盘按钮里）
# ============================================================
class CashScreen(Screen):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.name = "cash"
        box = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(6))
        top = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(8))
        top.add_widget(Label(text="现金资产", bold=True, font_size=dp(18),
                             color=(0.2, 0.2, 0.25, 1)))
        add_btn = Button(text="＋ 添加账户", background_color=ACCENT)
        add_btn.bind(on_press=lambda x: self.open_add_form())
        top.add_widget(add_btn)
        box.add_widget(top)
        self.body = BoxLayout(orientation="vertical", size_hint_y=None)
        box.add_widget(make_scroll(self.body))
        self.add_widget(box)
        Clock.schedule_once(lambda dt: self.refresh())

    def refresh(self, *args):
        self.body.clear_widgets()
        rows = db.get_cash_assets()
        if not rows:
            self.body.add_widget(Label(text="暂无账户，点＋添加", color=(0.5, 0.5, 0.55, 1),
                                       size_hint_y=None, height=dp(40)))
            return
        for r in rows:
            line = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(6))
            line.add_widget(Label(text=f"{r['name']}", size_hint_x=0.4,
                                  color=(0.25, 0.25, 0.3, 1)))
            line.add_widget(Label(text=money(r["amount"]), size_hint_x=0.3,
                                  color=ACCENT, bold=True))
            del_btn = Button(text="✕", size_hint_x=0.3, background_color=(0.9, 0.6, 0.6, 1),
                             color=(1, 1, 1, 1))
            del_btn.bind(on_press=lambda b, aid=r["id"]: self.delete_row(aid))
            line.add_widget(del_btn)
            self.body.add_widget(line)

    def open_add_form(self):
        box = BoxLayout(orientation="vertical", spacing=dp(8), padding=dp(10))
        box.add_widget(field_label("账户名（如 招商银行卡 / 零钱 / 公积金）"))
        name_in = TextInput(size_hint_y=None, height=dp(40))
        box.add_widget(name_in)
        box.add_widget(field_label("余额（元）"))
        amt_in = TextInput(input_filter="float", size_hint_y=None, height=dp(40))
        box.add_widget(amt_in)
        popup = Popup(title="添加账户", content=box, size_hint=(0.85, 0.5))
        def submit(btn):
            try:
                amt = float(amt_in.text)
            except ValueError:
                return
            db.add_cash_asset(name_in.text.strip(), amt)
            popup.dismiss()
            self.refresh()
        box.add_widget(Button(text="保存", background_color=ACCENT, size_hint_y=None,
                              height=dp(44), on_press=submit))
        popup.open()

    def delete_row(self, aid):
        p = Popup(title="删除该账户？",
                  content=Button(text="确认删除", background_color=RED, color=(1, 1, 1, 1)),
                  size_hint=(0.7, 0.35))
        p.content.bind(on_press=lambda b: (db.delete_cash_asset(aid), p.dismiss(), self.refresh()))
        p.open()


# ============================================================
# 工资计算器弹窗（参数来自「个人收支规划表」基础参数）
# ============================================================
def open_salary_calculator():
    box = BoxLayout(orientation="vertical", spacing=dp(6), padding=dp(10))
    box.add_widget(field_label("月基本工资（元）"))
    base_in = TextInput(text=str(db.SALARY_DEFAULTS["base"]), input_filter="float",
                        size_hint_y=None, height=dp(40))
    box.add_widget(base_in)
    box.add_widget(field_label("学历补贴（元/月）"))
    edu_in = TextInput(text=str(db.SALARY_DEFAULTS["edu"]), input_filter="float",
                       size_hint_y=None, height=dp(40))
    box.add_widget(edu_in)
    box.add_widget(field_label("从教津贴（元/月，满1年后600）"))
    teach_in = TextInput(text=str(db.SALARY_DEFAULTS["teach"]), input_filter="float",
                         size_hint_y=None, height=dp(40))
    box.add_widget(teach_in)

    result_label = Label(text="", size_hint_y=None, height=dp(170),
                         color=(0.2, 0.2, 0.25, 1), halign="left", valign="top")
    result_label.bind(size=result_label.setter("text_size"))
    box.add_widget(result_label)
    popup = Popup(title="工资计算", content=box, size_hint=(0.88, 0.92))

    def calc(btn):
        try:
            base = float(base_in.text or 0)
            edu = float(edu_in.text or 0)
            teach = float(teach_in.text or 0)
        except ValueError:
            return
        s = db.calc_salary(base, edu, teach)
        result_label.text = (
            f"税前总收入：{money(s['gross'])}\n"
            f"养老 {money(s['pension'])}   医疗 {money(s['medical'])}   失业 {money(s['unemployment'])}\n"
            f"公积金（个人）{money(s['fund_personal'])}   （单位入账）{money(s['fund_company'])}\n"
            f"五险一金个人合计：{money(s['social_total'])}\n"
            f"个人所得税（3%简化）：{money(s['tax'])}\n"
            f"每月到手现金：{money(s['net'])}"
        )

    box.add_widget(Button(text="计算", background_color=ACCENT, size_hint_y=None,
                          height=dp(44), on_press=calc))
    popup.open()


# ============================================================
# 预算页面（月度支出预算，来源「个人收支规划表」）
# ============================================================
class BudgetScreen(Screen):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.name = "budget"
        self.month_selector = None
        box = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(6))
        top = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(8))
        top.add_widget(Label(text="月度预算", bold=True, font_size=dp(18),
                             color=(0.2, 0.2, 0.25, 1)))
        edit_btn = Button(text="＋ 设置预算", background_color=ACCENT)
        edit_btn.bind(on_press=lambda x: self.open_edit_form())
        self.month_selector = Spinner(text="本月", values=["本月", "全部"],
                                      size_hint_x=0.4)
        self.month_selector.bind(text=lambda *a: self.refresh())
        top.add_widget(edit_btn)
        top.add_widget(self.month_selector)
        box.add_widget(top)

        self.summary = Label(text="", size_hint_y=None, height=dp(30),
                             color=(0.3, 0.3, 0.35, 1))
        box.add_widget(self.summary)
        self.body = BoxLayout(orientation="vertical", size_hint_y=None)
        box.add_widget(make_scroll(self.body))
        self.add_widget(box)
        Clock.schedule_once(lambda dt: self.refresh())

    def refresh(self, *args):
        self.body.clear_widgets()
        month = None if self.month_selector.text == "全部" else \
            __import__("datetime").date.today().strftime("%Y-%m")
        budgets = db.get_budgets()
        spending = db.get_category_spending(month)
        total_budget = sum(budgets.values())
        total_spent = sum(spending.values())
        remain = total_budget - total_spent
        self.summary.text = (f"本月已花 {money(total_spent)} / 预算 {money(total_budget)}"
                             f"   剩余 {money(remain)}")
        for cat in EXPENSE_CATEGORIES:
            budget = budgets.get(cat, 0)
            spent = spending.get(cat, 0)
            remain_c = budget - spent
            pct = (spent / budget) if budget > 0 else 0
            bar_len = int(min(pct, 1.0) * 20)
            bar = "█" * bar_len + "░" * (20 - bar_len)
            color = RED if (budget > 0 and spent > budget) else (0.3, 0.3, 0.35, 1)
            line = BoxLayout(orientation="vertical", size_hint_y=None,
                             height=dp(50), spacing=dp(2))
            line.add_widget(Label(
                text=f"{cat}  已花 {money(spent)} / {money(budget)}  （剩 {money(remain_c)}）",
                size_hint_y=None, height=dp(24), color=(0.25, 0.25, 0.3, 1),
                halign="left"))
            line.add_widget(Label(text=f"{bar} {pct * 100:.0f}%",
                                  size_hint_y=None, height=dp(22), color=color,
                                  halign="left"))
            self.body.add_widget(line)

    def open_edit_form(self):
        box = BoxLayout(orientation="vertical", spacing=dp(6), padding=dp(10))
        box.add_widget(field_label("类别"))
        cat_sp = Spinner(text="住房", values=EXPENSE_CATEGORIES,
                         size_hint_y=None, height=dp(40))
        box.add_widget(cat_sp)
        box.add_widget(field_label("月预算（元）"))
        amt_in = TextInput(input_filter="float", size_hint_y=None, height=dp(40))
        box.add_widget(amt_in)
        popup = Popup(title="设置预算", content=box, size_hint=(0.85, 0.5))

        def submit(btn):
            try:
                amt = float(amt_in.text)
            except ValueError:
                return
            db.set_budget(cat_sp.text, amt)
            popup.dismiss()
            self.refresh()
        box.add_widget(Button(text="保存", background_color=ACCENT, size_hint_y=None,
                              height=dp(44), on_press=submit))
        popup.open()


# ============================================================
# 主程序：底部导航 + 页面切换
# ============================================================
class AssetApp(App):
    title = "我的资产账本"

    def build(self):
        db.init_db()
        sm = ScreenManager()
        sm.add_widget(DashboardScreen())
        sm.add_widget(LedgerScreen())
        sm.add_widget(BudgetScreen())
        sm.add_widget(CashScreen())
        sm.add_widget(StocksScreen())
        sm.add_widget(CS2Screen())

        # 底部导航
        nav = BoxLayout(size_hint_y=None, height=dp(54), orientation="horizontal",
                        spacing=dp(2), padding=[2, 4, 2, 2])
        items = [
            ("🏠", "仪表盘", "dashboard"),
            ("📒", "记账", "ledger"),
            ("🎯", "预算", "budget"),
            ("💰", "现金", "cash"),
            ("📈", "股票", "stocks"),
            ("🎮", "饰品", "cs2"),
        ]
        for icon, text, screen_name in items:
            btn = Button(text=f"{icon}\n{text}", font_size=dp(11), halign="center",
                         background_color=(0.92, 0.93, 0.96, 1),
                         color=(0.2, 0.2, 0.25, 1))
            btn.bind(on_press=lambda b, s=screen_name: setattr(sm, 'current', s))
            nav.add_widget(btn)

        root = BoxLayout(orientation="vertical")
        root.add_widget(sm)
        root.add_widget(nav)
        return root


if __name__ == "__main__":
    AssetApp().run()
