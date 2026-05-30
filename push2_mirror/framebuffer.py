"""图像 -> Push 2 帧缓冲(BGR565 + XOR)的转换。

使用 numpy 做向量化运算,保证足够的帧率。
"""

import numpy as np
from PIL import Image

from .display import DISPLAY_HEIGHT, DISPLAY_WIDTH, FRAME_BYTES, LINE_BYTES

# 每行 uint16 数量:2048 字节 / 2 = 1024(前 960 为像素,后 64 为填充)
_LINE_U16 = LINE_BYTES // 2  # 1024

# XOR 模式 0xFFE7F3E7,字节序为 E7 F3 E7 FF。
# 以 uint16 小端来看,每两个 uint16 循环一次:[0xF3E7, 0xFFE7]。
_XOR_PATTERN_U16 = np.tile(
    np.array([0xF3E7, 0xFFE7], dtype=np.uint16), _LINE_U16 // 2
)  # 形状 (1024,)


def image_to_frame(img):
    """把一张 960x160 的 RGB ``PIL.Image`` 转成 327680 字节的帧缓冲。

    返回的 ``bytes`` 已经完成 BGR565 编码与 XOR,可直接交给
    :meth:`Push2Display.send_frame`。
    """
    if img.mode != "RGB":
        img = img.convert("RGB")
    if img.size != (DISPLAY_WIDTH, DISPLAY_HEIGHT):
        raise ValueError(
            "图像尺寸必须为 %dx%d,实际为 %r"
            % (DISPLAY_WIDTH, DISPLAY_HEIGHT, img.size)
        )

    arr = np.asarray(img, dtype=np.uint16)  # (160, 960, 3)
    r = arr[:, :, 0]
    g = arr[:, :, 1]
    b = arr[:, :, 2]

    # BGR565: bbbbb gggggg rrrrr
    pixels = ((b >> 3) << 11) | ((g >> 2) << 5) | (r >> 3)  # (160, 960) uint16

    line = np.zeros((DISPLAY_HEIGHT, _LINE_U16), dtype=np.uint16)
    line[:, :DISPLAY_WIDTH] = pixels
    line ^= _XOR_PATTERN_U16  # 广播到每一行

    # 强制小端字节序后转 bytes
    return line.astype("<u2").tobytes()


def black_frame_bytes():
    """返回一帧全黑画面对应的字节缓冲(已应用 XOR)。"""
    line = np.zeros((DISPLAY_HEIGHT, _LINE_U16), dtype=np.uint16)
    line ^= _XOR_PATTERN_U16
    data = line.astype("<u2").tobytes()
    assert len(data) == FRAME_BYTES
    return data


def fit_letterbox(img, target_w=DISPLAY_WIDTH, target_h=DISPLAY_HEIGHT,
                  background=(0, 0, 0), resample=Image.BILINEAR):
    """保持纵横比缩放并居中,空白处填充背景色(留黑边)。"""
    if img.mode != "RGB":
        img = img.convert("RGB")
    w, h = img.size
    if w == 0 or h == 0:
        return Image.new("RGB", (target_w, target_h), background)
    scale = min(target_w / w, target_h / h)
    new_w = max(1, int(round(w * scale)))
    new_h = max(1, int(round(h * scale)))
    resized = img.resize((new_w, new_h), resample)
    canvas = Image.new("RGB", (target_w, target_h), background)
    canvas.paste(resized, ((target_w - new_w) // 2, (target_h - new_h) // 2))
    return canvas


def stretch_fill(img, target_w=DISPLAY_WIDTH, target_h=DISPLAY_HEIGHT,
                 resample=Image.BILINEAR):
    """直接拉伸到目标尺寸(填满,可能变形)。"""
    if img.mode != "RGB":
        img = img.convert("RGB")
    return img.resize((target_w, target_h), resample)


def crop_fill(img, target_w=DISPLAY_WIDTH, target_h=DISPLAY_HEIGHT,
              resample=Image.BILINEAR):
    """保持纵横比缩放到覆盖目标,再居中裁剪(填满,不变形,会切边)。"""
    if img.mode != "RGB":
        img = img.convert("RGB")
    w, h = img.size
    if w == 0 or h == 0:
        return Image.new("RGB", (target_w, target_h), (0, 0, 0))
    scale = max(target_w / w, target_h / h)
    new_w = max(target_w, int(round(w * scale)))
    new_h = max(target_h, int(round(h * scale)))
    resized = img.resize((new_w, new_h), resample)
    x = (new_w - target_w) // 2
    y = (new_h - target_h) // 2
    return resized.crop((x, y, x + target_w, y + target_h))


def scale_image(img, mode="fit"):
    """按指定模式把图像缩放到 960x160。mode: fit|stretch|crop。"""
    if mode == "stretch":
        return stretch_fill(img)
    if mode == "crop":
        return crop_fill(img)
    return fit_letterbox(img)


def rotate_image(img, degrees):
    """按顺时针角度旋转图像(0/90/180/270)。用于把竖向画面转成横向。"""
    d = int(degrees) % 360
    if d == 0:
        return img
    if d == 90:
        return img.transpose(Image.Transpose.ROTATE_270)  # 顺时针 90°
    if d == 180:
        return img.transpose(Image.Transpose.ROTATE_180)
    if d == 270:
        return img.transpose(Image.Transpose.ROTATE_90)   # 顺时针 270°(=逆时针 90°)
    return img
