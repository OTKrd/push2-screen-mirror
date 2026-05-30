"""应用设置的持久化(区域 / 帧率 / 缩放方式 / 背光亮度 / 自启)。"""

import json
import os
from dataclasses import dataclass, field
from typing import Optional

from .region import Region

CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".push2_mirror")
SETTINGS_PATH = os.path.join(CONFIG_DIR, "settings.json")
LEGACY_REGION_PATH = os.path.join(CONFIG_DIR, "region.json")

SCALE_MODES = ("fit", "stretch", "crop")
SCALE_MODE_LABELS = {
    "fit": "留黑边(保持比例)",
    "stretch": "拉满(可能变形)",
    "crop": "裁剪填满(保持比例)",
}


@dataclass
class Settings:
    region: Optional[Region] = None
    fps: int = 60
    scale_mode: str = "fit"
    brightness: int = 255
    autostart: bool = False
    rotation: int = 0  # 顺时针旋转角度:0 / 90 / 180 / 270

    def normalized(self):
        self.fps = max(1, min(120, int(self.fps)))
        self.brightness = max(0, min(255, int(self.brightness)))
        if self.scale_mode not in SCALE_MODES:
            self.scale_mode = "fit"
        if int(self.rotation) % 360 not in (0, 90, 180, 270):
            self.rotation = 0
        else:
            self.rotation = int(self.rotation) % 360
        return self


def load_settings(path=SETTINGS_PATH):
    """读取设置;不存在时尝试迁移旧的 region.json,再不行返回默认设置。"""
    data = None
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (ValueError, OSError):
            data = None

    if data is None:
        # 迁移旧版仅含区域的配置
        region = _load_legacy_region()
        return Settings(region=region).normalized()

    region = None
    r = data.get("region")
    if isinstance(r, dict):
        try:
            region = Region(
                left=int(r["left"]), top=int(r["top"]),
                width=int(r["width"]), height=int(r["height"]),
            )
            if not region.is_valid():
                region = None
        except (KeyError, ValueError, TypeError):
            region = None

    s = Settings(
        region=region,
        fps=int(data.get("fps", 60)),
        scale_mode=str(data.get("scale_mode", "fit")),
        brightness=int(data.get("brightness", 255)),
        autostart=bool(data.get("autostart", False)),
        rotation=int(data.get("rotation", 0)),
    )
    return s.normalized()


def save_settings(settings, path=SETTINGS_PATH):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    settings.normalized()
    data = {
        "region": (
            {
                "left": settings.region.left,
                "top": settings.region.top,
                "width": settings.region.width,
                "height": settings.region.height,
            }
            if settings.region is not None
            else None
        ),
        "fps": settings.fps,
        "scale_mode": settings.scale_mode,
        "brightness": settings.brightness,
        "autostart": settings.autostart,
        "rotation": settings.rotation,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return path


def _load_legacy_region():
    if not os.path.exists(LEGACY_REGION_PATH):
        return None
    try:
        with open(LEGACY_REGION_PATH, "r", encoding="utf-8") as f:
            d = json.load(f)
        region = Region(
            left=int(d["left"]), top=int(d["top"]),
            width=int(d["width"]), height=int(d["height"]),
        )
        return region if region.is_valid() else None
    except (ValueError, KeyError, OSError, TypeError):
        return None
