# Push 2 Screen Mirror

**[中文版说明 (Chinese)](#中文说明)**

Mirror a custom region of your computer screen onto the **Ableton Push 2** display (960×160) in real time — **no DAW required**.

Drives the Push 2 display directly over USB, following the official [Ableton Push 2 Interface Specification](https://github.com/Ableton/push-interface).

---

## Features

- **GUI application** — modern dark UI (customtkinter), no command-line needed
- **Region selection** — drag-to-select overlay spanning all monitors; move, resize, lock aspect ratio
- **~48 FPS** — dual-thread pipeline (capture + send in parallel), high-resolution timer
- **Fast capture** — [bettercam](https://github.com/RootKit-Org/BetterCam) (Desktop Duplication API) with automatic fallback to mss
- **Scale modes** — fit (letterbox), stretch, or crop-to-fill
- **Rotation** — 0° / 90° CW / 180° / 90° CCW; select vertically, display horizontally
- **Backlight control** — brightness slider via MIDI sysex; only briefly opens the MIDI port while adjusting, never locks it out from your DAW
- **System tray** — close window to minimize; right-click tray icon to start/stop/show/quit
- **Single instance** — launching again brings the existing window to front
- **Portable** — PyInstaller-packaged standalone exe, no Python installation needed on target machine
- **DAW-friendly** — does not occupy Push 2 MIDI ports when idle; pads/knobs/buttons remain fully usable by your DAW

---

## How It Works

```
Screen capture (bettercam/mss) → Scale/Rotate → BGR565 + XOR → USB bulk transfer → Push 2 display
```

- Display: 960 × 160 px, 16-bit color (BGR565)
- Each frame: 16-byte header + 327,680 bytes pixel data, sent as **two separate bulk transfers** on endpoint `0x01`
- Capture prefers bettercam (DDA, ~3× faster than mss); falls back to mss when unavailable or when the region spans multiple monitors

---

## Quick Start (GUI)

### Pre-built executable (recommended)

1. Download the `Push2Mirror-GUI` folder from [Releases](https://github.com/OTKrd/push2-screen-mirror/releases) (or build it yourself, see below).
2. Close **Ableton Live** (or any software using Push 2).
3. Connect Push 2 via USB and power it on.
4. Double-click **`Push2Mirror-GUI.exe`**.
5. Click **Select Region** → drag to select → press **Enter**.
6. Click **▶ Start**.

### From source

Requires **Python 3.9+** on Windows.

```powershell
git clone https://github.com/OTKrd/push2-screen-mirror.git
cd push2-screen-mirror
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
py gui_main.py
```

---

## Windows USB Driver

The program accesses the Push 2 display via libusb. In many cases it works out of the box (especially if Ableton Live has been installed). If the GUI shows "Push 2 not connected":

### Option A: UsbDk (recommended, non-invasive)

Install [UsbDk](https://github.com/daynix/UsbDk/releases). It does **not** replace the Push 2 driver and does **not** affect Ableton Live. Can be uninstalled at any time.

### Option B: Zadig + WinUSB (invasive)

> ⚠️ This replaces the driver for the Push 2 Display interface. Ableton Live may not be able to drive the display until you revert. To revert: uninstall the device in Device Manager and re-plug Push 2.

1. Download [Zadig](https://zadig.akeo.ie/), open it with Push 2 connected.
2. `Options → List All Devices`.
3. Select **`Ableton Push 2 (Interface 0)`** or the entry containing **`Display`** — do **not** select the MIDI interface.
4. Choose **`WinUSB`** on the right, click **Replace Driver**.

---

## GUI Controls

| Control | Description |
| --- | --- |
| **Status dot** | Green = Push 2 connected and ready; Red = not connected |
| **Select Region** | Opens a transparent overlay across all monitors. Drag to select, drag inside to move, drag edges/corners to resize. Press **R** to reset to target ratio, **L** to lock/unlock ratio, **Enter** to confirm, **Esc** to cancel. |
| **Scale mode** | Fit (letterbox) / Stretch / Crop-to-fill |
| **Rotation** | None / CW 90° / 180° / CCW 90°. With 90°/270°, the selection target becomes 1:6 (vertical select → horizontal display). |
| **Backlight brightness** | Slider 0–255. Sent via MIDI sysex; port is only opened momentarily. Note: USB-powered Push 2 (no external PSU) is hardware-limited to ~7% max brightness. |
| **Auto-start** | When checked, mirroring starts automatically on next launch using the last saved region. |
| **Start / Stop** | Toggle mirroring. |
| **Close window** | Minimizes to system tray. Right-click the tray icon for Start / Stop / Show / Quit. |

---

## Building the Executable

```powershell
.\.venv\Scripts\Activate.ps1
pip install pyinstaller
pyinstaller push2mirror_gui.spec --noconfirm
```

Output: `dist/Push2Mirror-GUI/` — the entire folder is portable.

---

## DAW Coexistence

| State | MIDI ports (pads/knobs/LEDs) | Display |
| --- | --- | --- |
| GUI open, not mirroring | ✅ Not occupied | ✅ Not occupied |
| Dragging brightness slider | Briefly opens MIDI output, releases immediately | — |
| Mirroring | ✅ Not occupied | Occupied (DAW cannot drive the display) |
| Quit (tray → Quit) | ✅ All released | ✅ All released |

---

## Safety

This tool only sends the **officially documented display frame header**. It does not touch any reserved, diagnostic, or firmware-flashing commands. Do not modify `FRAME_HEADER` in `push2_mirror/display.py` — an incorrect header could theoretically brick the device.

---

## License

MIT

---

---

# 中文说明

把电脑屏幕上的**自定义区域**实时投屏到 **Ableton Push 2** 的屏幕(960×160)上,**无需启动 Ableton Live 或任何 DAW**。

通过 USB 直接驱动 Push 2 的显示屏,实现细节完全依据 [Ableton 官方协议文档](https://github.com/Ableton/push-interface)。

---

## 功能特性

- **图形界面** — 现代深色 UI(customtkinter),无需命令行
- **区域框选** — 半透明遮罩覆盖所有显示器;可移动、缩放、锁定宽高比
- **~48 FPS** — 双线程流水线(采集 + 发送并行)+ 高精度定时器
- **高效采集** — 优先使用 bettercam(Desktop Duplication API),不可用时自动回退 mss
- **缩放方式** — 留黑边 / 拉满 / 裁剪填满
- **旋转** — 0° / 顺时针 90° / 180° / 逆时针 90°;可竖向框选、横向显示
- **背光亮度** — 通过 MIDI sysex 调节;仅在拖动滑块时短暂占用 MIDI 端口,不影响 DAW
- **系统托盘** — 关闭窗口即最小化到托盘;右键托盘图标可 开始/停止/显示/退出
- **单实例保护** — 重复启动时唤醒已有窗口,不会开多个
- **免安装** — PyInstaller 打包为独立 exe,目标机器无需安装 Python
- **与 DAW 共存** — 空闲时不占用 Push 2 MIDI 端口;pad/旋钮/按钮可被 DAW 正常使用

---

## 工作原理

```
屏幕区域截取(bettercam/mss) → 缩放/旋转 → BGR565 + XOR → USB 推送给 Push 2
```

- 屏幕:960 × 160 像素,16 位色(BGR565)
- 每帧:16 字节帧头 + 327,680 字节像素数据,通过端点 `0x01` **分两次 bulk 传输**
- 采集优先使用 bettercam(DDA,比 mss 快约 3 倍);不可用或跨屏时自动回退 mss

---

## 快速开始(GUI)

### 使用预编译 exe(推荐)

1. 从 [Releases](https://github.com/OTKrd/push2-screen-mirror/releases) 下载 `Push2Mirror-GUI` 文件夹(或自行构建)。
2. 关闭 **Ableton Live**(或其他使用 Push 2 的软件)。
3. 通过 USB 连接 Push 2 并开机。
4. 双击 **`Push2Mirror-GUI.exe`**。
5. 点击 **重新框选区域** → 拖拽选区 → 按 **Enter** 确认。
6. 点击 **▶ 开始投屏**。

### 从源码运行

需要 Windows + **Python 3.9+**。

```powershell
git clone https://github.com/OTKrd/push2-screen-mirror.git
cd push2-screen-mirror
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
py gui_main.py
```

---

## Windows USB 驱动配置

程序通过 libusb 访问 Push 2 显示接口。很多情况下无需额外配置(尤其是已安装过 Ableton Live)。若 GUI 显示"Push 2 未连接":

### 方案 A:UsbDk(推荐,无侵入性)

安装 [UsbDk](https://github.com/daynix/UsbDk/releases)。**不会替换** Push 2 原有驱动,**不影响** Ableton Live,可随时卸载。

### 方案 B:Zadig + WinUSB(有侵入性)

> ⚠️ 此方式会**接管** Push 2 Display 接口的驱动,Ableton Live 可能暂时无法驱动屏幕。恢复方法:在设备管理器中卸载该设备并重新插拔 Push 2。

1. 下载 [Zadig](https://zadig.akeo.ie/),连接 Push 2 后打开。
2. `Options → List All Devices`。
3. 选择 **`Ableton Push 2 (Interface 0)`** 或含 **`Display`** 的条目(**不要**选 MIDI 接口)。
4. 右侧选择 **`WinUSB`**,点击 **Replace Driver**。

---

## 界面说明

| 控件 | 说明 |
| --- | --- |
| **状态指示灯** | 绿 = Push 2 已连接就绪;红 = 未连接 |
| **重新框选区域** | 打开覆盖所有显示器的半透明遮罩。拖拽框选,拖动内部移动,拖边/角缩放。按 **R** 恢复目标比例,**L** 锁定/解锁比例,**Enter** 确认,**Esc** 取消。 |
| **缩放方式** | 留黑边 / 拉满 / 裁剪填满 |
| **旋转** | 不旋转 / 顺时针 90° / 180° / 逆时针 90°。选择 90°/270° 后,框选目标变为 1:6(竖向框选 → 横向显示)。 |
| **背光亮度** | 滑块 0–255,通过 MIDI sysex 发送;仅在拖动时短暂占用 MIDI 端口。注意:仅 USB 供电的 Push 2(未接外部电源)最大亮度被硬件限制在约 7%。 |
| **启动时自动投屏** | 勾选后,下次启动自动使用上次区域开始投屏。 |
| **开始 / 停止** | 切换投屏状态。 |
| **关闭窗口** | 最小化到系统托盘。右键托盘图标可 开始/停止/显示/退出。 |

---

## 构建 exe

```powershell
.\.venv\Scripts\Activate.ps1
pip install pyinstaller
pyinstaller push2mirror_gui.spec --noconfirm
```

产物:`dist/Push2Mirror-GUI/`,整个文件夹可直接拷走使用。

---

## 与 DAW 共存

| 状态 | MIDI 端口(pad/旋钮/LED) | 显示屏 |
| --- | --- | --- |
| GUI 开着但未投屏 | ✅ 不占用 | ✅ 不占用 |
| 拖动亮度滑块时 | 短暂打开 MIDI 输出,立即释放 | — |
| 投屏中 | ✅ 不占用 | 占用(DAW 此时无法驱动屏幕) |
| 退出(托盘 → 退出) | ✅ 全部释放 | ✅ 全部释放 |

---

## 安全说明

本工具仅发送官方文档中**公开的显示帧头**,不触碰任何保留/诊断/固件刷写指令。请勿修改 `push2_mirror/display.py` 中的 `FRAME_HEADER`,错误的帧头理论上可能损坏设备。

---

## 许可证

MIT
