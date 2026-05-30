"""截屏区域的数据结构与配置文件读写。"""

import json
import os
from dataclasses import asdict, dataclass

# 配置文件默认保存在用户目录下,跨运行保持选区。
DEFAULT_CONFIG_PATH = os.path.join(
    os.path.expanduser("~"), ".push2_mirror", "region.json"
)


@dataclass
class Region:
    """屏幕上的一块矩形区域(绝对坐标,单位:像素)。"""

    left: int
    top: int
    width: int
    height: int

    def to_mss(self):
        """转换为 mss.grab 所需的字典。"""
        return {
            "left": int(self.left),
            "top": int(self.top),
            "width": int(self.width),
            "height": int(self.height),
        }

    def is_valid(self):
        return self.width > 0 and self.height > 0


def save_region(region, path=DEFAULT_CONFIG_PATH):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(asdict(region), f, ensure_ascii=False, indent=2)
    return path


def load_region(path=DEFAULT_CONFIG_PATH):
    """读取已保存的区域,不存在或非法时返回 None。"""
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        region = Region(
            left=int(data["left"]),
            top=int(data["top"]),
            width=int(data["width"]),
            height=int(data["height"]),
        )
    except (ValueError, KeyError, OSError, TypeError):
        return None
    return region if region.is_valid() else None


def parse_region_arg(text):
    """解析形如 ``x,y,w,h`` 的命令行参数为 Region。"""
    parts = [p.strip() for p in text.split(",")]
    if len(parts) != 4:
        raise ValueError("区域格式应为 x,y,width,height,例如 0,0,1920,320")
    left, top, width, height = (int(p) for p in parts)
    region = Region(left=left, top=top, width=width, height=height)
    if not region.is_valid():
        raise ValueError("区域的宽和高必须为正数")
    return region
