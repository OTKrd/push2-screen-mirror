# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置:GUI 版(无控制台窗口)。

构建:
    pyinstaller push2mirror_gui.spec --noconfirm

产物:dist/Push2Mirror-GUI/Push2Mirror-GUI.exe(连同文件夹可整体拷走)。
"""

from PyInstaller.utils.hooks import collect_all

datas = []
binaries = []
hiddenimports = []

# 需要完整收集数据/二进制/子模块的包:
#  - libusb_package: 内置 libusb DLL(访问 Push 2 显示接口)
#  - bettercam/comtypes: 高效屏幕采集
#  - customtkinter: 主题与资源文件
#  - pystray: 系统托盘
#  - mido / rtmidi: MIDI 背光控制
for pkg in ("libusb_package", "bettercam", "comtypes", "customtkinter",
            "pystray", "mido", "rtmidi"):
    try:
        d, b, h = collect_all(pkg)
        datas += d
        binaries += b
        hiddenimports += h
    except Exception:
        pass

hiddenimports += [
    "usb.backend.libusb1",
    "usb.backend.libusb0",
    "usb.backend.openusb",
    "numpy",
    "PIL",
    "PIL.Image",
    "PIL.ImageDraw",
    "mss",
    "mss.windows",
    "bettercam",
    "comtypes",
    "customtkinter",
    "darkdetect",
    "pystray",
    "pystray._win32",
    "mido",
    "mido.backends.rtmidi",
    "rtmidi",
]


a = Analysis(
    ["gui_main.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Push2Mirror-GUI",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,  # GUI:不弹命令行窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="Push2Mirror-GUI",
)
