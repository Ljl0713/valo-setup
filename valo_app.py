# -*- coding: utf-8 -*-
"""
valo_app —— 界面层
所有业务逻辑在 valo_core / valo_game / valo_sys / valo_state，这里只负责呈现与调度。
"""
import ctypes
import os
import sys
import time
import traceback

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog

import valo_core as core
import valo_game as game
import valo_state as state
import valo_sys as sysx

APP_TITLE = "VALO SETUP  ·  无畏契约 4:3 拉伸 & 职业设置"

BG = "#0e1014"
CARD = "#171a21"
CARD2 = "#1f242e"
LINE = "#2b3140"
TXT = "#e9ecf1"
SUB = "#8b94a6"
DIM = "#5d6577"
ACC = "#ff4655"
ACC_DK = "#d33b48"
OKC = "#3ddc97"
WARN = "#ffb84d"

FF = "Microsoft YaHei UI"


class Card(tk.Frame):
    def __init__(self, master, title=None, **kw):
        super().__init__(master, bg=CARD, highlightbackground=LINE,
                         highlightthickness=1, **kw)
        self.head = None
        if title:
            bar = tk.Frame(self, bg=CARD)
            bar.pack(fill="x", padx=14, pady=(11, 5))
            tk.Label(bar, text=title, bg=CARD, fg=TXT, font=(FF, 11, "bold"),
                     anchor="w").pack(side="left")
            self.head = bar


class App:
    def __init__(self, root):
        self.root = root
        self.conf = state.load()
        self.all_mons = core.monitors()
        self.mon = core.pick(self.conf.get("monitor_id"), self.all_mons)
        self.game = game.discover()
        self.dpi = self._dpi()
        self.scale = max(1.0, min(2.5, self.dpi / 96.0))
        self._last_game = game.game_running()
        self._closing = False

        root.title(APP_TITLE)
        root.configure(bg=BG)
        root.protocol("WM_DELETE_WINDOW", self.on_close)
        root.report_callback_exception = self.on_tk_error
        self._geometry()
        self._style()
        self._build()
        self._icon()
        self.root.bind("<F1>", lambda e: self.show_diagnose())
        self.refresh_all()
        self.selfcheck()
        root.after(1200, self.tick)
        if not self.conf.get("guide_done"):
            root.after(500, self.show_guide)
        state.log("启动：显示器=%s 原生=%s 配置=%s" % (
            self.mon["monitor"] if self.mon else "-",
            core.native_of(self.mon) if self.mon else "-",
            self.game["game_ini"]))
        self.say("就绪 · 按 F1 看诊断信息 · 当前 %s" % (
            ("%d×%d" % (self.mon["current"]["w"], self.mon["current"]["h"]))
            if self.mon and self.mon["current"] else "未知"), "ok")

    # ------------------------------------------------------------ 基础

    def _dpi(self):
        try:
            return ctypes.WinDLL("user32").GetDpiForSystem()
        except Exception:
            return 96

    def _geometry(self):
        w, h = int(1060 * self.scale), int(940 * self.scale)
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        w = min(w, int(sw * 0.95))
        h = min(h, int(sh * 0.94))
        self.root.geometry("%dx%d+%d+%d" % (w, h, max(0, (sw - w) // 2),
                                            max(0, (sh - h) // 2 - int(20 * self.scale))))
        self.root.minsize(min(int(940 * self.scale), int(sw * 0.6)),
                          min(int(700 * self.scale), int(sh * 0.6)))

    def _style(self):
        st = ttk.Style()
        try:
            st.theme_use("clam")
        except tk.TclError:
            pass
        st.configure("TCombobox", fieldbackground=CARD2, background=CARD2,
                     foreground=TXT, arrowcolor=TXT, bordercolor=LINE,
                     lightcolor=CARD2, darkcolor=CARD2, selectbackground=CARD2,
                     selectforeground=TXT, padding=3)
        st.map("TCombobox", fieldbackground=[("readonly", CARD2)],
               foreground=[("readonly", TXT)], bordercolor=[("focus", ACC)])
        for opt in ("background", "foreground", "selectBackground", "selectForeground"):
            self.root.option_add("*TCombobox*Listbox." + opt,
                                 {"background": CARD2, "foreground": TXT,
                                  "selectBackground": ACC,
                                  "selectForeground": "#ffffff"}[opt])
        st.configure("Vertical.TScrollbar", background=CARD2, troughcolor=CARD,
                     bordercolor=LINE, arrowcolor=SUB)

    def _icon(self):
        try:
            base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
            p = os.path.join(base, "valo.ico")
            if os.path.isfile(p):
                self.root.iconbitmap(default=p)
        except Exception:
            pass

    def px(self, v):
        return max(1, int(round(v * self.scale)))

    def center_on_parent(self, top, w=None, h=None):
        """把子窗口摆到主窗口正中间（并夹在屏幕内），避免默认飘到左上角。"""
        top.update_idletasks()
        w = w or top.winfo_reqwidth()
        h = h or top.winfo_reqheight()
        px, py = self.root.winfo_rootx(), self.root.winfo_rooty()
        pw, ph = self.root.winfo_width(), self.root.winfo_height()
        sw, sh = top.winfo_screenwidth(), top.winfo_screenheight()
        x = px + max(0, (pw - w) // 2)
        y = py + max(0, (ph - h) // 2)
        x = max(0, min(x, sw - w - 10))
        y = max(0, min(y, sh - h - 50))
        top.geometry("%dx%d+%d+%d" % (w, h, x, y))
        top.update_idletasks()
        state.log("center: parent=(%d,%d) size=(%dx%d) child=(%dx%d) -> +%d+%d, got %s"
                  % (px, py, pw, ph, w, h, x, y, top.geometry()))

    # ------------------------------------------------------------ 构建

    def _build(self):
        s = self.scale

        wrap = tk.Frame(self.root, bg=BG)
        wrap.pack(side="bottom", fill="x", padx=self.px(18), pady=(self.px(6), self.px(12)))
        self.logbox = tk.Text(wrap, height=4, bg="#0a0c10", fg=SUB,
                              font=("Consolas", max(8, int(9 * s))),
                              relief="flat", bd=0, padx=self.px(10), pady=self.px(6),
                              wrap="word", highlightthickness=1,
                              highlightbackground=LINE)
        self.logbox.pack(fill="x")
        self.logbox.configure(state="disabled")
        for tag, col in (("ok", OKC), ("err", ACC), ("warn", WARN), ("info", SUB)):
            self.logbox.tag_config(tag, foreground=col)

        head = tk.Frame(self.root, bg=BG)
        head.pack(side="top", fill="x", padx=self.px(18), pady=(self.px(12), self.px(2)))
        tk.Label(head, text="VALO SETUP", bg=BG, fg=ACC,
                 font=(FF, max(12, int(18 * s)), "bold")).pack(side="left")
        tk.Label(head, text="4:3 拉伸 · 职业选手一键设置", bg=BG, fg=SUB,
                 font=(FF, max(8, int(10 * s)))).pack(side="left", padx=(self.px(10), 0),
                                                      pady=(self.px(6), 0))
        tk.Button(head, text="诊断", font=(FF, max(8, int(9 * s))), bg=CARD2, fg=SUB,
                  activebackground=LINE, activeforeground=TXT, relief="flat", bd=0,
                  cursor="hand2", padx=self.px(10), pady=self.px(2),
                  command=self.show_diagnose).pack(side="right")
        tk.Button(head, text="帮助", font=(FF, max(8, int(9 * s))), bg=CARD2, fg=SUB,
                  activebackground=LINE, activeforeground=TXT, relief="flat", bd=0,
                  cursor="hand2", padx=self.px(10), pady=self.px(2),
                  command=self.show_guide).pack(side="right", padx=(0, self.px(6)))
        tk.Button(head, text="重置", font=(FF, max(8, int(9 * s))), bg=CARD2, fg=ACC,
                  activebackground=LINE, activeforeground=ACC, relief="flat", bd=0,
                  cursor="hand2", padx=self.px(10), pady=self.px(2),
                  command=self.reset_all).pack(side="right", padx=(0, self.px(6)))
        self.mon_box = ttk.Combobox(head, state="readonly", width=35,
                                    font=(FF, max(8, int(9 * s))))
        self.mon_box.pack(side="right", padx=(0, self.px(8)))
        self.mon_box.bind("<<ComboboxSelected>>", self.on_pick_monitor)

        self.banner = tk.Frame(self.root, bg="#3a2a12", highlightbackground=WARN,
                               highlightthickness=1)
        self.banner_lbl = tk.Label(self.banner, bg="#3a2a12", fg=WARN,
                                   font=(FF, max(8, int(9 * s))), anchor="w",
                                   justify="left", wraplength=self.px(950))
        self.banner_lbl.pack(fill="x", padx=self.px(12), pady=self.px(6))

        body = tk.Frame(self.root, bg=BG)
        self.body = body
        body.pack(side="top", fill="both", expand=True, padx=self.px(18), pady=self.px(4))
        body.columnconfigure(0, weight=1, uniform="c")
        body.columnconfigure(1, weight=1, uniform="c")
        body.rowconfigure(0, weight=1)
        left = tk.Frame(body, bg=BG)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, self.px(8)))
        right = tk.Frame(body, bg=BG)
        right.grid(row=0, column=1, sticky="nsew", padx=(self.px(8), 0))

        # ---------------- 左：状态 + 一键
        c1 = Card(left, "当前状态")
        c1.pack(fill="x")
        self.stat_lbl = tk.Label(c1, text="", bg=CARD, fg=SUB,
                                 font=(FF, max(8, int(9 * s))), anchor="w", justify="left")
        self.stat_lbl.pack(fill="x", padx=self.px(14), pady=(0, self.px(8)))

        self.big = tk.Button(c1, text="", font=(FF, max(10, int(14 * s)), "bold"),
                             bg=ACC, fg="#ffffff", activebackground=ACC_DK,
                             activeforeground="#ffffff", relief="flat", bd=0,
                             cursor="hand2", command=self.toggle, height=2)
        self.big.pack(fill="x", padx=self.px(14), pady=(0, self.px(8)))

        row0 = tk.Frame(c1, bg=CARD)
        row0.pack(fill="x", padx=self.px(14), pady=(0, self.px(8)))
        tk.Button(row0, text="一键全套", font=(FF, max(8, int(10 * s)), "bold"),
                  bg=CARD2, fg=TXT, activebackground=LINE, activeforeground=TXT,
                  relief="flat", bd=0, cursor="hand2", height=2,
                  command=self.one_click).pack(side="left", fill="x", expand=True,
                                               padx=(0, self.px(5)))
        tk.Button(row0, text="去黑边", font=(FF, max(8, int(10 * s)), "bold"),
                  bg=CARD2, fg=WARN, activebackground=LINE, activeforeground=WARN,
                  relief="flat", bd=0, cursor="hand2", height=2,
                  command=self.one_tap_letterbox).pack(side="left", fill="x",
                                                       expand=True)
        self.auto_var = tk.BooleanVar(value=bool(self.conf.get("auto")))
        tk.Checkbutton(c1, text="自动切换：进游戏切 4:3，退游戏切回日常",
                       variable=self.auto_var, bg=CARD, fg=SUB, selectcolor=CARD2,
                       activebackground=CARD, activeforeground=TXT,
                       font=(FF, max(8, int(9 * s))), bd=0, highlightthickness=0,
                       command=self.on_auto, anchor="w").pack(fill="x", padx=self.px(14))
        tk.Label(c1, text="窗口最小化后依然生效，别关掉", bg=CARD, fg=DIM,
                 font=(FF, max(7, int(8 * s))), anchor="w").pack(
            fill="x", padx=self.px(32), pady=(0, self.px(8)))

        # ---------------- 左：分辨率
        c2 = Card(left, "游戏分辨率")
        c2.pack(fill="both", expand=True, pady=(self.px(10), 0))
        self.res_grid = tk.Frame(c2, bg=CARD)
        self.res_grid.pack(fill="x", padx=self.px(10), pady=(0, self.px(4)))
        self.res_btns = {}

        row = tk.Frame(c2, bg=CARD)
        row.pack(fill="x", padx=self.px(14), pady=(self.px(2), self.px(4)))
        tk.Label(row, text="刷新率", bg=CARD, fg=SUB,
                 font=(FF, max(8, int(9 * s)))).pack(side="left")
        self.hz_box = ttk.Combobox(row, width=6, state="readonly",
                                   font=(FF, max(8, int(9 * s))))
        self.hz_box.pack(side="left", padx=(self.px(6), self.px(12)))
        self.hz_box.bind("<<ComboboxSelected>>", lambda e: self.on_hz())
        tk.Button(row, text="当前 → 记为日常", font=(FF, max(8, int(9 * s))),
                  bg=CARD2, fg=TXT, activebackground=LINE, relief="flat", bd=0,
                  cursor="hand2", padx=self.px(8),
                  command=self.save_native).pack(side="right")

        crow = tk.Frame(c2, bg=CARD)
        crow.pack(fill="x", padx=self.px(14), pady=(0, self.px(10)))
        tk.Label(crow, text="自定义", bg=CARD, fg=SUB,
                 font=(FF, max(8, int(9 * s)))).pack(side="left")
        self.cw = tk.Entry(crow, width=6, bg=CARD2, fg=TXT, insertbackground=TXT,
                           relief="flat", bd=0, font=(FF, max(8, int(9 * s))),
                           highlightthickness=1, highlightbackground=LINE,
                           highlightcolor=ACC, justify="center")
        self.cw.pack(side="left", padx=(self.px(6), self.px(2)), ipady=self.px(2))
        tk.Label(crow, text="×", bg=CARD, fg=SUB).pack(side="left")
        self.ch = tk.Entry(crow, width=6, bg=CARD2, fg=TXT, insertbackground=TXT,
                           relief="flat", bd=0, font=(FF, max(8, int(9 * s))),
                           highlightthickness=1, highlightbackground=LINE,
                           highlightcolor=ACC, justify="center")
        self.ch.pack(side="left", padx=(self.px(2), self.px(8)), ipady=self.px(2))
        tk.Button(crow, text="应用", font=(FF, max(8, int(9 * s))), bg=CARD2, fg=TXT,
                  activebackground=LINE, relief="flat", bd=0, cursor="hand2",
                  padx=self.px(10), command=self.apply_custom).pack(side="left")
        self.custom_hint = tk.Label(crow, text="", bg=CARD, fg=DIM,
                                    font=(FF, max(7, int(8 * s))))
        self.custom_hint.pack(side="left", padx=(self.px(8), 0))

        tip = ("1280×960 在 2K 屏上是横向拉伸 1.33 倍，等同 1080p 屏上的 1440×1080。\n"
               "想更宽用 1024×768，想更清晰用 1440×1080。\n"
               "切完如果左右有黑边，点上面的「去黑边」，不是分辨率的问题。")
        tk.Label(c2, text=tip, bg=CARD, fg=DIM, font=(FF, max(7, int(8 * s))),
                 justify="left", anchor="w", wraplength=self.px(460)).pack(
            side="bottom", fill="x", padx=self.px(14), pady=(0, self.px(10)))

        # ---------------- 右：游戏内设置
        c3 = Card(right, "游戏内设置 · 直接写配置")
        c3.pack(fill="x")
        self.ini_lbl = tk.Label(c3, text="", bg=CARD, fg=DIM,
                                font=(FF, max(7, int(8 * s))), anchor="w",
                                justify="left", wraplength=self.px(440))
        self.ini_lbl.pack(fill="x", padx=self.px(14), pady=(0, self.px(4)))

        self.opt = {}
        for key, label, default in (
            ("fullscreen", "全屏模式 + 关闭垂直同步", True),
            ("stretch", "真·拉伸（关闭 letterbox 黑边）", True),
            ("fps", "解除帧率上限", True),
            ("reflex", "NVIDIA Reflex 开 + 加速", True),
            ("lowq", "职业低画质（材质/细节低、阴影关、抗锯齿关）", True),
        ):
            self.opt[key] = tk.BooleanVar(value=default)
            tk.Checkbutton(c3, text=label, variable=self.opt[key], bg=CARD, fg=TXT,
                           selectcolor=CARD2, activebackground=CARD, activeforeground=TXT,
                           font=(FF, max(8, int(9 * s))), anchor="w", bd=0,
                           highlightthickness=0, cursor="hand2").pack(
                fill="x", padx=self.px(12))

        btns = tk.Frame(c3, bg=CARD)
        btns.pack(fill="x", padx=self.px(12), pady=(self.px(8), self.px(10)))
        self.btn_write = tk.Button(btns, text="写入游戏设置", font=(FF, max(9, int(10 * s)), "bold"),
                                   bg=ACC, fg="#fff", activebackground=ACC_DK,
                                   relief="flat", bd=0, cursor="hand2",
                                   command=self.write_game)
        self.btn_write.pack(side="left", fill="x", expand=True, padx=(0, self.px(6)),
                            ipady=self.px(3))
        tk.Button(btns, text="备份", font=(FF, max(8, int(9 * s))), bg=CARD2, fg=TXT,
                  activebackground=LINE, relief="flat", bd=0, cursor="hand2",
                  padx=self.px(8), command=self.do_backup).pack(side="left",
                                                                padx=(0, self.px(6)))
        tk.Button(btns, text="恢复", font=(FF, max(8, int(9 * s))), bg=CARD2, fg=TXT,
                  activebackground=LINE, relief="flat", bd=0, cursor="hand2",
                  padx=self.px(8), command=self.do_restore).pack(side="left",
                                                                 padx=(0, self.px(6)))
        tk.Button(btns, text="选路径", font=(FF, max(8, int(9 * s))), bg=CARD2, fg=SUB,
                  activebackground=LINE, relief="flat", bd=0, cursor="hand2",
                  padx=self.px(8), command=self.pick_folder).pack(side="left")

        # ---------------- 右：系统优化
        c4 = Card(right, "系统优化 · 职业选手基线")
        c4.pack(fill="x", pady=(self.px(10), 0))
        self.sys_rows = {}
        for it in sysx.items():
            f = tk.Frame(c4, bg=CARD)
            f.pack(fill="x", padx=self.px(14), pady=self.px(2))
            tk.Label(f, text=it["label"], bg=CARD, fg=TXT,
                     font=(FF, max(8, int(9 * s))), anchor="w").pack(side="left")
            b = tk.Button(f, text="", font=(FF, max(7, int(8 * s))), bg=CARD2, fg=SUB,
                          relief="flat", bd=0, cursor="hand2", width=7,
                          command=lambda k=it["key"]: self.flip(k))
            b.pack(side="right")
            self.sys_rows[it["key"]] = b
            tk.Label(f, text=it["hint"], bg=CARD, fg=DIM,
                     font=(FF, max(7, int(8 * s))), anchor="w").pack(
                side="left", padx=(self.px(8), 0))

        prow = tk.Frame(c4, bg=CARD)
        prow.pack(fill="x", padx=self.px(14), pady=(self.px(6), self.px(4)))
        self.power_lbl = tk.Label(prow, text="", bg=CARD, fg=SUB,
                                  font=(FF, max(8, int(9 * s))), anchor="w")
        self.power_lbl.pack(side="left")
        tk.Button(prow, text="切最高性能", font=(FF, max(7, int(8 * s))), bg=CARD2,
                  fg=SUB, activebackground=LINE, relief="flat", bd=0, cursor="hand2",
                  padx=self.px(6), command=self.set_power).pack(side="right")

        nrow = tk.Frame(c4, bg=CARD)
        nrow.pack(fill="x", padx=self.px(14), pady=(0, self.px(10)))
        tk.Button(nrow, text="打开显卡缩放设置（去黑边没用时再用）",
                  font=(FF, max(8, int(9 * s))),
                  bg=CARD2, fg=TXT, activebackground=LINE, relief="flat", bd=0,
                  cursor="hand2", pady=self.px(3),
                  command=self.open_nvidia).pack(fill="x")

        # ---------------- 右：提示
        c5 = Card(right, "还有黑边？")
        c5.pack(fill="both", expand=True, pady=(self.px(10), 0))
        txt = ("先点左边的「去黑边」。\n"
               "它会自动做完三件事：切 4:3、把显卡缩放设成拉伸、\n"
               "关掉游戏配置里的黑边开关。\n"
               "大多数机器到这一步就铺满了。\n\n"
               "还是没铺满，再点下面这个按钮，\n"
               "按里面的顺序一条条查。")
        tk.Label(c5, text=txt, bg=CARD, fg=SUB, font=(FF, max(8, int(9 * s))),
                 justify="left", anchor="w",
                 wraplength=self.px(430)).pack(fill="x", padx=self.px(14),
                                               pady=(0, self.px(4)))
        tk.Button(c5, text="点过去黑边还是没铺满？点这里",
                  font=(FF, max(7, int(8 * s))), bg=CARD2, fg=WARN,
                  activebackground=LINE, activeforeground=WARN, relief="flat",
                  bd=0, cursor="hand2", anchor="w",
                  command=self.show_letterbox_help).pack(fill="x",
                                                         padx=self.px(14),
                                                         pady=(0, self.px(6)))
        self.top_var = tk.BooleanVar(value=bool(self.conf.get("topmost")))
        tk.Checkbutton(c5, text="窗口置顶（方便边玩边点）", variable=self.top_var,
                       bg=CARD, fg=SUB, selectcolor=CARD2, activebackground=CARD,
                       activeforeground=TXT, font=(FF, max(8, int(9 * s))), bd=0,
                       highlightthickness=0, command=self.on_top).pack(
            anchor="w", padx=self.px(12))

    # ------------------------------------------------------------ 日志

    def say(self, msg, kind="info"):
        self.logbox.configure(state="normal")
        self.logbox.insert("end", "%s  %s\n" % (time.strftime("%H:%M:%S"), msg), kind)
        self.logbox.see("end")
        self.logbox.configure(state="disabled")
        state.log(msg)

    # ------------------------------------------------------------ 刷新

    def selfcheck(self):
        """兜底：上次异常退出（强杀 / 关机 / 断电）可能把 4:3 留在系统里"""
        if not self.mon:
            return
        c = self.mon["current"] or {}
        g = self.conf["game"]
        if (c.get("w"), c.get("h")) != (g["w"], g["h"]):
            return
        if game.game_running():
            return
        n = self.conf.get("native") or {}
        nw = n.get("w") or core.native_of(self.mon)[0]
        nh = n.get("h") or core.native_of(self.mon)[1]
        ok, msg = core.set_mode(self.mon, nw, nh, n.get("hz"), persist=True)
        try:
            core.set_scaling(False, device=self.mon.get("device"))
        except Exception:
            pass
        self.say("检测到上次退出时残留 4:3，已自动切回 %d×%d" % (nw, nh),
                 "warn" if ok else "err")
        self.refresh_all()

    def refresh_all(self):
        self.refresh_monitors_box()
        self.refresh_stat()
        self.refresh_res()
        self.refresh_sys()
        self.refresh_ini_label()
        self.refresh_banner()

    def refresh_monitors_box(self):
        vals = [core.label(m) for m in self.all_mons] or ["未检测到显示器"]
        self.mon_box.configure(values=vals)
        if self.mon:
            idx = self.all_mons.index(self.mon)
            self.mon_box.current(idx)
        self.conf["monitor_id"] = self.mon["monitor_id"] if self.mon else None

    def refresh_stat(self):
        if not self.mon:
            self.stat_lbl.configure(text="未检测到可用显示器")
            return
        core.refresh(self.mon)
        c = self.mon["current"] or {}
        nw, nh = core.native_of(self.mon)
        g = self.conf["game"]
        in_game_mode = (c.get("w"), c.get("h")) == (g["w"], g["h"])
        self.stat_lbl.configure(
            text="面板原生  %d×%d  (%s)\n当前分辨率  %d×%d @ %dHz  %s\n游戏设置  %d×%d (%s)" % (
                nw, nh, core.describe_ratio(nw, nh),
                c.get("w", 0), c.get("h", 0), c.get("hz", 0), "● 已切 4:3" if in_game_mode else "",
                g["w"], g["h"], core.describe_ratio(g["w"], g["h"])))
        if in_game_mode:
            n = self.conf.get("native") or {"w": nw, "h": nh}
            self.big.configure(text="切回日常  %d × %d" % (n["w"], n["h"]))
        else:
            self.big.configure(text="切到 4:3  %d × %d" % (g["w"], g["h"]))

    def refresh_res(self):
        if not self.mon:
            return
        modes = self.mon["modes"]
        four = [(w, h) for (w, h) in modes if core.is_43(w, h) and w >= 1024]
        four.sort(key=lambda t: (t != (1280, 960), -(t[0] * t[1])))
        four = four[:6]

        for wdg in self.res_grid.winfo_children():
            wdg.destroy()
        self.res_btns = {}
        if not four:
            tk.Label(self.res_grid, text="这台显示器的驱动没有提供任何 4:3 模式",
                     bg=CARD, fg=WARN, font=(FF, max(8, int(9 * self.scale)))).grid(
                row=0, column=0, sticky="w", padx=4, pady=6)
        g = self.conf["game"]
        area = sorted(four, key=lambda t: t[0] * t[1])
        for i, (w, h) in enumerate(four):
            if (w, h) == (1280, 960):
                tag = "职业主流"
            elif (w, h) == area[-1]:
                tag = "最高"
            elif (w, h) == area[0]:
                tag = "最宽拉伸"
            else:
                tag = core.describe_ratio(w, h)
            active = (g["w"], g["h"]) == (w, h)
            b = tk.Button(self.res_grid, text="%d × %d\n%s" % (w, h, tag),
                          font=(FF, max(7, int(9 * self.scale))),
                          bg=ACC if active else CARD2,
                          fg="#ffffff" if active else TXT,
                          activebackground=ACC_DK if active else LINE,
                          activeforeground=TXT, relief="flat", bd=0, cursor="hand2",
                          height=2, command=lambda w=w, h=h: self.pick_res(w, h))
            b.grid(row=i // 3, column=i % 3, sticky="nsew",
                   padx=self.px(4), pady=self.px(4))
            self.res_btns[(w, h)] = b
        for c in range(3):
            self.res_grid.columnconfigure(c, weight=1)

        hs = [str(x) for x in modes.get((g["w"], g["h"]), [])]
        self.hz_box.configure(values=hs)
        want = g.get("hz")
        if hs:
            if want and str(want) in hs:
                self.hz_box.set(str(want))
            else:
                self.hz_box.set(hs[-1])
        self.cw.delete(0, "end")
        self.ch.delete(0, "end")
        self.cw.insert(0, str(g["w"]))
        self.ch.insert(0, str(g["h"]))
        ok = (g["w"], g["h"]) in modes
        self.custom_hint.configure(
            text="" if ok else "驱动无此模式，需先在显卡面板添加",
            fg=DIM if ok else WARN)

    def refresh_sys(self):
        st = sysx.state()
        for k, b in self.sys_rows.items():
            on = st.get(k)
            b.configure(text="✓ 已优化" if on else "未优化",
                        bg="#16302a" if on else CARD2,
                        fg=OKC if on else SUB)
        self.power_lbl.configure(text="电源计划  " + st.get("_power", "未知"))

    def refresh_ini_label(self):
        if game.game_running():
            self.btn_write.configure(state="disabled", bg=LINE)
        else:
            self.btn_write.configure(state="normal", bg=ACC)
        if self.game["game_ini"]:
            n = len(self.game["user_inis"])
            where = os.path.basename(os.path.dirname(self.game["game_ini"]))
            self.ini_lbl.configure(
                text="已定位配置目录 %s · 画质文件 %d 个 · %s" % (
                    where or "WindowsClient", n,
                    "游戏运行中，暂不可写" if game.game_running() else "可写入"),
                fg=DIM)
        else:
            self.ini_lbl.configure(text="未找到游戏配置：" + (self.game["error"] or ""),
                                   fg=WARN)

    def refresh_banner(self):
        msgs = []
        if self.mon and (1280, 960) not in self.mon["modes"]:
            msgs.append("你的显卡驱动没有 1280×960，需要用显卡面板添加自定义分辨率，或用下面其他 4:3 档位。")
        if not self.game["game_ini"]:
            msgs.append("没找到无畏契约配置文件，游戏设置相关功能不可用。")
        else:
            data, _ = game.read_ini(self.game["game_ini"])
            if str(data.get("bShouldLetterbox", "")).strip().lower() == "true":
                msgs.append("配置文件里 letterbox 还是开着的（切 4:3 会出黑边），点「写入游戏设置」可直接关闭。")
        if msgs:
            self.banner_lbl.configure(text="   ".join(msgs))
            self.banner.pack(side="top", fill="x", padx=self.px(18),
                             pady=(self.px(4), 0), before=self.body)
        else:
            self.banner.pack_forget()

    # ------------------------------------------------------------ 动作：分辨率

    def toggle(self):
        if not self.mon:
            return
        c = self.mon["current"] or {}
        g = self.conf["game"]
        n = self.conf.get("native") or {}
        if (c.get("w"), c.get("h")) == (g["w"], g["h"]):
            tw, th, thz = n.get("w"), n.get("h"), n.get("hz")
        else:
            tw, th, thz = g["w"], g["h"], g.get("hz")
        self.apply_mode(tw, th, thz, "4:3" if (tw, th) == (g["w"], g["h"]) else "日常")

    def apply_mode(self, w, h, hz, name):
        if not w or not h:
            self.say("没有可用的目标分辨率", "err")
            return False
        before = dict(self.mon["current"] or {})
        ok, msg = core.set_mode(self.mon, w, h, hz)
        self.say("%s → %s" % (name, msg), "ok" if ok else "err")
        if not ok:
            self.refresh_stat()
            return False
        self.refresh_all()
        return True

    def pick_res(self, w, h):
        modes = self.mon["modes"].get((w, h)) or []
        self.conf["game"] = {"w": w, "h": h, "hz": max(modes) if modes else None}
        state.save(self.conf)
        self.refresh_res()
        self.say("游戏分辨率设为 %d×%d" % (w, h), "ok")
        self.apply_mode(w, h, self.conf["game"]["hz"], "游戏 4:3")

    def on_hz(self):
        try:
            self.conf["game"]["hz"] = int(self.hz_box.get())
            state.save(self.conf)
            self.say("刷新率锁定 %s Hz" % self.hz_box.get(), "ok")
        except (ValueError, TypeError):
            pass

    def apply_custom(self):
        try:
            w = int(self.cw.get().strip())
            h = int(self.ch.get().strip())
        except ValueError:
            self.say("自定义分辨率要填两个数字", "err")
            return
        if not (320 <= w <= 7680 and 200 <= h <= 4320):
            self.say("分辨率超出合理范围", "err")
            return
        if (w, h) not in self.mon["modes"]:
            self.say("驱动不提供 %d×%d：请先在显卡控制面板里添加这个分辨率，再回来点应用" % (w, h), "err")
            self.custom_hint.configure(text="驱动无此模式，需先在显卡面板添加", fg=WARN)
            return
        self.pick_res(w, h)

    def save_native(self):
        c = self.mon["current"] or {}
        g = self.conf["game"]
        if (c.get("w"), c.get("h")) == (g["w"], g["h"]):
            if not messagebox.askyesno("确认", "你现在正处于 4:3 游戏模式。\n"
                                               "把它记成「日常」会导致回来后还是 4:3。\n\n"
                                               "确定要这样记吗？"):
                return
        self.conf["native"] = {"w": c.get("w"), "h": c.get("h"), "hz": c.get("hz")}
        state.save(self.conf)
        self.say("日常分辨率记为 %d×%d @ %dHz" % (c["w"], c["h"], c["hz"]), "ok")
        self.refresh_stat()

    def on_pick_monitor(self, _evt=None):
        idx = self.mon_box.current()
        if 0 <= idx < len(self.all_mons):
            self.mon = self.all_mons[idx]
            self.conf["monitor_id"] = self.mon["monitor_id"]
            state.save(self.conf)
            self.refresh_all()
            self.say("切换到显示器 %s" % self.mon["monitor"], "ok")

    # ------------------------------------------------------------ 动作：游戏配置

    def write_game(self):
        if game.game_running():
            self.say("游戏正在运行，先完全退出再写入（否则退出时会被覆盖）", "err")
            return
        gi = self.game["game_ini"]
        if not gi:
            self.say("没有找到 GameUserSettings.ini，无法写入", "err")
            return
        ui = game.pick_user_ini(self.game["user_inis"], self.conf.get("user_ini"))
        paths = [gi] + ([ui] if ui else [])
        bk = game.backup(paths, state.BACKUP_DIR, int(self.conf.get("backup_keep", 10)))
        if bk:
            self.say("已备份 → %s" % os.path.basename(bk), "ok")
        g = self.conf["game"]
        expect = game.apply_display(
            gi, g["w"], g["h"],
            fullscreen=self.opt["fullscreen"].get(),
            no_vsync=self.opt["fullscreen"].get(),
            stretch=self.opt["stretch"].get(),
            unlock_fps=self.opt["fps"].get())
        good, bad = game.verify(gi, expect)
        self.say("显示设置 %d 项写入%s" % (len(expect), "，回读一致" if good else
                                       "，回读不一致：" + ",".join(bad)),
                 "ok" if good else "err")
        if ui:
            kv = game.apply_quality(ui, quality_pro=self.opt["lowq"].get(),
                                    reflex=self.opt["reflex"].get())
            g2, bad2 = game.verify(ui, kv)
            self.say("画质设置 %d 项写入%s" % (len(kv), "，回读一致" if g2 else
                                           "，回读不一致：" + ",".join(bad2)),
                     "ok" if g2 else "err")
        else:
            self.say("没找到画质配置文件（RiotUserSettings.ini），只写了显示部分", "warn")
        self.refresh_ini_label()
        self.refresh_banner()

    def do_backup(self):
        ui = game.pick_user_ini(self.game["user_inis"], self.conf.get("user_ini"))
        paths = [x for x in (self.game["game_ini"], ui) if x]
        d = game.backup(paths, state.BACKUP_DIR, int(self.conf.get("backup_keep", 10)))
        self.say(("已备份 → %s" % os.path.basename(d)) if d else "没有可备份的配置文件",
                 "ok" if d else "warn")

    def do_restore(self):
        bs = game.list_backups(state.BACKUP_DIR)
        if not bs:
            self.say("还没有备份", "warn")
            return
        if not messagebox.askyesno("恢复备份", "用最近一次备份（%s）覆盖当前配置？"
                                             % os.path.basename(bs[0])):
            return
        ui = game.pick_user_ini(self.game["user_inis"], self.conf.get("user_ini"))
        n = game.restore(bs[0], self.game["game_ini"], ui)
        self.say("已恢复 %d 个文件" % n, "ok" if n else "warn")
        self.refresh_banner()

    def pick_folder(self):
        d = filedialog.askdirectory(title="选择无畏契约的 Saved\\Config 上级目录（含 WindowsClient）")
        if not d:
            return
        gi = os.path.join(d, "WindowsClient", "GameUserSettings.ini")
        if not os.path.isfile(gi):
            gi2 = os.path.join(d, "GameUserSettings.ini")
            if os.path.isfile(gi2):
                gi = gi2
            else:
                self.say("这个目录里没找到 GameUserSettings.ini", "err")
                return
        self.game["game_ini"] = gi
        self.game["base"] = os.path.dirname(os.path.dirname(gi))
        self.game["error"] = None
        ui = game.discover()
        self.game["user_inis"] = ui["user_inis"]
        self.say("已指定配置目录：%s" % os.path.dirname(gi), "ok")
        self.refresh_ini_label()
        self.refresh_banner()

    # ------------------------------------------------------------ 动作：系统

    def flip(self, key):
        for it in sysx.items():
            if it["key"] == key:
                try:
                    it["set"]()
                    self.say("已应用：%s%s" % (it["label"],
                                              ("（%s）" % it["note"]) if it.get("note") else ""),
                             "ok")
                except Exception as e:
                    self.say("设置失败 %s：%r" % (it["label"], e), "err")
                break
        self.refresh_sys()

    def set_power(self):
        plan = sysx.best_power_plan()
        if not plan:
            self.say("没找到高性能电源计划", "err")
            return
        ok, msg = sysx.set_power_plan(plan)
        self.say(("电源计划 → %s" % msg) if ok else ("切换失败：%s" % msg),
                 "ok" if ok else "err")
        self.refresh_sys()

    def open_nvidia(self):
        ok = sysx.open_nvidia_panel()
        self.say("已尝试打开显卡设置面板" if ok else "没能自动打开，请手动打开 NVIDIA 控制面板",
                 "ok" if ok else "warn")

    def on_top(self):
        on = bool(self.top_var.get())
        try:
            self.root.attributes("-topmost", on)
        except tk.TclError:
            pass
        self.conf["topmost"] = on
        state.save(self.conf)

    # ------------------------------------------------------------ 一键全套

    def one_click(self):
        g = self.conf["game"]
        # 第一次优化前先记下用户原来的样子，恢复默认时才能回到"他自己的原值"
        if not self.conf.get("sys_snapshot"):
            self.conf["sys_snapshot"] = sysx.snapshot()
            state.save(self.conf)
        self.apply_mode(g["w"], g["h"], g.get("hz"), "① 4:3")
        okn, detail = sysx.optimize_all()
        self.say("② 系统优化 %d/%d 项" % (okn, len(sysx.items())), "ok")
        for d in detail:
            self.say("   " + d, "warn")
        self.refresh_sys()
        if game.game_running():
            self.say("③ 游戏正在运行，跳过写配置（退出后点「写入游戏设置」）", "warn")
        else:
            self.write_game()

    def reset_all(self):
        """恢复全部默认：分辨率、缩放、系统优化项、游戏配置、软件设置"""
        if not messagebox.askyesno(
                "恢复全部默认",
                "会把这台机器还原成你没用过这个软件之前的样子：\n\n"
                "① 分辨率切回显示器原生\n"
                "② 显卡缩放恢复「不缩放」\n"
                "③ 鼠标加速、粘滞键、GameDVR、游戏模式、电源计划全部还原\n"
                "④ 无畏契约配置从最近一次备份恢复\n"
                "⑤ 软件自己的设置清空（记住的分辨率、自动切换等）\n\n"
                "游戏正在运行时第 ④ 步会跳过。\n"
                "确定要恢复吗？", icon="warning"):
            return

        done, bad = [], []

        # ① 分辨率 ② 缩放
        if self.mon:
            n = self.conf.get("native") or {}
            nw = n.get("w") or core.native_of(self.mon)[0]
            nh = n.get("h") or core.native_of(self.mon)[1]
            ok, msg = core.set_mode(self.mon, nw, nh, n.get("hz"), persist=True)
            done.append("① 分辨率 → %s%s" % (msg, "" if ok else "（失败）"))
            if not ok:
                bad.append("分辨率切换失败：" + msg)
            sok, smsg = core.set_scaling(False, device=self.mon.get("device"))
            done.append("② 缩放 → %s" % smsg)
        else:
            done.append("①② 没有可用显示器，跳过")

        # ③ 系统项
        okn, detail = sysx.apply_snapshot(self.conf.get("sys_snapshot"))
        done.append("③ 系统项 → 还原 %d 项" % okn)
        done.extend("     " + d for d in detail)
        if okn < len(sysx.items()):
            bad.append("部分系统项没还原成功，见上面明细")

        # ④ 游戏配置
        gi = self.game["game_ini"]
        if not gi:
            done.append("④ 游戏配置 → 没找到配置文件，跳过")
        elif game.game_running():
            done.append("④ 游戏配置 → 游戏正在运行，跳过（退出后再点一次）")
            bad.append("游戏配置未恢复：游戏在运行")
        else:
            latest = game.latest_backup(state.BACKUP_DIR)
            if not latest:
                done.append("④ 游戏配置 → 没有可用备份")
            else:
                ui = game.pick_user_ini(self.game["user_inis"],
                                        self.conf.get("user_ini"))
                n = game.restore(latest, gi, ui)
                done.append("④ 游戏配置 → 从 %s 还原 %d 个文件"
                            % (os.path.basename(latest), n))
                if not n:
                    bad.append("游戏配置还原失败，备份目录里没有目标文件")

        # ⑤ 软件设置
        keep_native = self.conf.get("native")
        self.conf = state.fresh()
        if keep_native:
            self.conf["native"] = keep_native
        self.conf["guide_done"] = True      # 别因为重置又弹一次引导
        state.save(self.conf)
        done.append("⑤ 软件设置 → 已清空")
        self.refresh_all()

        for d in done:
            self.say(d, "err" if "失败" in d or "跳过" in d else "ok")
        tail = ("\n\n建议重启一次电脑，粘滞键这类注册表项要注销后才完全生效。"
                if not bad else
                "\n\n需要处理的问题：\n· " + "\n· ".join(bad) +
                "\n\n建议重启一次电脑。")
        messagebox.showinfo("恢复完成", "\n".join(done) + tail)

    def one_tap_letterbox(self):
        """给不会操作显卡面板的人用：能自动做的全做完，做不了的给出针对性指引"""
        if not self.mon:
            return
        g = self.conf["game"]
        ok, msg, (rw, rh) = core.fix_letterbox(self.mon, g["w"], g["h"], g.get("hz"))
        self.say("① 分辨率与缩放：" + msg, "ok" if ok else "err")
        if not ok:
            messagebox.showerror("切换失败", msg)
            return
        self.refresh_all()

        if game.game_running():
            self.say("② 游戏正在运行，配置暂不能写", "warn")
            messagebox.showwarning(
                "先退出游戏",
                "画面已经切好了。\n\n但游戏正在运行，配置文件写不进去——"
                "游戏退出时会把内存里的旧设置写回文件，覆盖掉修改。\n\n"
                "请完全退出无畏契约，再点一次「去黑边」。")
            return

        gi = self.game["game_ini"]
        if not gi:
            self.say("② 没找到游戏配置文件", "err")
            messagebox.showwarning(
                "没找到游戏配置",
                "画面已经切好并拉伸了。\n\n但没找到无畏契约的配置文件，"
                "游戏内的 letterbox 关不掉。\n"
                "如果进游戏还有黑边，在游戏里把画面模式设成「全屏」。")
            return

        ui = game.pick_user_ini(self.game["user_inis"], self.conf.get("user_ini"))
        game.backup([x for x in (gi, ui) if x], state.BACKUP_DIR,
                    int(self.conf.get("backup_keep", 10)))
        kv = game.apply_display(gi, rw, rh, fullscreen=True,
                                no_vsync=True, stretch=True, unlock_fps=False)
        good, bad = game.verify(gi, kv)
        self.say("② 游戏配置：黑边已关闭" if good else "② 回读不一致：" + ",".join(bad),
                 "ok" if good else "err")
        self.refresh_banner()
        self.refresh_ini_label()

        tip = {
            "nvidia": "NVIDIA 控制面板 → 显示 →「调整桌面尺寸和位置」\n"
                      "　缩放模式选「全屏」\n"
                      "　勾选「覆盖游戏和程序设置的缩放模式」\n"
                      "　执行缩放选「GPU」",
            "amd": "AMD Software → 显示 →\n"
                   "　缩放模式选「整个面板」\n"
                   "　关闭「保持宽高比」",
            "intel": "Intel 显卡控制中心 → 显示 →\n"
                     "　缩放选「拉伸到全屏」",
            "unknown": "打开显卡控制面板 → 显示 / 缩放设置\n"
                       "　缩放模式改「全屏」或「拉伸」\n"
                       "　关闭「保持宽高比」",
        }.get(core.gpu_vendor(self.mon), "")
        messagebox.showinfo(
            "去黑边完成",
            "已经做完三件事：\n"
            "· 切到 %d×%d\n"
            "· 显卡缩放设成「拉伸填充」\n"
            "· 游戏配置里的黑边开关已关\n\n"
            "重启游戏看看：\n"
            "· 已经铺满 → 完事，什么都不用再设\n"
            "· 左右还有黑边 → 显卡里开着「覆盖游戏缩放」\n\n"
            "按下面手动关掉，只做一次：\n\n%s\n\n"
            "关掉这个窗口后，主界面右下角有个\n"
            "「点过去黑边还是没铺满？点这里」，\n"
            "里面是完整的排查顺序。" % (rw, rh, tip))

    # ------------------------------------------------------------ 自动切换

    def on_auto(self):
        self.conf["auto"] = bool(self.auto_var.get())
        state.save(self.conf)
        self._last_game = game.game_running()
        self.say("自动切换：" + ("开" if self.conf["auto"] else "关"), "ok")

    def tick(self):
        try:
            running = game.game_running()
            if self.auto_var.get() and running != self._last_game:
                self._last_game = running
                g = self.conf["game"]
                c = (self.mon["current"] or {}) if self.mon else {}
                if running and (c.get("w"), c.get("h")) != (g["w"], g["h"]):
                    self.apply_mode(g["w"], g["h"], g.get("hz"), "检测到游戏启动")
                elif not running and (c.get("w"), c.get("h")) == (g["w"], g["h"]):
                    n = self.conf.get("native") or {}
                    if n.get("w"):
                        self.apply_mode(n["w"], n["h"], n.get("hz"), "游戏已退出")
            else:
                self._last_game = running
            if self.mon:
                core.refresh(self.mon)
            self.refresh_stat()
            self.refresh_ini_label()
        except Exception:
            state.log("tick 异常：\n" + traceback.format_exc())
        finally:
            if not self._closing:
                self.root.after(1800, self.tick)

    # ------------------------------------------------------------ 引导 / 诊断

    def show_guide(self):
        win = getattr(self, "_guide_win", None)
        if win is not None and win.winfo_exists():
            win.lift()
            win.focus_force()
            return
        top = tk.Toplevel(self.root)
        self._guide_win = top
        top.title("第一次使用")
        top.configure(bg=CARD)
        top.transient(self.root)
        top.resizable(False, False)
        steps = ("① 先点「去黑边」（只做一次）\n"
                 "   它会自动做完三件事：切 4:3、把显卡缩放设成拉伸、\n"
                 "   关掉游戏配置里的黑边开关。\n"
                 "   点完重启游戏看看，大多数机器到这一步就铺满了。\n\n"
                 "② 选一个 4:3 分辨率\n"
                 "   点「1280×960」卡片，或者自己填宽高。\n\n"
                 "③ 让程序留在后台\n"
                 "   开着「自动切换」，以后进游戏自动切 4:3，退游戏自动切回来。\n"
                 "   窗口可以最小化，但别关掉。")
        tk.Label(top, text="三步就能用起来", bg=CARD, fg=TXT,
                 font=(FF, 13, "bold")).pack(anchor="w", padx=22, pady=(18, 8))
        tk.Label(top, text=steps, bg=CARD, fg=SUB, font=(FF, 10),
                 justify="left").pack(anchor="w", padx=22)
        bar = tk.Frame(top, bg=CARD)
        bar.pack(fill="x", padx=22, pady=(14, 18))
        tk.Button(bar, text="知道了", font=(FF, 10, "bold"), bg=ACC, fg="#fff",
                  activebackground=ACC_DK, relief="flat", bd=0, cursor="hand2",
                  padx=24, pady=5,
                  command=self._guide_close).pack(side="right")
        tk.Button(bar, text="打开显卡缩放设置", font=(FF, 9), bg=CARD2, fg=TXT,
                  activebackground=LINE, relief="flat", bd=0, cursor="hand2",
                  padx=12, pady=5, command=self.open_nvidia).pack(side="right", padx=8)
        self.guide_no_more = tk.BooleanVar(value=True)
        tk.Checkbutton(bar, text="不再提示", variable=self.guide_no_more,
                       bg=CARD, fg=SUB, selectcolor=CARD2, activebackground=CARD,
                       activeforeground=TXT, font=(FF, 9), bd=0, highlightthickness=0,
                       cursor="hand2").pack(side="left")
        # 点 X 或按 Esc 也算看过了，否则每次启动都会再弹一次
        top.protocol("WM_DELETE_WINDOW", self._guide_close)
        top.bind("<Escape>", lambda e: self._guide_close())
        self.center_on_parent(top)
        top.lift()
        top.focus_force()

    def _guide_close(self):
        # 只有勾了「不再提示」才记住；否则下次启动还会弹，方便随时回看
        if getattr(self, "guide_no_more", None) is None or self.guide_no_more.get():
            self._guide_done()
        win = getattr(self, "_guide_win", None)
        if win is not None and win.winfo_exists():
            win.destroy()
        self._guide_win = None

    def _guide_done(self):
        if not self.conf.get("guide_done"):
            self.conf["guide_done"] = True
            state.save(self.conf)

    def show_letterbox_help(self):
        """「覆盖游戏缩放」灰掉时的排查清单——这是最常见的卡点"""
        win = getattr(self, "_lb_win", None)
        if win is not None and win.winfo_exists():
            win.lift()
            win.focus_force()
            return
        top = tk.Toplevel(self.root)
        self._lb_win = top
        top.title("去黑边没铺满？按这个查")
        top.configure(bg=BG)
        top.transient(self.root)
        body = (
            "　\n"
            "第一步：先确认「去黑边」真的跑完了\n"
            "────────────────────────\n\n"
            "切回主界面点一次「去黑边」，然后看下面日志区最后两行：\n\n"
            "· 写着「缩放已设为拉伸填充」\n"
            "  → 已经生效了。进游戏前记得重启游戏，进游戏看是不是铺满。\n"
            "    如果游戏里还是黑的，说明是游戏自己的 letterbox，\n"
            "    确认日志里「游戏配置：黑边已关闭」也在。\n\n"
            "· 写着「已提交但未生效，可能被显卡驱动接管」\n"
            "  → 系统不接管缩放，得靠显卡面板。往下走第二步。\n\n"
            "· 写着「系统拒绝了缩放变更（代码 xxx）」\n"
            "  → 系统层面被拦，通常是权限或远程会话，往下走第二步。\n\n\n"
            "　\n"
            "第二步：还不行，按顺序排查\n"
            "────────────────────────\n\n"
            "①  先把分辨率切成 4:3，再回头看显卡面板\n"
            "     不少驱动在「原生分辨率」下会把缩放相关选项整列灰掉。\n"
            "     先在主界面切到 4:3，再打开面板看一次。\n\n"
            "②  确认「选择显示器」选对了\n"
            "     面板左上角有个显示器下拉框。多屏时必须选中你打游戏的那台，\n"
            "     选错的话右边整列都是灰的。\n\n"
            "③  笔记本内屏通常不支持\n"
            "     内屏走的是 eDP，多数机型不给「覆盖游戏缩放」这个开关。\n"
            "     这种情况只能外接显示器，或者接受内屏按比例显示。\n\n"
            "④  别经过转接器 / 扩展坞\n"
            "     USB-C 转 HDMI、KVM 切换器、老扩展坞都可能让缩放选项失效。\n"
            "     换一根 DP 或 HDMI 直连再试一次。\n\n"
            "⑤  驱动版本问题\n"
            "     新版 NVIDIA App 把设置挪到了：设置 → 显示 → 缩放。\n"
            "     太老的驱动根本没有这一项，更新一次就好。\n\n\n"
            "　\n"
            "小抄：显卡面板里到底要改哪一项\n"
            "────────────────────────\n\n"
            "NVIDIA：控制面板 → 显示 → 调整桌面尺寸和位置\n"
            "　　　　缩放模式选「全屏」\n"
            "　　　　勾选「覆盖游戏和程序设置的缩放模式」\n"
            "　　　　执行缩放选「GPU」\n\n"
            "AMD：Software → 显示\n"
            "　　　　缩放模式选「整个面板」，关掉「保持宽高比」\n\n"
            "Intel：显卡控制中心 → 显示 → 缩放 → 「拉伸到全屏」\n\n\n"
            "　\n"
            "最后一条：如果以上都不行\n"
            "────────────────────────\n\n"
            "把主界面按 F1 导出的诊断信息发给作者，里面带显示器型号、\n"
            "显卡、当前缩放模式和日志，比截图有用得多。"
        )
        box = tk.Text(top, bg="#0a0c10", fg=SUB, font=(FF, 11), relief="flat", bd=0,
                      padx=22, pady=18, wrap="word", highlightthickness=1,
                      highlightbackground=LINE)
        box.pack(fill="both", expand=True, padx=14, pady=(14, 8))
        box.insert("1.0", body)
        box.configure(state="disabled")
        bar = tk.Frame(top, bg=BG)
        bar.pack(fill="x", padx=14, pady=(0, 14))
        tk.Button(bar, text="打开显卡设置", font=(FF, 10), bg=CARD2, fg=TXT,
                  activebackground=LINE, relief="flat", bd=0, cursor="hand2",
                  padx=16, pady=5, command=self.open_nvidia).pack(side="left")
        tk.Button(bar, text="知道了", font=(FF, 10, "bold"), bg=ACC, fg="#fff",
                  activebackground=ACC_DK, relief="flat", bd=0, cursor="hand2",
                  padx=22, pady=5,
                  command=lambda: (top.destroy(), setattr(self, "_lb_win", None))
                  ).pack(side="right")
        self.center_on_parent(top, self.px(760), self.px(680))

    def show_diagnose(self):
        text = state.diagnose(self.mon, {
            "游戏进程": "运行中" if game.game_running() else "未运行",
            "游戏配置": self.game["game_ini"] or "未找到",
            "备份数量": len(game.list_backups(state.BACKUP_DIR)),
        })
        p = state.write_diagnose(text)
        top = tk.Toplevel(self.root)
        top.title("诊断信息")
        top.configure(bg=BG)
        top.transient(self.root)
        self.center_on_parent(top, self.px(760), self.px(560))
        box = tk.Text(top, bg="#0a0c10", fg=SUB, font=("Consolas", 9),
                      relief="flat", bd=0, padx=12, pady=10, wrap="none")
        box.pack(fill="both", expand=True, padx=12, pady=(12, 6))
        box.insert("1.0", text)
        box.configure(state="disabled")
        bar = tk.Frame(top, bg=BG)
        bar.pack(fill="x", padx=12, pady=(0, 12))
        tk.Button(bar, text="复制到剪贴板", font=(FF, 9), bg=CARD2, fg=TXT,
                  activebackground=LINE, relief="flat", bd=0, cursor="hand2",
                  padx=12, pady=4,
                  command=lambda: self.say("已复制诊断信息" if state.copy_clipboard(text)
                                           else "复制失败", "ok")).pack(side="left")
        if p:
            tk.Label(bar, text="已保存 " + p, bg=BG, fg=DIM,
                     font=(FF, 8)).pack(side="left", padx=10)

    # ------------------------------------------------------------ 退出 / 异常

    def on_close(self):
        if self.auto_var.get() and not self._closing:
            if not messagebox.askyesno(
                    "确认退出",
                    "「自动切换」需要程序一直运行。\n"
                    "关掉它，以后进游戏就不会自动切成 4:3 了。\n\n仍然退出？"):
                return
        self._closing = True
        # 退出前还原分辨率：否则关机时系统会把 4:3 记成"上次状态"，下次开机卡在 4:3
        try:
            if self.mon:
                c = self.mon["current"] or {}
                g = self.conf["game"]
                if (c.get("w"), c.get("h")) == (g["w"], g["h"]):
                    n = self.conf.get("native") or {}
                    nw = n.get("w") or core.native_of(self.mon)[0]
                    nh = n.get("h") or core.native_of(self.mon)[1]
                    ok, msg = core.set_mode(self.mon, nw, nh, n.get("hz"),
                                            persist=True)
                    try:
                        core.set_scaling(False, device=self.mon.get("device"))
                    except Exception:
                        pass
                    state.log("退出还原：%s %s" % (ok, msg))
        except Exception:
            state.log("退出还原失败：\n" + traceback.format_exc())
        try:
            self.conf["monitor_id"] = self.mon["monitor_id"] if self.mon else None
            state.save(self.conf)
        except Exception:
            pass
        self.root.destroy()

    def on_tk_error(self, exc, val, tb):
        text = traceback.format_exception(exc, val, tb)
        p = state.crash_dump("".join(text))
        try:
            messagebox.showerror("出错了",
                                 "程序遇到一个异常，已记录到：\n%s\n\n界面还能继续用，"
                                 "如果反复出现请把日志发给开发者。" % (p or state.DATA_DIR))
        except Exception:
            pass


def run():
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        pass
    root = tk.Tk()
    try:
        root.tk.call("tk", "scaling", root.winfo_fpixels("1i") / 72.0)
    except Exception:
        pass
    try:
        App(root)
    except Exception:
        p = state.crash_dump(traceback.format_exc())
        try:
            messagebox.showerror("启动失败", "程序启动失败，日志：\n%s" % (p or state.DATA_DIR))
        except Exception:
            pass
        raise
    root.mainloop()
