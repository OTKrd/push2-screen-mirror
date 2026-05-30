"""通过 MIDI sysex 控制 Push 2 的显示背光亮度。

依据官方协议(Set Display Brightness, sysex ID 0x08):
    F0 00 21 1D 01 01 08 <LSB> <MSB> F7
其中亮度 0..255,LSB=低 7 位,MSB=高 1 位。

注意:Push 2 仅靠 USB 供电(未接电源适配器)时,背光最大亮度会被硬件限制。
"""

# Ableton sysex 前缀(不含 F0/F7,mido 的 data 字段不含首尾字节)
_SYSEX_PREFIX = [0x00, 0x21, 0x1D, 0x01, 0x01]
_SET_DISPLAY_BRIGHTNESS = 0x08


class Push2MidiError(Exception):
    pass


def _brightness_data(value):
    value = max(0, min(255, int(value)))
    return _SYSEX_PREFIX + [_SET_DISPLAY_BRIGHTNESS, value & 0x7F, (value >> 7) & 0x01]


def find_push2_output():
    """返回 Push 2 的 MIDI 输出端口名(优先 Live 口),没有则 None。"""
    try:
        import mido
    except Exception:
        return None
    try:
        outs = mido.get_output_names()
    except Exception:
        return None
    push = [n for n in outs if "push 2" in n.lower()]
    if not push:
        return None
    # 优先不含 MIDIOUT2 的(Live 口)
    live = [n for n in push if "midiout2" not in n.lower()]
    return (live or push)[0]


class Push2Midi:
    """设置 Push 2 显示背光亮度。

    采用「用时才开、发完即关」策略:平时不占用 Push 2 的 MIDI 输出端口,
    这样不投屏时其它 DAW 仍可正常使用 Push 2 的控制面板(pad/旋钮/按钮)。
    """

    def __init__(self):
        self._port_name = None  # 仅缓存端口名,避免每次重新枚举

    @property
    def available(self):
        return find_push2_output() is not None

    def open(self):
        """仅解析并缓存端口名,不长期占用端口。"""
        self._port_name = find_push2_output()
        if self._port_name is None:
            raise Push2MidiError("未找到 Push 2 的 MIDI 输出端口")
        return self

    def set_brightness(self, value):
        """设置显示背光亮度(0..255):打开端口 -> 发送 -> 立即关闭。"""
        import mido

        name = self._port_name or find_push2_output()
        if name is None:
            raise Push2MidiError("未找到 Push 2 的 MIDI 输出端口")
        self._port_name = name
        msg = mido.Message("sysex", data=_brightness_data(value))
        try:
            with mido.open_output(name) as port:
                port.send(msg)
        except Exception as exc:  # noqa: BLE001
            self._port_name = None  # 端口名可能已失效,下次重新查找
            raise Push2MidiError("发送亮度指令失败:%s" % exc) from exc

    def close(self):
        self._port_name = None
