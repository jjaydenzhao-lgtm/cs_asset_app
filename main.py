# -*- coding: utf-8 -*-
"""
main.py —— 我的资产账本（KivyMD Material Design 版）
=====================================================
技术栈：KivyMD（Material Design 组件库，蓝白主题）+ 本地 SQLite
功能：仪表盘 / 记账 / 预算 / 现金 / 股票 / CS2 饰品 / 工资计算

本地运行（需 Python 3.11）：
    pip install kivy kivymd requests
    python main.py
"""

import threading
import datetime

from kivy.metrics import dp
from kivy.clock import Clock
from kivy.uix.screenmanager import ScreenManager
from kivy.uix.popup import Popup

from kivymd.app import MDApp
from kivymd.uix.screen import MDScreen
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.gridlayout import MDGridLayout
from kivymd.uix.label import MDLabel
from kivymd.uix.button import MDButton, MDButtonText, MDIconButton
from kivymd.uix.card import MDCard
from kivymd.uix.textfield import MDTextField, MDTextFieldHintText
from kivymd.uix.scrollview import MDScrollView
from kivymd.uix.divider import MDDivider

import database as db
import price_fetcher as pf


# ============================================================
# 常量
# ============================================================
GREEN = (0.16, 0.67, 0.36, 1)      # 盈利/收入绿
RED = (0.86, 0.26, 0.26, 1)        # 亏损/支出红
DARK = (0.16, 0.18, 0.22, 1)       # 正文深色
GRAY = (0.45, 0.48, 0.55, 1)       # 次要文字

EXPENSE_CATEGORIES = ["住房", "通讯", "交通", "饮食", "衣物", "医疗",
                      "娱乐", "学习", "健身", "其他"]
INCOME_CATEGORIES = ["工资", "补贴", "津贴", "兼职", "红包", "其他"]
PAY_METHODS = ["现金", "微信", "支付宝", "银行卡", "其他"]


def money(v):
    """格式化金额，带千分位"""
    try:
        return f"¥{float(v):,.2f}"
    except Exception:
        return "¥0.00"


def today():
    return datetime.date.today()


def this_month():
    return today().strftime("%Y-%m")


def make_scroll(body):
    """把内容放进可滚动容器"""
    root = MDScrollView()
    inner = MDBoxLayout(orientation="vertical", size_hint_y=None,
                        padding=[dp(16), dp(12), dp(16), dp(90)],
                        spacing=dp(10))
    inner.bind(minimum_height=inner.setter("height"))
    inner.add_widget(body)
    root.add_widget(inner)
    return root


def section_title(text):
    return MDLabel(
        text=text, font_style="Title", role="medium",
        theme_text_color="Custom", text_color=DARK,
        size_hint_y=None, height=dp(36), adaptive_height=True,
    )


def field(label_text, hint):
    """带标签的输入框（用于表单弹窗）"""
    box = MDBoxLayout(orientation="vertical", size_hint_y=None,
                      height=dp(76), spacing=dp(4), adaptive_height=True)
    box.add_widget(MDLabel(text=label_text, font_style="Label", role="small",
                           theme_text_color="Custom", text_color=GRAY,
                           size_hint_y=None, height=dp(20)))
    tf = MDTextField(
        MDTextFieldHintText(text=hint),
        size_hint_y=None, height=dp(50),
        mode="outlined",
    )
    box.add_widget(tf)
    return box, tf


# ============================================================
# 仪表盘
# ============================================================
class DashboardScreen(MDScreen):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.name = "dashboard"

        root = MDBoxLayout(orientation="vertical", spacing=0)
        # 顶部标题栏（蓝底白字）
        header = MDBoxLayout(orientation="vertical", size_hint_y=None,
                             height=dp(160), padding=[dp(20), dp(24), dp(20), dp(16)],
                             spacing=dp(6), md_bg_color=(0.14, 0.44, 0.85, 1))
        header.add_widget(MDLabel(text="总资产", font_style="Label", role="small",
                                  theme_text_color="Custom", text_color=(1, 1, 1, 0.85),
                                  size_hint_y=None, height=dp(20)))
        self.total_label = MDLabel(text="¥0.00", font_style="Headline", role="large",
                                   theme_text_color="Custom", text_color=(1, 1, 1, 1),
                                   size_hint_y=None, height=dp(52))
        header.add_widget(self.total_label)
        self.month_label = MDLabel(text="", font_style="Label",
                                   theme_text_color="Custom", text_color=(1, 1, 1, 0.9),
                                   size_hint_y=None, height=dp(24))
        header.add_widget(self.month_label)
        root.add_widget(header)

        # 资产分类卡片
        self.card_grid = MDGridLayout(cols=3, spacing=dp(10), size_hint_y=None,
                                      height=dp(96), padding=[dp(16), dp(12), dp(16), 0])
        root.add_widget(self.card_grid)

        # 预算进度
        self.budget_title = section_title("本月预算")
        self.budget_bar = MDLabel(text="", size_hint_y=None, height=dp(30),
                                  theme_text_color="Custom", text_color=GRAY)
        # 净值走势
        self.trend_title = section_title("净值走势")
        self.trend_label = MDLabel(text="", size_hint_y=None, height=dp(50),
                                   theme_text_color="Custom", text_color=GRAY)

        # 按钮区
        actions = MDBoxLayout(orientation="horizontal", size_hint_y=None,
                              height=dp(50), spacing=dp(10),
                              padding=[dp(16), 0, dp(16), 0])
        snap_btn = MDButton(
            MDButtonText(text="保存今日快照"),
            style="filled", theme_bg_color="Primary",
            size_hint_x=1,
        )
        snap_btn.bind(on_release=lambda *_: self.save_snapshot())
        salary_btn = MDButton(
            MDButtonText(text="工资计算"),
            style="tonal", theme_bg_color="Primary",
            size_hint_x=1,
        )
        salary_btn.bind(on_release=lambda *_: open_salary_calculator())
        actions.add_widget(snap_btn)
        actions.add_widget(salary_btn)

        body = MDBoxLayout(orientation="vertical", size_hint_y=None,
                           spacing=dp(6), adaptive_height=True)
        body.add_widget(self.budget_title)
        body.add_widget(self.budget_bar)
        body.add_widget(MDDivider())
        body.add_widget(self.trend_title)
        body.add_widget(self.trend_label)
        body.add_widget(actions)
        body.bind(minimum_height=body.setter("height"))

        root.add_widget(make_scroll(body))
        self.add_widget(root)
        Clock.schedule_once(lambda dt: self.refresh())

    def refresh(self, *args):
        stock_val = db.get_stock_total_value()
        cs2_val = db.get_cs2_total_value()
        cash_val = db.get_cash_total()
        total = stock_val + cs2_val + cash_val
        self.total_label.text = money(total)

        month = this_month()
        income, expense = db.get_month_summary(month)
        self.month_label.text = f"{month}  收入 {money(income)}   支出 {money(expense)}"

        # 资产卡片
        self.card_grid.clear_widgets()
        cards = [
            ("现金", cash_val, (0.14, 0.44, 0.85, 1)),
            ("股票", stock_val, GREEN),
            ("饰品", cs2_val, (0.90, 0.55, 0.15, 1)),
        ]
        for title, val, color in cards:
            self.card_grid.add_widget(self._mini_card(title, val, color))

        # 预算进度
        budgets = db.get_budgets()
        spent = db.get_category_spending(month)
        total_budget = sum(budgets.values())
        total_spent = sum(spent.values())
        remain = total_budget - total_spent
        pct = (total_spent / total_budget * 100) if total_budget > 0 else 0
        bar_len = int(min(pct / 100, 1.0) * 24)
        bar = "█" * bar_len + "░" * (24 - bar_len)
        self.budget_bar.text = (f"已花 {money(total_spent)} / 预算 {money(total_budget)}"
                                f"   剩余 {money(remain)}\n{bar} {pct:.0f}%")

        # 净值走势
        snaps = db.get_snapshots()[-7:]
        if snaps:
            lines = "  |  ".join(f"{s['date'][5:]} {s['total']:.0f}" for s in snaps)
            self.trend_label.text = lines
        else:
            self.trend_label.text = "（点击「保存今日快照」后显示净值走势）"

    def _mini_card(self, title, val, color):
        card = MDCard(
            MDBoxLayout(
                MDLabel(text=title, font_style="Label", role="small",
                        theme_text_color="Custom", text_color=GRAY,
                        size_hint_y=None, height=dp(20), halign="center"),
                MDLabel(text=money(val), font_style="Title", role="large",
                        theme_text_color="Custom", text_color=color,
                        size_hint_y=None, height=dp(30), halign="center",
                        adaptive_height=True),
                orientation="vertical", padding=[dp(4), dp(12), dp(4), dp(8)],
                spacing=dp(4),
            ),
            style="elevated", size_hint_y=None, height=dp(76), radius=dp(16),
            md_bg_color=(1, 1, 1, 1),
        )
        return card

    def save_snapshot(self):
        total = db.save_snapshot()
        p = Popup(title="已保存", size_hint=(0.7, 0.32),
                  content=MDLabel(text=f"今日快照已保存\n总资产 {money(total)}",
                                  halign="center"))
        p.open()
        Clock.schedule_once(lambda dt: self.refresh(), 0.1)


# ============================================================
# 记账页
# ============================================================
class LedgerScreen(MDScreen):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.name = "ledger"
        self.show_all = False

        root = MDBoxLayout(orientation="vertical", spacing=0)
        # 顶部操作栏
        bar = MDBoxLayout(orientation="horizontal", size_hint_y=None,
                          height=dp(56), padding=[dp(16), dp(8), dp(16), dp(8)],
                          spacing=dp(10))
        self.month_btn = MDButton(
            MDButtonText(text="本月"),
            style="outlined", theme_bg_color="Primary",
            size_hint_x=None,
        )
        self.month_btn.bind(on_release=lambda *_: self.toggle_month())
        add_btn = MDButton(
            MDButtonText(text="＋ 记一笔"),
            style="filled", theme_bg_color="Primary", size_hint_x=1,
        )
        add_btn.bind(on_release=lambda *_: open_ledger_form(self))
        bar.add_widget(self.month_btn)
        bar.add_widget(add_btn)
        root.add_widget(bar)
        root.add_widget(MDDivider())

        self.body = MDBoxLayout(orientation="vertical", size_hint_y=None,
                                spacing=dp(8), adaptive_height=True)
        root.add_widget(make_scroll(self.body))
        self.add_widget(root)
        Clock.schedule_once(lambda dt: self.refresh())

    def toggle_month(self):
        self.show_all = not self.show_all
        self.month_btn.children[0].text = "全部" if self.show_all else "本月"
        self.refresh()

    def refresh(self, *args):
        self.body.clear_widgets()
        month = None if self.show_all else this_month()
        rows = db.get_transactions(month)
        if not rows:
            self.body.add_widget(MDLabel(
                text="暂无记录，点右上角「记一笔」", font_style="Body",
                theme_text_color="Custom", text_color=GRAY,
                size_hint_y=None, height=dp(60), halign="center"))
            return
        for r in rows:
            is_income = r["type"] == "income"
            tag = "收" if is_income else "支"
            color = GREEN if is_income else RED
            amount = f"{'+' if is_income else '-'}{money(r['amount'])}"

            card = MDCard(
                MDBoxLayout(
                    # 左侧：类别 + 支付方式
                    MDBoxLayout(
                        MDLabel(text=f"{r['category']}", font_style="Body",
                                role="medium", theme_text_color="Custom",
                                text_color=DARK, size_hint_y=None, height=dp(24),
                                halign="left"),
                        MDLabel(text=f"{r['date']}  ·  {r['payment'] or '—'}",
                                font_style="Label", role="small",
                                theme_text_color="Custom", text_color=GRAY,
                                size_hint_y=None, height=dp(18), halign="left"),
                        orientation="vertical", size_hint_x=1, spacing=dp(2),
                    ),
                    # 右侧：金额 + 删除
                    MDLabel(text=amount, font_style="Title", role="large",
                            theme_text_color="Custom", text_color=color,
                            size_hint_x=None, width=dp(110), halign="right"),
                    MDIconButton(icon="delete", style="standard",
                                 theme_icon_color="Error",
                                 size_hint_x=None),
                    orientation="horizontal", padding=[dp(14), dp(12), dp(4), dp(12)],
                    spacing=dp(8), adaptive_height=True,
                ),
                style="elevated", size_hint_y=None, height=dp(72),
                radius=dp(16), md_bg_color=(1, 1, 1, 1),
            )
            # 绑定删除
            del_btn = card.children[0].children[0]
            del_btn.bind(on_release=lambda b, tid=r["id"]: self.confirm_delete(tid))
            self.body.add_widget(card)

            if r["note"]:
                self.body.add_widget(MDLabel(
                    text="   备注：" + r["note"], font_style="Label", role="small",
                    theme_text_color="Custom", text_color=GRAY,
                    size_hint_y=None, height=dp(20)))

    def confirm_delete(self, tid):
        p = Popup(title="删除这条记录？", size_hint=(0.72, 0.3),
                  content=MDButton(
                      MDButtonText(text="确认删除"),
                      style="filled", theme_bg_color="Custom",
                      md_bg_color=(0.86, 0.26, 0.26, 1),
                      size_hint_y=None, height=dp(48),
                  ))
        p.content.bind(on_release=lambda b: (db.delete_transaction(tid),
                                             p.dismiss(), self.refresh()))
        p.open()


# ============================================================
# 预算页
# ============================================================
class BudgetScreen(MDScreen):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.name = "budget"
        root = MDBoxLayout(orientation="vertical", spacing=0)
        bar = MDBoxLayout(orientation="horizontal", size_hint_y=None,
                          height=dp(56), padding=[dp(16), dp(8), dp(16), dp(8)],
                          spacing=dp(10))
        self.summary = MDLabel(text="", font_style="Label", role="medium",
                               theme_text_color="Custom", text_color=DARK,
                               size_hint_x=1)
        edit_btn = MDButton(
            MDButtonText(text="设置预算"),
            style="filled", theme_bg_color="Primary",
        )
        edit_btn.bind(on_release=lambda *_: open_budget_form(self))
        bar.add_widget(self.summary)
        bar.add_widget(edit_btn)
        root.add_widget(bar)
        root.add_widget(MDDivider())

        self.body = MDBoxLayout(orientation="vertical", size_hint_y=None,
                                spacing=dp(8), adaptive_height=True)
        root.add_widget(make_scroll(self.body))
        self.add_widget(root)
        Clock.schedule_once(lambda dt: self.refresh())

    def refresh(self, *args):
        self.body.clear_widgets()
        month = this_month()
        budgets = db.get_budgets()
        spending = db.get_category_spending(month)
        total_budget = sum(budgets.values())
        total_spent = sum(spending.values())
        self.summary.text = f"已花 {money(total_spent)} / {money(total_budget)}"

        for cat in EXPENSE_CATEGORIES:
            budget = budgets.get(cat, 0)
            spent = spending.get(cat, 0)
            remain = budget - spent
            pct = (spent / budget * 100) if budget > 0 else 0
            over = budget > 0 and spent > budget
            bar_len = int(min(pct / 100, 1.0) * 22)
            bar = "█" * bar_len + "░" * (22 - bar_len)
            color = RED if over else DARK

            card = MDCard(
                MDBoxLayout(
                    MDBoxLayout(
                        MDLabel(text=cat, font_style="Body", role="medium",
                                theme_text_color="Custom", text_color=DARK,
                                size_hint_y=None, height=dp(24), halign="left"),
                        MDLabel(text=f"已花 {money(spent)} / {money(budget)}",
                                font_style="Label", role="small",
                                theme_text_color="Custom", text_color=GRAY,
                                size_hint_y=None, height=dp(18), halign="left"),
                        orientation="vertical", size_hint_x=1, spacing=dp(2),
                    ),
                    MDLabel(text=f"剩 {money(remain)}" if remain >= 0 else f"超 {money(-remain)}",
                            font_style="Body", role="medium",
                            theme_text_color="Custom", text_color=color,
                            size_hint_x=None, width=dp(110), halign="right"),
                    orientation="horizontal", padding=[dp(14), dp(10), dp(14), dp(4)],
                    spacing=dp(8), adaptive_height=True,
                ),
                style="elevated", size_hint_y=None, height=dp(72),
                radius=dp(16), md_bg_color=(1, 1, 1, 1),
            )
            # 进度条单独一行
            bar_label = MDLabel(text=f"  {bar} {pct:.0f}%",
                                font_style="Label", role="small",
                                theme_text_color="Custom", text_color=color,
                                size_hint_y=None, height=dp(20))
            wrapper = MDBoxLayout(orientation="vertical", size_hint_y=None,
                                  height=dp(92), spacing=dp(0), adaptive_height=True)
            wrapper.add_widget(card)
            wrapper.add_widget(bar_label)
            self.body.add_widget(wrapper)


# ============================================================
# 现金资产页
# ============================================================
class CashScreen(MDScreen):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.name = "cash"
        root = MDBoxLayout(orientation="vertical", spacing=0)
        bar = MDBoxLayout(orientation="horizontal", size_hint_y=None,
                          height=dp(56), padding=[dp(16), dp(8), dp(16), dp(8)],
                          spacing=dp(10))
        bar.add_widget(MDLabel(text="现金资产", font_style="Title", role="large",
                               theme_text_color="Custom", text_color=DARK,
                               size_hint_x=1))
        add_btn = MDButton(
            MDButtonText(text="＋ 添加账户"),
            style="filled", theme_bg_color="Primary",
        )
        add_btn.bind(on_release=lambda *_: open_cash_form(self))
        bar.add_widget(add_btn)
        root.add_widget(bar)
        root.add_widget(MDDivider())

        self.body = MDBoxLayout(orientation="vertical", size_hint_y=None,
                                spacing=dp(8), adaptive_height=True)
        root.add_widget(make_scroll(self.body))
        self.add_widget(root)
        Clock.schedule_once(lambda dt: self.refresh())

    def refresh(self, *args):
        self.body.clear_widgets()
        rows = db.get_cash_assets()
        if not rows:
            self.body.add_widget(MDLabel(text="暂无账户，点右上角添加",
                                         font_style="Body", theme_text_color="Custom",
                                         text_color=GRAY, size_hint_y=None,
                                         height=dp(60), halign="center"))
            return
        for r in rows:
            card = MDCard(
                MDBoxLayout(
                    MDBoxLayout(
                        MDLabel(text=r["name"], font_style="Body", role="medium",
                                theme_text_color="Custom", text_color=DARK,
                                size_hint_y=None, height=dp(24), halign="left"),
                        MDLabel(text="更新于 " + (r["updated_date"] or ""),
                                font_style="Label", role="small",
                                theme_text_color="Custom", text_color=GRAY,
                                size_hint_y=None, height=dp(18), halign="left"),
                        orientation="vertical", size_hint_x=1, spacing=dp(2),
                    ),
                    MDLabel(text=money(r["amount"]), font_style="Title", role="large",
                            theme_text_color="Custom",
                            text_color=(0.14, 0.44, 0.85, 1),
                            size_hint_x=None, width=dp(130), halign="right"),
                    MDIconButton(icon="delete", style="standard",
                                 theme_icon_color="Error", size_hint_x=None),
                    orientation="horizontal", padding=[dp(14), dp(12), dp(4), dp(12)],
                    spacing=dp(8), adaptive_height=True,
                ),
                style="elevated", size_hint_y=None, height=dp(72),
                radius=dp(16), md_bg_color=(1, 1, 1, 1),
            )
            del_btn = card.children[0].children[0]
            del_btn.bind(on_release=lambda b, aid=r["id"]: self.confirm_delete(aid))
            self.body.add_widget(card)

    def confirm_delete(self, aid):
        p = Popup(title="删除该账户？", size_hint=(0.72, 0.3),
                  content=MDButton(MDButtonText(text="确认删除"),
                                   style="filled", theme_bg_color="Custom",
                      md_bg_color=(0.86, 0.26, 0.26, 1),
                                   size_hint_y=None, height=dp(48)))
        p.content.bind(on_release=lambda b: (db.delete_cash_asset(aid),
                                             p.dismiss(), self.refresh()))
        p.open()


# ============================================================
# 股票页
# ============================================================
class StocksScreen(MDScreen):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.name = "stocks"
        root = MDBoxLayout(orientation="vertical", spacing=0)
        bar = MDBoxLayout(orientation="horizontal", size_hint_y=None,
                          height=dp(56), padding=[dp(16), dp(8), dp(16), dp(8)],
                          spacing=dp(10))
        bar.add_widget(MDLabel(text="股票持仓", font_style="Title", role="large",
                               theme_text_color="Custom", text_color=DARK,
                               size_hint_x=1))
        add_btn = MDButton(MDButtonText(text="＋"), style="filled",
                           theme_bg_color="Primary")
        add_btn.bind(on_release=lambda *_: open_stock_form(self))
        refresh_btn = MDButton(MDButtonText(text="刷新价"), style="tonal",
                               theme_bg_color="Primary")
        refresh_btn.bind(on_release=lambda *_: self.refresh_prices())
        bar.add_widget(add_btn)
        bar.add_widget(refresh_btn)
        root.add_widget(bar)
        root.add_widget(MDDivider())

        self.body = MDBoxLayout(orientation="vertical", size_hint_y=None,
                                spacing=dp(8), adaptive_height=True)
        root.add_widget(make_scroll(self.body))
        self.add_widget(root)
        Clock.schedule_once(lambda dt: self.refresh())

    def refresh(self, *args):
        self.body.clear_widgets()
        rows = db.get_stocks()
        if not rows:
            self.body.add_widget(MDLabel(text="暂无持仓，点＋加仓",
                                         font_style="Body", theme_text_color="Custom",
                                         text_color=GRAY, size_hint_y=None,
                                         height=dp(60), halign="center"))
            return
        for r in rows:
            market_val = r["shares"] * r["current_price"]
            cost_val = r["shares"] * r["cost_price"]
            pnl = market_val - cost_val
            pnl_color = GREEN if pnl >= 0 else RED
            cur = f"{r['current_price']:.2f}" if r["current_price"] else "--"
            pnl_text = f"{pnl:+.0f}" if r["current_price"] else "--"

            card = MDCard(
                MDBoxLayout(
                    MDBoxLayout(
                        MDLabel(text=f"{r['name']}", font_style="Body", role="medium",
                                theme_text_color="Custom", text_color=DARK,
                                size_hint_y=None, height=dp(24), halign="left"),
                        MDLabel(text=f"{r['market'].upper()}:{r['code']}  ×{r['shares']:g}",
                                font_style="Label", role="small",
                                theme_text_color="Custom", text_color=GRAY,
                                size_hint_y=None, height=dp(18), halign="left"),
                        orientation="vertical", size_hint_x=1, spacing=dp(2),
                    ),
                    MDBoxLayout(
                        MDLabel(text=cur, font_style="Title", role="large",
                                theme_text_color="Custom", text_color=DARK,
                                size_hint_y=None, height=dp(26), halign="right"),
                        MDLabel(text=pnl_text, font_style="Label", role="medium",
                                theme_text_color="Custom", text_color=pnl_color,
                                size_hint_y=None, height=dp(20), halign="right"),
                        orientation="vertical", size_hint_x=None, width=dp(90), spacing=dp(0),
                    ),
                    MDIconButton(icon="delete", style="standard",
                                 theme_icon_color="Error", size_hint_x=None),
                    orientation="horizontal", padding=[dp(14), dp(10), dp(4), dp(10)],
                    spacing=dp(8), adaptive_height=True,
                ),
                style="elevated", size_hint_y=None, height=dp(76),
                radius=dp(16), md_bg_color=(1, 1, 1, 1),
            )
            del_btn = card.children[0].children[0]
            del_btn.bind(on_release=lambda b, sid=r["id"]: self.confirm_delete(sid))
            self.body.add_widget(card)

    def confirm_delete(self, sid):
        p = Popup(title="删除该持仓？", size_hint=(0.72, 0.3),
                  content=MDButton(MDButtonText(text="确认删除"),
                                   style="filled", theme_bg_color="Custom",
                      md_bg_color=(0.86, 0.26, 0.26, 1),
                                   size_hint_y=None, height=dp(48)))
        p.content.bind(on_release=lambda b: (db.delete_stock(sid),
                                             p.dismiss(), self.refresh()))
        p.open()

    def refresh_prices(self):
        def work():
            for r in db.get_stocks():
                price = pf.fetch_stock_price(r["market"], r["code"])
                if price:
                    db.update_stock_price(r["id"], price)
            Clock.schedule_once(lambda dt: self.refresh())
        threading.Thread(target=work, daemon=True).start()
        p = Popup(title="刷新中", content=MDLabel(text="正在拉取最新股价…", halign="center"),
                  size_hint=(0.7, 0.3), auto_dismiss=False)
        p.open()
        Clock.schedule_once(lambda dt: p.dismiss(), 1.5)


# ============================================================
# CS2 饰品页
# ============================================================
class CS2Screen(MDScreen):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.name = "cs2"
        root = MDBoxLayout(orientation="vertical", spacing=0)
        bar = MDBoxLayout(orientation="horizontal", size_hint_y=None,
                          height=dp(56), padding=[dp(16), dp(8), dp(16), dp(8)],
                          spacing=dp(10))
        bar.add_widget(MDLabel(text="CS2 饰品", font_style="Title", role="large",
                               theme_text_color="Custom", text_color=DARK,
                               size_hint_x=1))
        add_btn = MDButton(MDButtonText(text="＋"), style="filled",
                           theme_bg_color="Primary")
        add_btn.bind(on_release=lambda *_: open_cs2_form(self))
        refresh_btn = MDButton(MDButtonText(text="刷新价"), style="tonal",
                               theme_bg_color="Primary")
        refresh_btn.bind(on_release=lambda *_: self.refresh_prices())
        bar.add_widget(add_btn)
        bar.add_widget(refresh_btn)
        root.add_widget(bar)
        root.add_widget(MDDivider())

        self.body = MDBoxLayout(orientation="vertical", size_hint_y=None,
                                spacing=dp(8), adaptive_height=True)
        root.add_widget(make_scroll(self.body))
        self.add_widget(root)
        Clock.schedule_once(lambda dt: self.refresh())

    def refresh(self, *args):
        self.body.clear_widgets()
        rows = db.get_cs2_items()
        if not rows:
            self.body.add_widget(MDLabel(text="暂无饰品，点＋录入",
                                         font_style="Body", theme_text_color="Custom",
                                         text_color=GRAY, size_hint_y=None,
                                         height=dp(60), halign="center"))
            return
        for r in rows:
            market_val = r["quantity"] * r["current_price"]
            cost_val = r["quantity"] * r["cost_price"]
            pnl = market_val - cost_val
            pnl_color = GREEN if pnl >= 0 else RED
            sk = "StatTrak " if r["stattrak"] else ""
            wear = r["wear"].upper() or "-"
            cur = f"{r['current_price']:.2f}" if r["current_price"] else "--"
            pnl_text = f"{pnl:+.0f}" if r["current_price"] else "--"

            card = MDCard(
                MDBoxLayout(
                    MDBoxLayout(
                        MDLabel(text=f"{sk}{r['name']}", font_style="Body",
                                role="medium", theme_text_color="Custom",
                                text_color=DARK, size_hint_y=None, height=dp(24),
                                halign="left"),
                        MDLabel(text=f"[{wear}] ×{r['quantity']}", font_style="Label",
                                role="small", theme_text_color="Custom",
                                text_color=GRAY, size_hint_y=None, height=dp(18),
                                halign="left"),
                        orientation="vertical", size_hint_x=1, spacing=dp(2),
                    ),
                    MDBoxLayout(
                        MDLabel(text=cur, font_style="Title", role="large",
                                theme_text_color="Custom", text_color=DARK,
                                size_hint_y=None, height=dp(26), halign="right"),
                        MDLabel(text=pnl_text, font_style="Label", role="medium",
                                theme_text_color="Custom", text_color=pnl_color,
                                size_hint_y=None, height=dp(20), halign="right"),
                        orientation="vertical", size_hint_x=None, width=dp(90), spacing=dp(0),
                    ),
                    MDIconButton(icon="delete", style="standard",
                                 theme_icon_color="Error", size_hint_x=None),
                    orientation="horizontal", padding=[dp(14), dp(10), dp(4), dp(10)],
                    spacing=dp(8), adaptive_height=True,
                ),
                style="elevated", size_hint_y=None, height=dp(76),
                radius=dp(16), md_bg_color=(1, 1, 1, 1),
            )
            del_btn = card.children[0].children[0]
            del_btn.bind(on_release=lambda b, iid=r["id"]: self.confirm_delete(iid))
            self.body.add_widget(card)

    def confirm_delete(self, iid):
        p = Popup(title="删除该饰品？", size_hint=(0.72, 0.3),
                  content=MDButton(MDButtonText(text="确认删除"),
                                   style="filled", theme_bg_color="Custom",
                      md_bg_color=(0.86, 0.26, 0.26, 1),
                                   size_hint_y=None, height=dp(48)))
        p.content.bind(on_release=lambda b: (db.delete_cs2_item(iid),
                                             p.dismiss(), self.refresh()))
        p.open()

    def refresh_prices(self):
        def work():
            items = [dict(r) for r in db.get_cs2_items()]
            results, _ = pf.refresh_cs2_prices(items)
            for res in results:
                if res["found"] and res["price_cny"]:
                    db.update_cs2_price(res["id"], res["price_cny"])
            Clock.schedule_once(lambda dt: self.refresh())
        threading.Thread(target=work, daemon=True).start()
        p = Popup(title="刷新中", content=MDLabel(text="正在下载饰品行情表并匹配…\n首次约需1-2分钟",
                                                  halign="center"),
                  size_hint=(0.8, 0.35), auto_dismiss=False)
        p.open()
        Clock.schedule_once(lambda dt: p.dismiss(), 1.5)


# ============================================================
# 表单弹窗（记一笔 / 预算 / 现金 / 股票 / 饰品 / 工资）
# ============================================================
def _dropdown(button, values, on_select):
    """简单下拉：点击按钮循环切换选项"""
    idx = [0]

    def cycle(*_):
        idx[0] = (idx[0] + 1) % len(values)
        on_select(values[idx[0]])
    button.bind(on_release=cycle)
    return button


def _make_selector(label_text, values):
    """一个循环切换的选择按钮（替代 Spinner）"""
    box = MDBoxLayout(orientation="vertical", size_hint_y=None,
                      height=dp(76), spacing=dp(4), adaptive_height=True)
    box.add_widget(MDLabel(text=label_text, font_style="Label", role="small",
                           theme_text_color="Custom", text_color=GRAY,
                           size_hint_y=None, height=dp(20)))
    btn = MDButton(
        MDButtonText(text=values[0]),
        style="outlined", theme_bg_color="Primary",
        size_hint_y=None, height=dp(50),
    )
    state = {"i": 0}
    btn.bind(on_release=lambda *_: _cycle_selector(btn, values, state))
    box.add_widget(btn)
    return box, btn


def _cycle_selector(btn, values, state):
    state["i"] = (state["i"] + 1) % len(values)
    btn.children[0].text = values[state["i"]]


def _selector_value(btn):
    return btn.children[0].text


def open_ledger_form(screen):
    box = MDBoxLayout(orientation="vertical", spacing=dp(8), padding=dp(6))
    type_box, type_btn = _make_selector("类型", ["支出", "收入"])
    cat_box, cat_btn = _make_selector("分类", EXPENSE_CATEGORIES)
    pay_box, pay_btn = _make_selector("支付方式", PAY_METHODS)
    amt_box, amt_tf = field("金额（元）", "如 35.5")
    note_box, note_tf = field("备注", "可选")
    for w in (type_box, cat_box, pay_box, amt_box, note_box):
        box.add_widget(w)

    # 类型切换联动分类
    def on_type(btn):
        cats = INCOME_CATEGORIES if _selector_value(type_btn) == "收入" else EXPENSE_CATEGORIES
        cat_btn.children[0].text = cats[0]
    type_btn.bind(on_release=on_type)

    popup = Popup(title="记一笔", content=box, size_hint=(0.88, 0.82))

    def submit(*_):
        try:
            amt = float(amt_tf.text)
        except ValueError:
            return
        ttype = "income" if _selector_value(type_btn) == "收入" else "expense"
        db.add_transaction(today().strftime("%Y-%m-%d"), ttype,
                           _selector_value(cat_btn), amt,
                           _selector_value(pay_btn), note_tf.text.strip())
        popup.dismiss()
        screen.refresh()

    save_btn = MDButton(MDButtonText(text="保存"), style="filled",
                        theme_bg_color="Primary", size_hint_y=None, height=dp(48))
    save_btn.bind(on_release=submit)
    box.add_widget(save_btn)
    popup.open()


def open_budget_form(screen):
    box = MDBoxLayout(orientation="vertical", spacing=dp(8), padding=dp(6))
    cat_box, cat_btn = _make_selector("类别", EXPENSE_CATEGORIES)
    amt_box, amt_tf = field("月预算（元）", "如 1500")
    box.add_widget(cat_box)
    box.add_widget(amt_box)
    popup = Popup(title="设置预算", content=box, size_hint=(0.85, 0.5))

    def submit(*_):
        try:
            amt = float(amt_tf.text)
        except ValueError:
            return
        db.set_budget(_selector_value(cat_btn), amt)
        popup.dismiss()
        screen.refresh()

    save_btn = MDButton(MDButtonText(text="保存"), style="filled",
                        theme_bg_color="Primary", size_hint_y=None, height=dp(48))
    save_btn.bind(on_release=submit)
    box.add_widget(save_btn)
    popup.open()


def open_cash_form(screen):
    box = MDBoxLayout(orientation="vertical", spacing=dp(8), padding=dp(6))
    name_box, name_tf = field("账户名", "如 招商银行卡 / 零钱")
    amt_box, amt_tf = field("余额（元）", "如 5000")
    box.add_widget(name_box)
    box.add_widget(amt_box)
    popup = Popup(title="添加账户", content=box, size_hint=(0.85, 0.5))

    def submit(*_):
        try:
            amt = float(amt_tf.text)
        except ValueError:
            return
        db.add_cash_asset(name_tf.text.strip(), amt)
        popup.dismiss()
        screen.refresh()

    save_btn = MDButton(MDButtonText(text="保存"), style="filled",
                        theme_bg_color="Primary", size_hint_y=None, height=dp(48))
    save_btn.bind(on_release=submit)
    box.add_widget(save_btn)
    popup.open()


def open_stock_form(screen):
    box = MDBoxLayout(orientation="vertical", spacing=dp(8), padding=dp(6))
    mk_box, mk_btn = _make_selector("市场", ["美股", "A股"])
    code_box, code_tf = field("代码", "美股 AAPL / A股 600519")
    name_box, name_tf = field("名称", "如 苹果")
    sh_box, sh_tf = field("持仓股数", "如 10")
    cost_box, cost_tf = field("成本单价（人民币）", "如 150")
    for w in (mk_box, code_box, name_box, sh_box, cost_box):
        box.add_widget(w)
    popup = Popup(title="加仓", content=box, size_hint=(0.88, 0.9))

    def submit(*_):
        try:
            shares = float(sh_tf.text)
            cost = float(cost_tf.text)
        except ValueError:
            return
        market = "us" if _selector_value(mk_btn) == "美股" else "cn"
        db.add_stock(code_tf.text.strip().upper(), market,
                     name_tf.text.strip(), shares, cost)
        popup.dismiss()
        screen.refresh()

    save_btn = MDButton(MDButtonText(text="保存"), style="filled",
                        theme_bg_color="Primary", size_hint_y=None, height=dp(48))
    save_btn.bind(on_release=submit)
    box.add_widget(save_btn)
    popup.open()


def open_cs2_form(screen):
    box = MDBoxLayout(orientation="vertical", spacing=dp(8), padding=dp(6))
    name_box, name_tf = field("饰品英文全名", "如 AK-47 | Redline")
    wear_box, wear_btn = _make_selector("磨损", ["FT", "FN", "MW", "WW", "BS", "无"])
    st_box, st_btn = _make_selector("是否暗金 StatTrak", ["否", "是"])
    qty_box, qty_tf = field("数量", "1")
    cost_box, cost_tf = field("购入单价（人民币）", "如 120")
    for w in (name_box, wear_box, st_box, qty_box, cost_box):
        box.add_widget(w)
    popup = Popup(title="录入饰品", content=box, size_hint=(0.88, 0.95))

    def submit(*_):
        try:
            qty = int(qty_tf.text)
            cost = float(cost_tf.text)
        except ValueError:
            return
        wear = "" if _selector_value(wear_btn) == "无" else _selector_value(wear_btn)
        st = 1 if _selector_value(st_btn) == "是" else 0
        db.add_cs2_item(name_tf.text.strip(), wear, st, qty, cost)
        popup.dismiss()
        screen.refresh()

    save_btn = MDButton(MDButtonText(text="保存"), style="filled",
                        theme_bg_color="Primary", size_hint_y=None, height=dp(48))
    save_btn.bind(on_release=submit)
    box.add_widget(save_btn)
    popup.open()


def open_salary_calculator():
    box = MDBoxLayout(orientation="vertical", spacing=dp(8), padding=dp(6))
    base_box, base_tf = field("月基本工资（元）", str(db.SALARY_DEFAULTS["base"]))
    edu_box, edu_tf = field("学历补贴（元/月）", str(db.SALARY_DEFAULTS["edu"]))
    teach_box, teach_tf = field("从教津贴（元/月）", str(db.SALARY_DEFAULTS["teach"]))
    result_label = MDLabel(text="", font_style="Body", role="medium",
                           theme_text_color="Custom", text_color=DARK,
                           size_hint_y=None, height=dp(160), adaptive_height=True,
                           halign="left")
    for w in (base_box, edu_box, teach_box):
        box.add_widget(w)
    box.add_widget(result_label)
    popup = Popup(title="工资计算", content=box, size_hint=(0.88, 0.92))

    def calc(*_):
        try:
            base = float(base_tf.text or 0)
            edu = float(edu_tf.text or 0)
            teach = float(teach_tf.text or 0)
        except ValueError:
            return
        s = db.calc_salary(base, edu, teach)
        result_label.text = (
            f"税前总收入：{money(s['gross'])}\n"
            f"养老 {money(s['pension'])}  医疗 {money(s['medical'])}  失业 {money(s['unemployment'])}\n"
            f"公积金个人 {money(s['fund_personal'])}  单位入账 {money(s['fund_company'])}\n"
            f"五险一金合计：{money(s['social_total'])}\n"
            f"个人所得税（3%简化）：{money(s['tax'])}\n"
            f"每月到手现金：{money(s['net'])}"
        )

    calc_btn = MDButton(MDButtonText(text="计算"), style="filled",
                        theme_bg_color="Primary", size_hint_y=None, height=dp(48))
    calc_btn.bind(on_release=calc)
    box.add_widget(calc_btn)
    popup.open()


# ============================================================
# 主程序：底部导航 + 页面切换
# ============================================================
NAV_ITEMS = [
    ("home", "仪表盘", "dashboard"),
    ("book", "记账", "ledger"),
    ("chart-pie", "预算", "budget"),
    ("wallet", "现金", "cash"),
    ("chart-line", "股票", "stocks"),
    ("gamepad-variant", "饰品", "cs2"),
]


class AssetApp(MDApp):
    title = "我的资产账本"

    def build(self):
        db.init_db()
        self.theme_cls.primary_palette = "Blue"
        self.theme_cls.theme_style = "Light"
        self.theme_cls.material_style = "M3"

        self.sm = ScreenManager()
        self.sm.add_widget(DashboardScreen())
        self.sm.add_widget(LedgerScreen())
        self.sm.add_widget(BudgetScreen())
        self.sm.add_widget(CashScreen())
        self.sm.add_widget(StocksScreen())
        self.sm.add_widget(CS2Screen())

        # 底部导航
        nav = MDBoxLayout(orientation="horizontal", size_hint_y=None,
                          height=dp(64), padding=[dp(4), dp(4), dp(4), dp(4)],
                          spacing=dp(2), md_bg_color=(1, 1, 1, 1))
        for icon, text, name in NAV_ITEMS:
            nav.add_widget(self._nav_item(icon, text, name))

        root = MDBoxLayout(orientation="vertical")
        root.add_widget(self.sm)
        root.add_widget(MDDivider())
        root.add_widget(nav)
        return root

    def _nav_item(self, icon, text, name):
        inner = MDBoxLayout(orientation="vertical", spacing=dp(0),
                            adaptive_height=True)
        inner.add_widget(MDIconButton(icon=icon, style="standard",
                                      theme_icon_color="Primary",
                                      size_hint_y=None, height=dp(30)))
        inner.add_widget(MDLabel(text=text, font_style="Label", role="small",
                                 theme_text_color="Custom", text_color=GRAY,
                                 size_hint_y=None, height=dp(18), halign="center"))
        btn = MDButton(inner, style="text", size_hint_x=1)
        btn.bind(on_release=lambda *_, s=name: setattr(self.sm, "current", s))
        return btn


if __name__ == "__main__":
    AssetApp().run()
