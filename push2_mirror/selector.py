"""交互式屏幕区域选择界面(基于 tkinter)。

打开一个覆盖主显示器的半透明遮罩,用鼠标拖拽画出一个矩形,
之后还可以:拖动矩形内部来移动、拖动边/角来调整大小。
按 Enter 或双击确认,按 Esc 取消。

返回绝对坐标的 :class:`Region`(已加上主显示器偏移)。
多显示器场景下,如需选择非主显示器区域,请改用命令行 ``--region``。
"""

import tkinter as tk

from .region import Region

_HANDLE_MARGIN = 8  # 判定"抓到边/角"的像素容差
_MIN_SIZE = 10
_TARGET_RATIO = 6.0  # Push 2 屏幕 960x160 = 6:1


def _virtual_desktop():
    """返回整个虚拟桌面(覆盖所有显示器)的 (left, top, width, height)。"""
    try:
        import mss

        with mss.mss() as sct:
            mon = sct.monitors[0]  # 0 = 全部显示器合成的虚拟桌面
            return mon["left"], mon["top"], mon["width"], mon["height"]
    except Exception:
        return 0, 0, 1920, 1080


class _RegionSelector:
    def __init__(self, initial=None, master=None, target_ratio=_TARGET_RATIO):
        self.result = None
        self._owns_root = master is None
        self._ratio = float(target_ratio) if target_ratio else _TARGET_RATIO
        # 虚拟桌面左上角在系统坐标中的偏移(副屏在左/上时可能为负)。
        self._offset_x, self._offset_y, vw, vh = _virtual_desktop()

        self.root = tk.Tk() if master is None else tk.Toplevel(master)
        self.root.title("选择投屏区域")
        # 用 overrideredirect + 精确 geometry 让遮罩横跨所有显示器,
        # 而不是被 fullscreen 限制在主屏。
        self.root.overrideredirect(True)
        self.root.geometry("%dx%d+%d+%d" % (vw, vh, self._offset_x, self._offset_y))
        self.root.attributes("-alpha", 0.35)
        self.root.attributes("-topmost", True)
        self.root.configure(bg="black")
        self.root.config(cursor="crosshair")

        self.canvas = tk.Canvas(
            self.root, bg="black", highlightthickness=0, cursor="crosshair",
            width=vw, height=vh,
        )
        self.canvas.pack(fill="both", expand=True)
        self.root.update_idletasks()
        self.root.focus_force()

        # 画布坐标范围即虚拟桌面尺寸;加上偏移即为系统绝对坐标。
        self.screen_w = vw
        self.screen_h = vh

        # 当前矩形(canvas 坐标),x0<x1, y0<y1
        self.x0 = self.y0 = self.x1 = self.y1 = None

        # 交互状态
        self._mode = None  # 'new' | 'move' | 'resize'
        self._resize_edge = None  # (left?, right?, top?, bottom?)
        self._drag_start = None
        self._rect_at_drag = None
        self._lock_ratio = False  # 锁定 6:1 比例

        # 画面元素
        self._rect_id = None
        self._dim_ids = []
        self._hint_id = None

        self._bind_events()
        self._init_rectangle(initial)
        self._redraw()

    # ------------------------------------------------------------------ #
    def _bind_events(self):
        c = self.canvas
        c.bind("<ButtonPress-1>", self._on_press)
        c.bind("<B1-Motion>", self._on_drag)
        c.bind("<ButtonRelease-1>", self._on_release)
        c.bind("<Double-Button-1>", lambda e: self._confirm())
        c.bind("<Motion>", self._on_hover)
        self.root.bind("<Return>", lambda e: self._confirm())
        self.root.bind("<KP_Enter>", lambda e: self._confirm())
        self.root.bind("<Escape>", lambda e: self._cancel())
        self.root.bind("<r>", lambda e: self._reset_ratio())
        self.root.bind("<R>", lambda e: self._reset_ratio())
        self.root.bind("<l>", lambda e: self._toggle_lock())
        self.root.bind("<L>", lambda e: self._toggle_lock())

    def _init_rectangle(self, initial):
        if initial is not None:
            x0 = initial.left - self._offset_x
            y0 = initial.top - self._offset_y
            x1 = x0 + initial.width
            y1 = y0 + initial.height
            if 0 <= x0 < self.screen_w and 0 <= y0 < self.screen_h:
                self.x0, self.y0 = x0, y0
                self.x1, self.y1 = x1, y1
                return
        # 默认给一个居中的、符合目标比例的参考框
        if self._ratio >= 1:
            w = int(self.screen_w * 0.6)
            h = max(_MIN_SIZE, int(w / self._ratio))
        else:
            h = int(self.screen_h * 0.6)
            w = max(_MIN_SIZE, int(h * self._ratio))
        self.x0 = (self.screen_w - w) // 2
        self.y0 = (self.screen_h - h) // 2
        self.x1 = self.x0 + w
        self.y1 = self.y0 + h

    # ------------------------------------------------------------------ #
    # 事件处理
    # ------------------------------------------------------------------ #
    def _on_press(self, event):
        x, y = event.x, event.y
        edge = self._hit_edge(x, y)
        if edge != (False, False, False, False):
            self._mode = "resize"
            self._resize_edge = edge
        elif self._inside(x, y):
            self._mode = "move"
        else:
            self._mode = "new"
            self.x0, self.y0 = x, y
            self.x1, self.y1 = x, y
        self._drag_start = (x, y)
        self._rect_at_drag = (self.x0, self.y0, self.x1, self.y1)

    def _on_drag(self, event):
        if self._mode is None:
            return
        x, y = self._clamp(event.x, event.y)
        ox0, oy0, ox1, oy1 = self._rect_at_drag
        dx = x - self._drag_start[0]
        dy = y - self._drag_start[1]

        if self._mode == "new":
            self.x1, self.y1 = x, y
        elif self._mode == "move":
            w = ox1 - ox0
            h = oy1 - oy0
            nx0 = min(max(0, ox0 + dx), self.screen_w - w)
            ny0 = min(max(0, oy0 + dy), self.screen_h - h)
            self.x0, self.y0 = nx0, ny0
            self.x1, self.y1 = nx0 + w, ny0 + h
        elif self._mode == "resize":
            left, right, top, bottom = self._resize_edge
            nx0, ny0, nx1, ny1 = ox0, oy0, ox1, oy1
            if left:
                nx0 = x
            if right:
                nx1 = x
            if top:
                ny0 = y
            if bottom:
                ny1 = y
            self.x0, self.y0, self.x1, self.y1 = nx0, ny0, nx1, ny1
        if self._lock_ratio:
            self._enforce_ratio()
        self._redraw()

    def _on_release(self, event):
        self._normalize()
        self._mode = None
        self._resize_edge = None
        self._redraw()

    def _on_hover(self, event):
        if self._mode is not None:
            return
        edge = self._hit_edge(event.x, event.y)
        cursor = self._cursor_for_edge(edge)
        if cursor is None:
            cursor = "fleur" if self._inside(event.x, event.y) else "crosshair"
        self.canvas.config(cursor=cursor)

    # ------------------------------------------------------------------ #
    # 几何辅助
    # ------------------------------------------------------------------ #
    def _norm_rect(self):
        x0, x1 = sorted((self.x0, self.x1))
        y0, y1 = sorted((self.y0, self.y1))
        return x0, y0, x1, y1

    def _normalize(self):
        self.x0, self.y0, self.x1, self.y1 = self._norm_rect()

    def _inside(self, x, y):
        x0, y0, x1, y1 = self._norm_rect()
        return x0 + _HANDLE_MARGIN < x < x1 - _HANDLE_MARGIN and \
            y0 + _HANDLE_MARGIN < y < y1 - _HANDLE_MARGIN

    def _hit_edge(self, x, y):
        x0, y0, x1, y1 = self._norm_rect()
        m = _HANDLE_MARGIN
        near_left = abs(x - x0) <= m and (y0 - m) <= y <= (y1 + m)
        near_right = abs(x - x1) <= m and (y0 - m) <= y <= (y1 + m)
        near_top = abs(y - y0) <= m and (x0 - m) <= x <= (x1 + m)
        near_bottom = abs(y - y1) <= m and (x0 - m) <= x <= (x1 + m)
        return (near_left, near_right, near_top, near_bottom)

    @staticmethod
    def _cursor_for_edge(edge):
        left, right, top, bottom = edge
        if (left and top) or (right and bottom):
            return "size_nw_se" if tk.TkVersion >= 8.6 else "sizing"
        if (right and top) or (left and bottom):
            return "size_ne_sw" if tk.TkVersion >= 8.6 else "sizing"
        if left or right:
            return "sb_h_double_arrow"
        if top or bottom:
            return "sb_v_double_arrow"
        return None

    def _clamp(self, x, y):
        return (
            min(max(0, x), self.screen_w),
            min(max(0, y), self.screen_h),
        )

    def _ratio_text(self):
        if self._ratio >= 1:
            return "%.0f:1" % self._ratio
        return "1:%.0f" % (1.0 / self._ratio)

    # ------------------------------------------------------------------ #
    # 比例相关
    # ------------------------------------------------------------------ #
    def _enforce_ratio(self):
        """在拖拽过程中把当前矩形约束为 6:1(锁定时调用)。"""
        x0, y0, x1, y1 = self.x0, self.y0, self.x1, self.y1
        if self._mode == "new":
            # 以起点为锚点,高度随宽度(保留方向符号)
            w = x1 - x0
            self.y1 = y0 + (abs(w) / self._ratio) * (1 if (y1 - y0) >= 0 else -1)
            return
        if self._mode != "resize":
            return
        left, right, top, bottom = self._resize_edge
        horizontal = left or right
        if horizontal:
            # 宽度变化为主 -> 由宽度推高度,竖直居中
            w = abs(x1 - x0)
            h = w / self._ratio
            cy = (y0 + y1) / 2.0
            self.y0, self.y1 = cy - h / 2.0, cy + h / 2.0
        else:
            # 仅竖直边变化 -> 由高度推宽度,水平居中
            h = abs(y1 - y0)
            w = h * self._ratio
            cx = (x0 + x1) / 2.0
            self.x0, self.x1 = cx - w / 2.0, cx + w / 2.0

    def _reset_ratio(self):
        """把当前框恢复成目标比例(保持中心),并夹回屏幕内。"""
        x0, y0, x1, y1 = self._norm_rect()
        cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
        if self._ratio >= 1:
            w = x1 - x0
            h = w / self._ratio
            if h > self.screen_h:
                h = self.screen_h
                w = h * self._ratio
        else:
            h = y1 - y0
            w = h * self._ratio
            if w > self.screen_w:
                w = self.screen_w
                h = w / self._ratio
        self.x0, self.x1 = cx - w / 2.0, cx + w / 2.0
        self.y0, self.y1 = cy - h / 2.0, cy + h / 2.0
        self._clamp_into_screen()
        self._normalize()
        self._redraw()

    def _toggle_lock(self):
        self._lock_ratio = not self._lock_ratio
        if self._lock_ratio:
            self._reset_ratio()  # 开启锁定时顺手对齐到 6:1
        else:
            self._redraw()

    def _clamp_into_screen(self):
        """把矩形整体平移/收缩到屏幕范围内。"""
        x0, y0, x1, y1 = self._norm_rect()
        w, h = x1 - x0, y1 - y0
        w = min(w, self.screen_w)
        h = min(h, self.screen_h)
        x0 = min(max(0, x0), self.screen_w - w)
        y0 = min(max(0, y0), self.screen_h - h)
        self.x0, self.y0, self.x1, self.y1 = x0, y0, x0 + w, y0 + h

    # ------------------------------------------------------------------ #
    # 绘制
    # ------------------------------------------------------------------ #
    def _redraw(self):
        c = self.canvas
        if self._rect_id is not None:
            c.delete(self._rect_id)
        for i in self._dim_ids:
            c.delete(i)
        self._dim_ids = []

        x0, y0, x1, y1 = self._norm_rect()
        self._rect_id = c.create_rectangle(
            x0, y0, x1, y1, outline="#19ff8b", width=2
        )
        # 四角手柄
        for hx, hy in ((x0, y0), (x1, y0), (x0, y1), (x1, y1)):
            self._dim_ids.append(
                c.create_rectangle(
                    hx - 4, hy - 4, hx + 4, hy + 4,
                    outline="#19ff8b", fill="#19ff8b",
                )
            )
        cx = (x0 + x1) // 2
        rt = self._ratio_text()

        # 尺寸标签:框的上方(空间不够则放下方)
        w = x1 - x0
        h = y1 - y0
        ratio = (w / h) if h else 0
        lock_txt = ("  [已锁定 %s]" % rt) if self._lock_ratio else ""
        size_label = "%d x %d  (比例 %.2f:1,目标 %s)%s" % (w, h, ratio, rt, lock_txt)
        sy = y0 - 14 if y0 > 22 else y1 + 32
        sx = min(max(cx, 160), self.screen_w - 160)
        self._dim_ids.append(
            c.create_text(sx, sy, fill="#19ff8b",
                          font=("Segoe UI", 12, "bold"), text=size_label)
        )

        # 操作提示:框的下方,跟随框移动(空间不够则放上方)
        hint = ("拖拽框选 · 拖动内部移动 · 拖边/角缩放 · "
                "R 恢复 %s · L 锁定/解锁 %s · Enter 确认 · Esc 取消" % (rt, rt))
        hy = y1 + 16 if y1 < self.screen_h - 26 else y0 - 36
        hx = min(max(cx, 360), self.screen_w - 360)
        self._dim_ids.append(
            c.create_text(hx, hy, fill="#9ad1ff",
                          font=("Segoe UI", 12, "bold"), text=hint)
        )

    # ------------------------------------------------------------------ #
    def _confirm(self):
        self._normalize()
        x0, y0, x1, y1 = self._norm_rect()
        w, h = x1 - x0, y1 - y0
        if w < _MIN_SIZE or h < _MIN_SIZE:
            return  # 太小,忽略确认
        self.result = Region(
            left=int(x0 + self._offset_x),
            top=int(y0 + self._offset_y),
            width=int(w),
            height=int(h),
        )
        self.root.destroy()

    def _cancel(self):
        self.result = None
        self.root.destroy()

    def run(self):
        if self._owns_root:
            self.root.mainloop()
        else:
            try:
                self.root.grab_set()
            except Exception:
                pass
            self.root.wait_window(self.root)
        return self.result


def select_region(initial=None, master=None, target_ratio=_TARGET_RATIO):
    """打开选择界面并返回用户确认的 :class:`Region`(取消则返回 None)。

    ``master`` 不为空时作为其子窗口运行(供已有 Tk 主窗口的 GUI 调用)。
    ``target_ratio`` 为 R 恢复 / L 锁定 时使用的目标宽高比(竖向用 <1,如 1/6)。
    """
    selector = _RegionSelector(initial=initial, master=master,
                               target_ratio=target_ratio)
    return selector.run()
