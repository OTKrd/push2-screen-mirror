"""Push 2 投屏的图形界面(customtkinter)+ 系统托盘(pystray)。"""

import threading

import customtkinter as ctk
from PIL import Image, ImageDraw

from . import display as disp
from .app import MirrorController
from .midi import Push2Midi
from .selector import select_region
from .settings import (
    SCALE_MODE_LABELS,
    SCALE_MODES,
    load_settings,
    save_settings,
)

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

_GREEN = "#19ff8b"
_RED = "#ff5c5c"
_GRAY = "#888888"

_SCALE_LABEL_TO_MODE = {v: k for k, v in SCALE_MODE_LABELS.items()}

# 顺时针旋转角度
ROTATION_LABELS = {0: "不旋转", 90: "顺时针 90°", 180: "180°", 270: "逆时针 90°"}
_ROTATION_ORDER = [0, 90, 180, 270]
_ROTATION_LABEL_TO_DEG = {v: k for k, v in ROTATION_LABELS.items()}


def _make_icon_image():
    img = Image.new("RGB", (64, 64), (24, 26, 32))
    d = ImageDraw.Draw(img)
    d.rectangle([6, 22, 58, 42], fill=(25, 255, 139))
    d.text((18, 25), "P2", fill=(0, 0, 0))
    return img


class Push2MirrorGUI(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.settings = load_settings()
        self.controller = MirrorController()
        self.midi = Push2Midi()
        self._tray = None
        self._quitting = False
        self._bright_after = None

        self.title("Push 2 投屏")
        self.geometry("460x560")
        self.resizable(False, False)

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._hide_to_tray)

        self._init_midi_async()
        self._start_tray()
        self._refresh_region_label()
        self._poll_connection()

        if self.settings.autostart and self.settings.region is not None:
            self.after(700, self._start)

    # ------------------------------------------------------------------ #
    # 界面
    # ------------------------------------------------------------------ #
    def _build_ui(self):
        pad = {"padx": 18, "pady": (0, 10)}

        title = ctk.CTkLabel(self, text="Push 2 屏幕投屏",
                             font=ctk.CTkFont(size=20, weight="bold"))
        title.pack(padx=18, pady=(18, 4), anchor="w")

        # 状态行
        status_row = ctk.CTkFrame(self, fg_color="transparent")
        status_row.pack(fill="x", **pad)
        self.dot = ctk.CTkLabel(status_row, text="●", text_color=_GRAY,
                                font=ctk.CTkFont(size=18))
        self.dot.pack(side="left")
        self.status_label = ctk.CTkLabel(status_row, text="检测中…",
                                         font=ctk.CTkFont(size=14))
        self.status_label.pack(side="left", padx=(6, 0))

        # 区域卡片
        region_card = ctk.CTkFrame(self)
        region_card.pack(fill="x", **pad)
        ctk.CTkLabel(region_card, text="投屏区域",
                     font=ctk.CTkFont(size=13, weight="bold")).pack(
            anchor="w", padx=14, pady=(12, 2))
        self.region_label = ctk.CTkLabel(region_card, text="(未设置)",
                                         text_color=_GRAY)
        self.region_label.pack(anchor="w", padx=14)
        ctk.CTkButton(region_card, text="重新框选区域",
                      command=self._select_region).pack(
            anchor="w", padx=14, pady=12)

        # 缩放方式
        scale_row = ctk.CTkFrame(self, fg_color="transparent")
        scale_row.pack(fill="x", **pad)
        ctk.CTkLabel(scale_row, text="缩放方式").pack(side="left")
        self.scale_menu = ctk.CTkOptionMenu(
            scale_row,
            values=[SCALE_MODE_LABELS[m] for m in SCALE_MODES],
            command=self._on_scale_change,
            width=200,
        )
        self.scale_menu.set(SCALE_MODE_LABELS.get(self.settings.scale_mode,
                                                  SCALE_MODE_LABELS["fit"]))
        self.scale_menu.pack(side="right")

        # 旋转(竖向框选 -> 横向显示)
        rot_row = ctk.CTkFrame(self, fg_color="transparent")
        rot_row.pack(fill="x", **pad)
        ctk.CTkLabel(rot_row, text="旋转").pack(side="left")
        self.rot_menu = ctk.CTkOptionMenu(
            rot_row,
            values=[ROTATION_LABELS[d] for d in _ROTATION_ORDER],
            command=self._on_rotation_change,
            width=200,
        )
        self.rot_menu.set(ROTATION_LABELS.get(self.settings.rotation, "不旋转"))
        self.rot_menu.pack(side="right")

        # 背光亮度
        bright_card = ctk.CTkFrame(self, fg_color="transparent")
        bright_card.pack(fill="x", **pad)
        head = ctk.CTkFrame(bright_card, fg_color="transparent")
        head.pack(fill="x")
        ctk.CTkLabel(head, text="背光亮度").pack(side="left")
        self.bright_value_label = ctk.CTkLabel(head, text=str(self.settings.brightness),
                                               text_color=_GRAY)
        self.bright_value_label.pack(side="right")
        self.bright_slider = ctk.CTkSlider(bright_card, from_=0, to=255,
                                           command=self._on_brightness)
        self.bright_slider.set(self.settings.brightness)
        self.bright_slider.pack(fill="x", pady=(6, 0))

        # 自启
        self.autostart_var = ctk.BooleanVar(value=self.settings.autostart)
        ctk.CTkCheckBox(self, text="启动时自动用上次区域开始投屏",
                        variable=self.autostart_var,
                        command=self._on_autostart).pack(anchor="w", **pad)

        # 开始/停止
        self.toggle_btn = ctk.CTkButton(self, text="▶  开始投屏", height=44,
                                        font=ctk.CTkFont(size=16, weight="bold"),
                                        command=self._toggle)
        self.toggle_btn.pack(fill="x", padx=18, pady=(6, 6))

        self.hint_label = ctk.CTkLabel(self, text="关闭窗口将最小化到系统托盘",
                                       text_color=_GRAY,
                                       font=ctk.CTkFont(size=11))
        self.hint_label.pack(pady=(0, 10))

    # ------------------------------------------------------------------ #
    # 投屏控制
    # ------------------------------------------------------------------ #
    def _toggle(self):
        if self.controller.running:
            self._stop()
        else:
            self._start()

    def _start(self):
        if self.controller.running:
            return
        if self.settings.region is None:
            self._set_status("请先框选投屏区域", _RED)
            return
        self.controller.start(self.settings, status_cb=self._status_cb)
        self.toggle_btn.configure(text="■  停止投屏")
        self._set_status("正在连接…", _GRAY)

    def _stop(self):
        self.controller.stop()
        self.toggle_btn.configure(text="▶  开始投屏")
        self._set_status("已停止", _GRAY)

    def _status_cb(self, event):
        # 来自后台线程,转回主线程更新 UI
        self.after(0, self._apply_status, event)

    def _apply_status(self, event):
        et = event.get("type")
        if et == "connected":
            self._set_status("投屏中 (后端 %s)" % event.get("backend", "?"), _GREEN)
        elif et == "fps":
            self._set_status("投屏中  %.1f FPS  (后端 %s)"
                             % (event.get("fps", 0), event.get("backend", "?")), _GREEN)
        elif et == "error":
            self._set_status("错误:%s" % event.get("msg", ""), _RED)
            self.toggle_btn.configure(text="▶  开始投屏")
        elif et == "stopped":
            if not self.controller.running:
                self.toggle_btn.configure(text="▶  开始投屏")

    # ------------------------------------------------------------------ #
    # 区域 / 缩放 / 亮度 / 自启
    # ------------------------------------------------------------------ #
    def _select_region(self):
        # 旋转 90/270 时,框选目标比例改为竖向 1:6,使旋转后正好填满 6:1。
        target_ratio = (1.0 / 6.0) if self.settings.rotation in (90, 270) else 6.0
        region = select_region(initial=self.settings.region, master=self,
                               target_ratio=target_ratio)
        if region is not None:
            self.settings.region = region
            save_settings(self.settings)
            self._refresh_region_label()

    def _refresh_region_label(self):
        r = self.settings.region
        if r is None:
            self.region_label.configure(text="(未设置)", text_color=_GRAY)
        else:
            self.region_label.configure(
                text="left=%d  top=%d   %d×%d" % (r.left, r.top, r.width, r.height),
                text_color="#dcdcdc",
            )

    def _on_scale_change(self, label):
        self.settings.scale_mode = _SCALE_LABEL_TO_MODE.get(label, "fit")
        save_settings(self.settings)
        self._restart_if_running()

    def _on_rotation_change(self, label):
        self.settings.rotation = _ROTATION_LABEL_TO_DEG.get(label, 0)
        save_settings(self.settings)
        self._restart_if_running()

    def _restart_if_running(self):
        if self.controller.running:
            self._stop()
            self.after(150, self._start)

    def _on_brightness(self, value):
        v = int(round(float(value)))
        self.settings.brightness = v
        self.bright_value_label.configure(text=str(v))
        if self._bright_after is not None:
            self.after_cancel(self._bright_after)
        self._bright_after = self.after(120, self._apply_brightness)

    def _apply_brightness(self):
        self._bright_after = None
        v = self.settings.brightness
        save_settings(self.settings)
        threading.Thread(target=self._send_brightness, args=(v,), daemon=True).start()

    def _send_brightness(self, v):
        try:
            self.midi.set_brightness(v)
        except Exception:
            pass

    def _on_autostart(self):
        self.settings.autostart = bool(self.autostart_var.get())
        save_settings(self.settings)

    # ------------------------------------------------------------------ #
    # 连接状态轮询
    # ------------------------------------------------------------------ #
    def _poll_connection(self):
        if self._quitting:
            return
        threading.Thread(target=self._check_connection, daemon=True).start()
        self.after(2500, self._poll_connection)

    def _check_connection(self):
        try:
            connected = len(disp.list_push2_devices()) > 0
        except Exception:
            connected = False
        self.after(0, self._update_connection, connected)

    def _update_connection(self, connected):
        if self.controller.running:
            return  # 投屏中由状态回调负责显示
        if connected:
            self._set_status("Push 2 已连接,就绪", _GREEN)
        else:
            self._set_status("Push 2 未连接", _RED)

    def _set_status(self, text, color):
        self.status_label.configure(text=text)
        self.dot.configure(text_color=color)

    # ------------------------------------------------------------------ #
    # MIDI 初始化
    # ------------------------------------------------------------------ #
    def _init_midi_async(self):
        def init():
            try:
                self.midi.open()
                self.midi.set_brightness(self.settings.brightness)
            except Exception:
                pass
        threading.Thread(target=init, daemon=True).start()

    # ------------------------------------------------------------------ #
    # 系统托盘
    # ------------------------------------------------------------------ #
    def _start_tray(self):
        try:
            import pystray
        except Exception:
            self._tray = None
            return

        menu = pystray.Menu(
            pystray.MenuItem("显示窗口", self._tray_show, default=True),
            pystray.MenuItem("开始投屏", self._tray_start),
            pystray.MenuItem("停止投屏", self._tray_stop),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("退出", self._tray_quit),
        )
        self._tray = pystray.Icon("push2mirror", _make_icon_image(),
                                  "Push 2 投屏", menu)
        threading.Thread(target=self._tray.run, daemon=True).start()

    def _tray_show(self, *args):
        self.after(0, self._show_window)

    def _tray_start(self, *args):
        self.after(0, self._start)

    def _tray_stop(self, *args):
        self.after(0, self._stop)

    def _tray_quit(self, *args):
        self.after(0, self._quit)

    def _hide_to_tray(self):
        if self._tray is not None:
            self.withdraw()
        else:
            self._quit()

    def _show_window(self):
        self.deiconify()
        self.lift()
        self.focus_force()

    def _quit(self):
        self._quitting = True
        try:
            self.controller.stop()
        except Exception:
            pass
        try:
            self.midi.close()
        except Exception:
            pass
        if self._tray is not None:
            try:
                self._tray.stop()
            except Exception:
                pass
        self.destroy()


def run_gui():
    app = Push2MirrorGUI()
    app.mainloop()
