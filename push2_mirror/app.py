"""投屏核心:抓取屏幕区域 -> 缩放 -> 转 BGR565 -> 推送给 Push 2。

双线程流水线:采集线程持续抓取+转码并保留最新一帧,发送线程不停推送。
支持外部停止信号与状态回调,便于 GUI 控制与展示。
"""

import sys
import threading
import time

from .capture import make_capturer
from .display import Push2Display, Push2DisplayError
from .framebuffer import image_to_frame, rotate_image, scale_image


class _HighResTimer:
    """在 Windows 上把系统定时器精度临时提到 1ms,使 time.sleep 精确。"""

    def __enter__(self):
        self._set = False
        if sys.platform == "win32":
            try:
                import ctypes

                ctypes.windll.winmm.timeBeginPeriod(1)
                self._set = True
            except Exception:
                pass
        return self

    def __exit__(self, *exc):
        if self._set:
            try:
                import ctypes

                ctypes.windll.winmm.timeEndPeriod(1)
            except Exception:
                pass


class MirrorApp:
    def __init__(self, region, fps=60, scale_mode="fit", rotation=0, verbose=True,
                 status_cb=None, stop_event=None):
        self.region = region
        self.fps = max(1, min(144, int(fps)))
        self.scale_mode = scale_mode
        self.rotation = int(rotation) % 360
        self.verbose = verbose
        self._status_cb = status_cb
        self._stop = stop_event or threading.Event()
        self._poll_interval = 1.0 / self.fps

    # ------------------------------------------------------------------ #
    def _emit(self, **event):
        if self._status_cb is not None:
            try:
                self._status_cb(event)
            except Exception:
                pass

    def stop(self):
        self._stop.set()

    # ------------------------------------------------------------------ #
    def run(self, duration=None):
        with _HighResTimer():
            return self._run(duration)

    def _run(self, duration=None):
        display = Push2Display()
        try:
            display.open()
        except Push2DisplayError as exc:
            msg = str(exc)
            if self.verbose:
                print("[错误] 无法连接 Push 2 显示屏:\n%s" % msg, file=sys.stderr)
            self._emit(type="error", msg=msg)
            self._emit(type="stopped")
            return 1

        lock = threading.Lock()
        holder = {"frame": None}
        capture_error = {"exc": None}
        backend_name = {"name": "?"}
        stop = self._stop

        def set_latest(data):
            with lock:
                holder["frame"] = data

        def get_latest():
            with lock:
                return holder["frame"]

        def capture_loop():
            cap = None
            try:
                cap = make_capturer(self.region, prefer_fast=True)
                backend_name["name"] = cap.backend
                while not stop.is_set():
                    t0 = time.perf_counter()
                    img = cap.grab()
                    if img is not None:
                        if self.rotation:
                            img = rotate_image(img, self.rotation)
                        set_latest(image_to_frame(scale_image(img, self.scale_mode)))
                    dt = time.perf_counter() - t0
                    if dt < self._poll_interval:
                        time.sleep(self._poll_interval - dt)
            except Exception as exc:  # noqa: BLE001
                capture_error["exc"] = exc
                stop.set()
            finally:
                if cap is not None:
                    cap.close()
                cap = None
                import gc
                gc.collect()

        worker = threading.Thread(target=capture_loop, name="capture", daemon=True)
        worker.start()

        t_wait = time.time()
        while get_latest() is None and not stop.is_set():
            if time.time() - t_wait > 5.0:
                break
            time.sleep(0.005)

        if not stop.is_set():
            if self.verbose:
                print(
                    "已连接 Push 2(采集后端:%s)。区域 left=%d top=%d %dx%d。Ctrl+C 停止。"
                    % (backend_name["name"], self.region.left, self.region.top,
                       self.region.width, self.region.height)
                )
            self._emit(type="connected", backend=backend_name["name"])

        frames = 0
        t_report = time.time()
        t_start = time.time()
        exit_code = 0
        try:
            while not stop.is_set():
                t_loop = time.perf_counter()
                if duration is not None and (time.time() - t_start) >= duration:
                    break
                data = get_latest()
                if data is None:
                    time.sleep(0.002)
                    continue
                display.send_frame(data)

                lag = time.perf_counter() - t_loop
                if lag < self._poll_interval:
                    time.sleep(self._poll_interval - lag)

                frames += 1
                elapsed = time.time() - t_report
                if elapsed >= 1.0:
                    fps = frames / elapsed
                    if self.verbose:
                        print("\r实时帧率:%5.1f FPS (后端 %s) " %
                              (fps, backend_name["name"]), end="", flush=True)
                    self._emit(type="fps", fps=fps, backend=backend_name["name"])
                    frames = 0
                    t_report = time.time()
        except KeyboardInterrupt:
            if self.verbose:
                print("\n正在停止并清屏...")
        except Push2DisplayError as exc:
            if self.verbose:
                print("\n[错误] 投屏过程中断:%s" % exc, file=sys.stderr)
            self._emit(type="error", msg=str(exc))
            exit_code = 1
        finally:
            stop.set()
            worker.join(timeout=2.0)
            try:
                display.clear()
            except Push2DisplayError:
                pass
            display.close()

        if capture_error["exc"] is not None:
            if self.verbose:
                print("\n[错误] 屏幕抓取失败:%s" % capture_error["exc"], file=sys.stderr)
            self._emit(type="error", msg="屏幕抓取失败:%s" % capture_error["exc"])
            self._emit(type="stopped")
            return 1

        self._emit(type="stopped")
        return exit_code


class MirrorController:
    """供 GUI 使用:在后台线程启动/停止投屏,并通过回调上报状态。"""

    def __init__(self):
        self._thread = None
        self._stop = threading.Event()
        self._app = None
        self.running = False

    def start(self, settings, status_cb=None):
        if self.running:
            return
        self._stop = threading.Event()
        self._app = MirrorApp(
            settings.region,
            fps=settings.fps,
            scale_mode=settings.scale_mode,
            rotation=settings.rotation,
            verbose=False,
            status_cb=status_cb,
            stop_event=self._stop,
        )
        self.running = True

        def runner():
            try:
                self._app.run()
            finally:
                self.running = False

        self._thread = threading.Thread(target=runner, name="mirror", daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        t = self._thread
        if t is not None and t.is_alive():
            t.join(timeout=3.0)
        self.running = False
        self._thread = None
