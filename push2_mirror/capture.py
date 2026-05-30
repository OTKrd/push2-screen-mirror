"""屏幕区域采集。

优先使用 Desktop Duplication API(bettercam,实测比 mss 快 3 倍以上);
不可用、区域跨显示器、或导入失败时,自动回退到 mss。

两种后端的 ``grab()`` 都返回 RGB 的 ``PIL.Image``;DDA 后端在画面无变化时
返回 ``None``(表示"和上一帧相同"),调用方据此跳过重复编码与传输浪费。
"""

import time

from PIL import Image


# --------------------------------------------------------------------------- #
# mss 后端(跨平台、稳定,作为后备)
# --------------------------------------------------------------------------- #
class MssCapturer:
    backend = "mss"

    def __init__(self, region):
        import mss

        self.region = region
        self._sct = mss.mss()
        self._bbox = region.to_mss()

    def grab(self):
        shot = self._sct.grab(self._bbox)
        return Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")

    def close(self):
        try:
            self._sct.close()
        except Exception:
            pass


# --------------------------------------------------------------------------- #
# Desktop Duplication 后端(bettercam / dxcam)
# --------------------------------------------------------------------------- #
def _import_dda():
    """返回可用的 DDA 模块(bettercam 优先),都没有则返回 None。"""
    try:
        import bettercam

        return bettercam
    except Exception:
        pass
    try:
        import dxcam

        return dxcam
    except Exception:
        return None


def _find_output(dda, region):
    """通过模块工厂读取各输出的 DesktopCoordinates,找到完全包含该区域的输出。

    全程不创建 camera(只读 COM 描述),避免反复创建/释放导致的 COM 崩溃。
    返回 (device_idx, output_idx, (left, top, right, bottom));找不到或跨屏返回 None。
    """
    factory = getattr(dda, "__factory", None)
    outputs_by_device = getattr(factory, "outputs", None)
    if not outputs_by_device:
        return None

    cx = region.left + region.width // 2
    cy = region.top + region.height // 2

    for dev_idx, outputs in enumerate(outputs_by_device):
        for out_idx, output in enumerate(outputs):
            try:
                output.update_desc()
                dc = output.desc.DesktopCoordinates
                left, top, right, bottom = dc.left, dc.top, dc.right, dc.bottom
            except Exception:
                continue
            if left <= cx < right and top <= cy < bottom:
                fully_inside = (
                    region.left >= left
                    and region.top >= top
                    and region.left + region.width <= right
                    and region.top + region.height <= bottom
                )
                return (dev_idx, out_idx, (left, top, right, bottom)) if fully_inside \
                    else None
    return None


class DdaCapturer:
    backend = "dda"

    def __init__(self, region):
        dda = _import_dda()
        if dda is None:
            raise RuntimeError("未安装 bettercam/dxcam")
        self.backend = getattr(dda, "__name__", "dda")

        found = _find_output(dda, region)
        if found is None:
            raise RuntimeError("未找到完全包含该区域的单个显示器(可能跨屏)")
        dev, out, (left, top, right, bottom) = found

        self.region = region
        # 用原生 BGRA 输出,避免 bettercam 在做颜色转换时依赖 opencv(cv2);
        # 我们随后用 PIL 的 "BGRX" 解码直接得到 RGB。
        self._cam = dda.create(device_idx=dev, output_idx=out, output_color="BGRA")
        self._local = (
            region.left - left,
            region.top - top,
            region.left - left + region.width,
            region.top - top + region.height,
        )

        # 预取首帧:静态桌面下也保证拿到一帧初始画面。
        self._primed = None
        deadline = time.time() + 0.5
        while time.time() < deadline:
            a = self._cam.grab(region=self._local)
            if a is not None:
                self._primed = self._to_rgb(a)
                break
            time.sleep(0.01)

    @staticmethod
    def _to_rgb(arr):
        # arr 为 BGRA 的 numpy 数组 (H, W, 4);用 "BGRX" 解码直接得到 RGB。
        h, w = arr.shape[:2]
        return Image.frombytes("RGB", (w, h), arr.tobytes(), "raw", "BGRX")

    def grab(self):
        if self._primed is not None:
            img = self._primed
            self._primed = None
            return img
        arr = self._cam.grab(region=self._local)
        if arr is None:
            return None  # 画面无变化,沿用上一帧
        return self._to_rgb(arr)

    def close(self):
        try:
            self._cam.release()
        except Exception:
            pass


# --------------------------------------------------------------------------- #
def make_capturer(region, prefer_fast=True):
    """根据区域和环境选择最优采集后端;失败时回退到 mss。"""
    if prefer_fast:
        try:
            return DdaCapturer(region)
        except Exception:
            pass
    return MssCapturer(region)
