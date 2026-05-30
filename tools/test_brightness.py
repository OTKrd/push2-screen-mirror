"""组合测试:持续显示白屏的同时循环改背光亮度,直观验证亮度控制。"""
import sys, threading, time
for s in (sys.stdout, sys.stderr):
    try: s.reconfigure(encoding="utf-8", errors="replace")
    except Exception: pass

import mido
from PIL import Image
from push2_mirror.display import Push2Display
from push2_mirror.framebuffer import image_to_frame

white = image_to_frame(Image.new("RGB", (960, 160), (255, 255, 255)))

def bright_msg(v):
    v = max(0, min(255, int(v)))
    return mido.Message("sysex", data=[0x00, 0x21, 0x1D, 0x01, 0x01, 0x08, v & 0x7F, (v >> 7) & 0x01])

outs = [n for n in mido.get_output_names() if "push 2" in n.lower() and "midiout2" not in n.lower()]
if not outs:
    outs = [n for n in mido.get_output_names() if "push 2" in n.lower()]
port_name = outs[0]
print("MIDI 端口:", port_name)

disp = Push2Display().open()
stop = threading.Event()

def feed():
    while not stop.is_set():
        disp.send_frame(white)
        time.sleep(1/60)

t = threading.Thread(target=feed, daemon=True); t.start()
time.sleep(0.3)

print("白屏已显示。现在循环改背光亮度,请观察屏幕明暗变化…")
with mido.open_output(port_name) as port:
    for v in (255, 40, 255, 40, 160):
        port.send(bright_msg(v))
        print("  亮度 =", v)
        time.sleep(1.5)
    port.send(bright_msg(255))  # 恢复最亮

stop.set(); t.join(timeout=1)
disp.clear(); disp.close()
print("完成。屏幕明暗有没有跟着变化?")
