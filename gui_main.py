"""Push 2 投屏 - 图形界面入口。"""

import sys

# 多屏 + 缩放下保证框选与抓取坐标一致(customtkinter 也会做 DPI 处理)。
if sys.platform == "win32":
    try:
        import ctypes

        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

# 单实例互斥锁句柄(需在进程生命周期内保持引用,否则锁会被释放)。
_MUTEX_HANDLE = None
_MUTEX_NAME = "Push2ScreenMirror_SingleInstance_Mutex"
_WINDOW_TITLE = "Push 2 投屏"


def _ensure_single_instance():
    """保证只运行一个实例。已有实例时唤醒其窗口并返回 False。"""
    global _MUTEX_HANDLE
    if sys.platform != "win32":
        return True
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        ERROR_ALREADY_EXISTS = 183
        _MUTEX_HANDLE = kernel32.CreateMutexW(None, False, _MUTEX_NAME)
        if kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
            _focus_existing_window()
            return False
    except Exception:
        # 互斥锁不可用时不阻塞启动
        return True
    return True


def _focus_existing_window():
    try:
        import ctypes

        user32 = ctypes.windll.user32
        hwnd = user32.FindWindowW(None, _WINDOW_TITLE)
        if hwnd:
            SW_RESTORE = 9
            user32.ShowWindow(hwnd, SW_RESTORE)
            user32.SetForegroundWindow(hwnd)
    except Exception:
        pass


def main():
    if not _ensure_single_instance():
        return 0
    from push2_mirror.gui import run_gui

    run_gui()
    return 0


if __name__ == "__main__":
    rc = main()
    import os

    os._exit(rc if isinstance(rc, int) else 0)
