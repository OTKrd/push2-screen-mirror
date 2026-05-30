"""Push 2 显示屏的底层 USB 驱动。

实现细节完全依据 Ableton 官方协议文档:
  https://github.com/Ableton/push-interface
  (doc/AbletonPush2MIDIDisplayInterface.asc 第 3 章 Display Interface)

要点:
  - 设备 VID=0x2982 / PID=0x1967,claim interface 0,bulk OUT 端点 0x01
  - 每帧先发 16 字节帧头,再发 327680 字节像素数据
  - 屏幕 160 行 x 960 像素,每行 2048 字节(1920 像素数据 + 128 填充)
  - 像素为 16 位小端 BGR565:bbbbb gggggg rrrrr
  - 发送前整行需与循环模式 0xFFE7F3E7(字节序 E7 F3 E7 FF)做 XOR
"""

import sys

import usb.core
import usb.util

try:
    import libusb_package
    _HAVE_LIBUSB_PACKAGE = True
except ImportError:  # pragma: no cover - 仅在缺少可选依赖时触发
    libusb_package = None
    _HAVE_LIBUSB_PACKAGE = False

ABLETON_VENDOR_ID = 0x2982
PUSH2_PRODUCT_ID = 0x1967
PUSH2_BULK_EP_OUT = 0x01

DISPLAY_WIDTH = 960
DISPLAY_HEIGHT = 160

# 每行 2048 字节 = 1920 字节像素 + 128 字节填充
LINE_BYTES = 2048
FRAME_BYTES = LINE_BYTES * DISPLAY_HEIGHT  # 327680

# 固定的 16 字节帧头(切勿改动,错误的帧头可能触发固件刷写等保留功能)
FRAME_HEADER = bytes(
    [
        0xFF, 0xCC, 0xAA, 0x88,
        0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00,
    ]
)

_WRITE_TIMEOUT_MS = 1000


class Push2DisplayError(Exception):
    """与 Push 2 显示屏通信相关的错误。"""


class Push2Display:
    """管理与 Push 2 显示屏的 USB 连接并推送帧数据。"""

    def __init__(self):
        self._device = None
        self._ep_out = None
        self._reattach_iface = False

    # ------------------------------------------------------------------ #
    # 连接管理
    # ------------------------------------------------------------------ #
    def open(self):
        """查找并打开 Push 2 显示接口。失败时抛出 Push2DisplayError。"""
        device = self._find_device()
        if device is None:
            raise Push2DisplayError(
                "未找到 Ableton Push 2 设备 (VID=0x2982 / PID=0x1967)。\n"
                "请确认:\n"
                "  1) Push 2 已通过 USB 连接并开机;\n"
                "  2) Ableton Live 等会占用设备的程序已关闭;\n"
                "  3) Windows 上已安装可供 libusb 访问的驱动"
                "(推荐 UsbDk,详见 README)。"
            )

        try:
            device.set_configuration()
        except usb.core.USBError as exc:
            # 已经被配置过通常会报错,可忽略;其它错误向上抛出。
            if exc.errno not in (None,) and "configured" not in str(exc).lower():
                raise Push2DisplayError(
                    "无法配置 Push 2 USB 设备:%s\n"
                    "这通常意味着驱动不正确,或设备正被其它程序占用。" % exc
                ) from exc

        cfg = device.get_active_configuration()
        intf = cfg[(0, 0)]

        # Linux 下若有内核驱动占用接口,需要先卸下(Windows 无此概念)。
        try:
            if device.is_kernel_driver_active(intf.bInterfaceNumber):
                device.detach_kernel_driver(intf.bInterfaceNumber)
                self._reattach_iface = True
        except (NotImplementedError, usb.core.USBError):
            pass

        ep_out = usb.util.find_descriptor(
            intf,
            custom_match=lambda e: e.bEndpointAddress == PUSH2_BULK_EP_OUT,
        )
        if ep_out is None:
            raise Push2DisplayError(
                "在 Push 2 接口上未找到 bulk OUT 端点 0x01。"
            )

        self._device = device
        self._ep_out = ep_out
        return self

    def close(self):
        """释放 USB 资源。"""
        if self._device is not None:
            try:
                usb.util.dispose_resources(self._device)
            except usb.core.USBError:
                pass
        self._device = None
        self._ep_out = None

    def __enter__(self):
        return self.open()

    def __exit__(self, exc_type, exc, tb):
        self.close()

    @property
    def is_open(self):
        return self._device is not None and self._ep_out is not None

    # ------------------------------------------------------------------ #
    # 帧发送
    # ------------------------------------------------------------------ #
    def send_frame(self, frame_bytes):
        """发送一整帧。frame_bytes 必须为已完成 XOR 的 327680 字节缓冲。"""
        if not self.is_open:
            raise Push2DisplayError("显示屏尚未打开,请先调用 open()。")
        if len(frame_bytes) != FRAME_BYTES:
            raise Push2DisplayError(
                "帧缓冲大小错误:期望 %d 字节,实际 %d 字节。"
                % (FRAME_BYTES, len(frame_bytes))
            )

        # 重要:帧头必须作为独立的一次 bulk 传输,随后再单独传输像素数据。
        # 不能把两者合并成一次传输 —— 那样虽然 USB 写入会"成功",但 Push 2
        # 无法正确解析(像素数据未对齐到 512 字节包边界),会出现背光亮却无图像。
        ep = self._ep_out
        try:
            ep.write(FRAME_HEADER, _WRITE_TIMEOUT_MS)
            ep.write(frame_bytes, _WRITE_TIMEOUT_MS)
        except usb.core.USBError as exc:
            raise Push2DisplayError("向 Push 2 写入帧数据失败:%s" % exc) from exc

    def clear(self):
        """把屏幕刷为黑色。"""
        self.send_frame(black_frame())

    # ------------------------------------------------------------------ #
    # 内部
    # ------------------------------------------------------------------ #
    @staticmethod
    def _find_device():
        if _HAVE_LIBUSB_PACKAGE:
            return libusb_package.find(
                idVendor=ABLETON_VENDOR_ID, idProduct=PUSH2_PRODUCT_ID
            )
        return usb.core.find(
            idVendor=ABLETON_VENDOR_ID, idProduct=PUSH2_PRODUCT_ID
        )


def black_frame():
    """返回一帧全黑画面(已应用 XOR),用于清屏。"""
    # 延迟导入避免循环依赖。
    from .framebuffer import black_frame_bytes

    return black_frame_bytes()


def list_push2_devices():
    """返回检测到的 Push 2 设备列表(用于诊断)。"""
    finder = libusb_package.find if _HAVE_LIBUSB_PACKAGE else usb.core.find
    return list(
        finder(
            find_all=True,
            idVendor=ABLETON_VENDOR_ID,
            idProduct=PUSH2_PRODUCT_ID,
        )
    )


def backend_info():
    """返回当前 USB 后端来源的描述字符串,便于排错。"""
    if _HAVE_LIBUSB_PACKAGE:
        return "libusb-package(内置 libusb DLL)"
    return "系统 libusb(需自行确保 libusb-1.0 可用)"


if __name__ == "__main__":  # 简单自测
    print("USB 后端:", backend_info())
    devices = list_push2_devices()
    print("检测到 Push 2 设备数量:", len(devices))
    sys.exit(0 if devices else 1)
