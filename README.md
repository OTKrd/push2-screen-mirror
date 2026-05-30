# Push 2 Screen Mirror

把电脑屏幕上的**自定义区域**实时投屏到 **Ableton Push 2** 的屏幕(960×160)上，
**无需启动 Ableton Live 或任何 DAW**。

通过 USB 直接驱动 Push 2 的显示屏，实现细节完全依据
[Ableton 官方协议文档](https://github.com/Ableton/push-interface)。

---

## 工作原理

```
屏幕区域截取(bettercam/mss) → 按 6:1 缩放并留黑边 → 转 BGR565 + XOR → USB 推送给 Push 2
```

- 屏幕分辨率：960 × 160，16 位色（BGR565）
- 每帧：16 字节帧头 + 327680 字节像素数据,**帧头与像素数据必须分两次 bulk 传输**
  (端点 `0x01`;合并成一次会导致背光亮但无图像)
- 采集优先用 **bettercam(Windows Desktop Duplication API)**,比 mss 快 3 倍以上、更省 CPU,
  不可用/跨屏时自动回退 mss
- 双线程流水线(采集 + 发送并行)+ 高精度定时器,实测 **~48 FPS**(上限受 USB 发送约束)

---

## 1. 安装依赖

需要 **Python 3.9+**。

```powershell
cd C:\Users\xurendi\projects\push2-screen-mirror
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

> `libusb-package` 已经内置了 libusb 的 DLL，所以**通常不用单独安装 libusb**。

---

## 2. 配置 Windows 驱动（关键一步）

在 Windows 上，程序要通过 USB 访问 Push 2 屏幕，需要一个 libusb 可访问的驱动。
**先什么都别装，直接跑一次检测**——有时 Ableton 装好后系统里已经有可用驱动：

```powershell
py main.py check
```

- 显示 **`[就绪]`** → 跳过本节，直接看第 3 步。
- 显示 **`[未就绪]`** → 按下面任选一种方案配置驱动。

### 方案 A：UsbDk（推荐，最不具侵入性）

UsbDk 是一个**系统级**的一次性安装，**不会替换 Push 2 原本的驱动，也不影响
Ableton Live 继续正常使用 Push 2**，随时可在「添加或删除程序」里卸载还原。

1. 到 [UsbDk Releases](https://github.com/daynix/UsbDk/releases) 下载并安装最新的
   `UsbDk_*.msi`。
2. 安装后重新插拔一次 Push 2，再次运行 `py main.py check` 确认就绪。

### 方案 B：Zadig + WinUSB（较具侵入性）

> ⚠️ 这种方式会**接管 Push 2「Display」接口的驱动**，可能导致 Ableton Live
> 暂时无法驱动 Push 2 屏幕。需要恢复时，在设备管理器里卸载该设备并重新插拔，
> 让 Windows 装回原驱动即可。

1. 下载 [Zadig](https://zadig.akeo.ie/)，连接 Push 2 后打开。
2. 菜单 `Options → List All Devices`。
3. 在下拉列表里选择 **`Ableton Push 2 (Interface 0)`** 或名称含
   **`Display`** 的那一项（**不要**选 MIDI 接口）。
4. 右侧驱动选择 **`WinUSB`**，点击 **Replace Driver**。
5. 完成后运行 `py main.py check` 确认就绪。

---

## 3. 选择要投屏的区域

```powershell
py main.py select
```

会弹出一个覆盖主显示器的半透明遮罩：

- **拖拽**：框选一个区域
- **拖动矩形内部**：移动
- **拖动边 / 角**：调整大小
- **Enter / 双击**：确认并保存
- **Esc**：取消

界面会实时显示选区的尺寸与宽高比（目标是 6:1，越接近黑边越少）。
选区会保存在 `~/.push2_mirror/region.json`，下次直接复用。

> 多显示器：框选界面会覆盖**整个虚拟桌面(所有显示器)**,可以跨屏框选,
> 也能在副屏(含负坐标的显示器)上选区。程序已声明「每显示器 DPI 感知」,
> 在不同缩放比例的多屏环境下,框选与抓取使用一致的物理像素坐标。

---

## 4. 开始投屏

```powershell
py main.py run                 # 用已保存的区域
py main.py run --select        # 先框选再投屏
py main.py run --fps 24        # 指定帧率
py main.py run --region 0,0,1920,320
```

按 **Ctrl+C** 停止，程序会自动把 Push 2 屏幕清黑。

---

## 命令速查

| 命令 | 说明 |
| --- | --- |
| `py main.py check` | 检测 Push 2 连接 / 驱动是否就绪 |
| `py main.py select` | 框选并保存区域 |
| `py main.py run` | 开始投屏（默认用已保存区域） |

---

## 常见问题

- **找不到设备 / 无法打开接口**：确认 Push 2 已开机、**Ableton Live 已完全关闭**
  （Live 会独占 USB 接口），并完成第 2 步的驱动配置。
- **画面有黑边**：这是「保持比例」模式的正常表现。Push 2 屏是 6:1 的超宽屏，
  框选区域越接近 6:1，黑边越少。
- **帧率**:实测可稳定在 ~48 FPS。关键优化:① 采集用 bettercam(DDA),比 mss
  快 3 倍、更省 CPU;② 双线程流水线让采集与发送并行;③ Windows 高精度定时器让
  帧率节流精确。`--fps` 设置目标帧率(默认 60,实际上限受 USB 发送约束约 49)。
  注意:帧头与像素数据**必须分两次 USB 传输**,合并虽然更快但会导致屏幕背光亮
  却无图像,因此不能合并。
- **采集后端**:启动日志会显示「采集后端: bettercam / mss」。若显示 mss,说明
  bettercam 未成功加载(或区域跨显示器),功能不受影响,只是 CPU 占用略高。
- **想恢复 Live 使用 Push 2**：若用过 Zadig，按第 2 步方案 B 的恢复说明操作；
  UsbDk 方案则无需任何恢复。

---

## 安全说明

本工具只发送官方文档中**公开的显示帧头**，不触碰任何保留/诊断/固件刷写指令。
请勿修改 `push2_mirror/display.py` 中的 `FRAME_HEADER`，错误的帧头理论上可能
损坏设备。
