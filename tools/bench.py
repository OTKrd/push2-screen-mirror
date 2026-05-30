"""性能基准:分别测量 抓取 / 缩放 / 转码 / USB发送 四个阶段的耗时。"""

import sys
import time

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

if sys.platform == "win32":
    try:
        import ctypes
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            ctypes.windll.user32.SetProcessDPIAware()
        ctypes.windll.kernel32.SetConsoleOutputCP(65001)
    except Exception:
        pass

from push2_mirror.capture import ScreenCapturer
from push2_mirror.display import Push2Display, Push2DisplayError
from push2_mirror.framebuffer import fit_letterbox, image_to_frame
from push2_mirror.region import Region, load_region

N = 120


def bench():
    region = load_region()
    if region is None:
        import mss
        with mss.mss() as sct:
            mon = sct.monitors[1]
        region = Region(mon["left"], mon["top"], mon["width"], mon["height"])
    print("测试区域: left=%d top=%d %dx%d" % (region.left, region.top,
                                               region.width, region.height))

    cap = ScreenCapturer(region)
    try:
        disp = Push2Display().open()
        have_hw = True
    except Push2DisplayError as e:
        print("（无硬件,跳过 USB 发送测试:%s）" % e)
        disp = None
        have_hw = False

    t_grab = t_box = t_conv = t_send = 0.0
    # 预热
    for _ in range(5):
        img = cap.grab()
        framed = fit_letterbox(img)
        frame = image_to_frame(framed)
        if have_hw:
            disp.send_frame(frame)

    for _ in range(N):
        a = time.perf_counter()
        img = cap.grab()
        b = time.perf_counter()
        framed = fit_letterbox(img)
        c = time.perf_counter()
        frame = image_to_frame(framed)
        d = time.perf_counter()
        if have_hw:
            disp.send_frame(frame)
        e = time.perf_counter()
        t_grab += b - a
        t_box += c - b
        t_conv += d - c
        t_send += e - d

    cap.close()
    if disp:
        disp.clear()
        disp.close()

    def ms(x):
        return 1000.0 * x / N

    total = t_grab + t_box + t_conv + t_send
    print("\n每帧平均耗时:")
    print("  抓取 grab     : %6.2f ms" % ms(t_grab))
    print("  缩放 letterbox: %6.2f ms" % ms(t_box))
    print("  转码 convert  : %6.2f ms" % ms(t_conv))
    print("  发送 send     : %6.2f ms" % ms(t_send))
    print("  合计          : %6.2f ms  -> 理论上限 %.1f FPS" % (ms(total), N / total))


if __name__ == "__main__":
    bench()
