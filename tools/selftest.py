"""离线自检:验证模块导入与帧缓冲转换的正确性(无需连接硬件)。"""

import sys

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

import numpy as np
from PIL import Image

from push2_mirror.display import FRAME_BYTES, LINE_BYTES, DISPLAY_HEIGHT, DISPLAY_WIDTH
from push2_mirror.framebuffer import (
    black_frame_bytes,
    fit_letterbox,
    image_to_frame,
    _XOR_PATTERN_U16,
)


def test_sizes():
    assert FRAME_BYTES == 327680, FRAME_BYTES
    assert LINE_BYTES == 2048
    assert len(black_frame_bytes()) == FRAME_BYTES
    print("[ok] 帧尺寸常量正确:FRAME_BYTES=%d" % FRAME_BYTES)


def test_xor_pattern():
    # 还原成字节序列,应为 E7 F3 E7 FF 循环
    raw = _XOR_PATTERN_U16.astype("<u2").tobytes()
    expected = bytes([0xE7, 0xF3, 0xE7, 0xFF]) * (len(raw) // 4)
    assert raw == expected, raw[:8]
    print("[ok] XOR 模式字节序正确:E7 F3 E7 FF 循环")


def _decode_pixel(le16):
    """把一个 16 位小端 BGR565 值解码回 (r,g,b) 的高位近似。"""
    v = le16
    b = (v >> 11) & 0x1F
    g = (v >> 5) & 0x3F
    r = v & 0x1F
    return r, g, b


def test_color_encoding():
    # 用纯红/绿/蓝/白测试编码 + XOR 是否可逆解码
    for color, name in [((255, 0, 0), "红"), ((0, 255, 0), "绿"),
                        ((0, 0, 255), "蓝"), ((255, 255, 255), "白")]:
        img = Image.new("RGB", (DISPLAY_WIDTH, DISPLAY_HEIGHT), color)
        frame = image_to_frame(img)
        arr = np.frombuffer(frame, dtype="<u2").reshape(DISPLAY_HEIGHT, LINE_BYTES // 2)
        # 去掉 XOR,取第一个像素
        un = arr[0, 0] ^ _XOR_PATTERN_U16[0]
        r, g, b = _decode_pixel(int(un))
        exp_r = color[0] >> 3
        exp_g = color[1] >> 2
        exp_b = color[2] >> 3
        assert (r, g, b) == (exp_r, exp_g, exp_b), (name, (r, g, b), (exp_r, exp_g, exp_b))
        print("[ok] %s 色编码正确 -> r=%d g=%d b=%d" % (name, r, g, b))


def test_letterbox():
    # 一个正方形图,缩放到 960x160 后应水平居中、上下贴边、左右留黑
    img = Image.new("RGB", (200, 200), (255, 255, 255))
    out = fit_letterbox(img)
    assert out.size == (DISPLAY_WIDTH, DISPLAY_HEIGHT)
    a = np.asarray(out)
    # 左边缘应为黑
    assert a[:, 0].sum() == 0
    # 中心应为白
    assert a[DISPLAY_HEIGHT // 2, DISPLAY_WIDTH // 2].sum() > 0
    print("[ok] 留黑边缩放正确:正方形 -> 居中 + 左右黑边")


if __name__ == "__main__":
    test_sizes()
    test_xor_pattern()
    test_color_encoding()
    test_letterbox()
    print("\n全部离线自检通过 [PASS]")
