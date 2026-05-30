"""测试 MIDI 连接与 Push 2 背光亮度 sysex。"""
import sys, time
for s in (sys.stdout, sys.stderr):
    try: s.reconfigure(encoding="utf-8", errors="replace")
    except Exception: pass

import mido

print("MIDI 后端:", mido.backend)
print("\n所有 MIDI 输出端口:")
outs = mido.get_output_names()
for n in outs:
    print("  -", n)

# 找到 Push 2 的端口(优先 Live 口,即不含 MIDIIN2/MIDIOUT2 的那个)
push_ports = [n for n in outs if "push 2" in n.lower()]
print("\nPush 2 输出端口:", push_ports)
if not push_ports:
    print("[失败] 没找到 Push 2 MIDI 输出端口。")
    sys.exit(1)

# 选择主(Live)口:名字里不含 MIDIOUT2 的
live = [n for n in push_ports if "midiout2" not in n.lower()]
target = (live or push_ports)[0]
print("使用端口:", target)


def brightness_sysex(value):
    value = max(0, min(255, int(value)))
    lsb = value & 0x7F
    msb = (value >> 7) & 0x01
    # mido Message sysex 的 data 不含 F0/F7
    return mido.Message("sysex", data=[0x00, 0x21, 0x1D, 0x01, 0x01, 0x08, lsb, msb])


with mido.open_output(target) as port:
    print("\n依次设置背光:255 -> 30 -> 128,每个停 1.5 秒,请观察屏幕亮度变化…")
    for v in (255, 30, 128):
        port.send(brightness_sysex(v))
        print("  已发送亮度 =", v)
        time.sleep(1.5)
print("完成。请告诉我屏幕背光亮度有没有跟着变化。")
