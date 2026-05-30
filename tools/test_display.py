"""真机端到端测试:向 Push 2 屏幕推送一张测试图,持续约 3 秒后清屏。"""

import sys
import time

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

from PIL import Image, ImageDraw

from push2_mirror.display import DISPLAY_HEIGHT, DISPLAY_WIDTH, Push2Display
from push2_mirror.framebuffer import image_to_frame


def make_test_image():
    img = Image.new("RGB", (DISPLAY_WIDTH, DISPLAY_HEIGHT), (0, 0, 0))
    draw = ImageDraw.Draw(img)
    colors = [
        (255, 0, 0), (0, 255, 0), (0, 0, 255),
        (255, 255, 0), (0, 255, 255), (255, 0, 255),
        (255, 255, 255), (128, 128, 128),
    ]
    bar_w = DISPLAY_WIDTH // len(colors)
    for i, c in enumerate(colors):
        draw.rectangle([i * bar_w, 0, (i + 1) * bar_w, DISPLAY_HEIGHT], fill=c)
    draw.rectangle([0, 0, DISPLAY_WIDTH - 1, DISPLAY_HEIGHT - 1],
                   outline=(255, 255, 255), width=2)
    draw.text((20, 60), "PUSH 2 OK", fill=(0, 0, 0))
    return img


def main():
    frame = image_to_frame(make_test_image())
    with Push2Display() as d:
        print("已连接,显示测试色条约 3 秒...")
        end = time.time() + 3.0
        while time.time() < end:
            d.send_frame(frame)
            time.sleep(1 / 30)
        print("清屏...")
        d.clear()
    print("测试完成 [PASS]")


if __name__ == "__main__":
    main()
