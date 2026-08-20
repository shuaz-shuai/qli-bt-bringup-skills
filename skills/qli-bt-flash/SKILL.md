---
name: qli-bt-flash
description: Flash a QLI build image to a Qualcomm board via PCAT/EDL, including Hamoa two-phase flash
---

# qli-bt-flash

Flash a QLI image to a Qualcomm board using PCAT/EDL or fastboot.

This is Step 4 of the BT bringup flow, after `qli-bt-dts`.

---

## 自动化执行前提

**本 skill 通过 `windows-serial` MCP 的 `exec_cmd` 全自动执行，无需人工干预。**

### 已知设备配置

| 板子 | Alpaca 脚本 | PCAT SN | 备注 |
|------|------------|---------|------|
| IQ-X7181-EVK (Hamoa) | `C:\mcp-serial\alpaca.py` | `5DEE301B` | 两阶段 flash |

### Alpaca 用法

```bash
python C:\mcp-serial\alpaca.py status   # 查电源状态
python C:\mcp-serial\alpaca.py off      # 断电
python C:\mcp-serial\alpaca.py on       # 开机
python C:\mcp-serial\alpaca.py edl      # 进 EDL
python C:\mcp-serial\alpaca.py reboot   # 重启
```

> **注意：** `C:\mcp-serial\alpaca.py` 不接受 port 参数，自动选择已连设备。

### PCAT 路径

```
C:\Program Files (x86)\Qualcomm\PCAT\bin\PCAT.exe
```

枚举设备（获取 SN）：
```bash
"C:\Program Files (x86)\Qualcomm\PCAT\bin\PCAT.exe" -devices
```

> **第一次使用新板子时：** 先枚举确认 SN，然后更新上方已知设备配置表。

---

## 路径自动推断板型

**用户只需提供 build 路径，不需要额外说明板型。** 从 `.qcomflash` 目录名自动推断：

| 目录名关键字 | 板型 | mem_type |
|---|---|---|
| `iq-9075-evk` | RB8 | UFS |
| `iq-8275-evk` | RB4 | UFS |
| `rb3gen2-core-kit` | RB3Gen2 | UFS |
| `iq-x7181-evk` | Hamoa | spinor + UFS（两阶段）|
| `iq-x5121-evk` | Purwa | spinor + UFS（两阶段）|

示例：
- `.../qcom-multimedia-image-iq-9075-evk.rootfs-20260610.qcomflash` → RB8，UFS
- `.../qcom-multimedia-image-iq-x7181-evk.rootfs.qcomflash` → Hamoa，两阶段

---

## Linux → Windows 路径映射

Windows PC 通过网络映射盘直接读 Linux 编译机路径，无需 SCP。

**自动解析顺序：**
1. 读 `configs/<board>.yaml` 的 `flash.windows_drive` 和 `flash.linux_prefix`
2. 如果 config 里有 → 直接转换，不问用户
3. 如果没有 → 问用户确认盘符，然后写入 config 供下次使用

路径转换规则（`/` → `\`，替换前缀）：
```
Linux:   <linux_prefix>/qclinux/QLI0.0/<BOARD>/build/tmp/deploy/images/...
Windows: <windows_drive>:\qclinux\QLI0.0\<BOARD>\build\tmp\deploy\images\...
```

---

## 一、PCAT/EDL Flash（完整镜像）

### 流程

```
Linux 编译机（sh04）
  └─ build 路径: /local/mnt/workspace/<user>/...
       ↓ 路径转换（无需 SCP，Windows 直接读映射盘）
Windows
  └─ 映射路径: Y:\<user>\...
       ↓
  PCAT.exe → EDL → flash → reboot
```

### 前提

Windows 上需要：
- PCAT.exe：`C:\Program Files (x86)\Qualcomm\PCAT\bin\PCAT.exe`
- Alpaca TAC 脚本：`alpaca.py`（通过 TACDev 控制电源）
  - 来源：`<internal-alpaca-repo>`，取 `src/alpaca.py`
  - 支持命令：`list / on / off / edl / hlos / status / cycle`
  - 用法：`python alpaca.py --port <PORT> <cmd>`
  - 获取方式：
    ```bash
    git clone https://<internal-alpaca-repo>.git /tmp/rene --depth=1
    cp /tmp/rene/src/alpaca.py C:\mcp-serial\alpaca.py
    ```
- 网络映射盘已挂载（盘符因人而异，见上方路径映射章节）

验证映射盘：
```bash
cmd.exe /c "for %d in (Y Z T) do (dir %d:\ >nul 2>&1 && echo %d_OK || echo %d_NOT_MOUNTED)"
```

### Step 1 — 确认 build 路径

```bash
ssh <BUILD_SERVER>
ls <WORKSPACE>/build/tmp/deploy/images/<MACHINE>/*.qcomflash
```

QLI build 直接产出 `.qcomflash` 目录，不需要解压。

**Image 选择优先级：**
1. `qcom-multimedia-proprietary-image-*` — 优先使用（含 proprietary 组件）
2. `qcom-multimedia-image-*` — 次选（upstream only）
3. 其他 image（networking、container-orchestration 等）— 不用于 BT bringup

### Step 2 — 进 EDL（off → edl 序列更可靠）

`--port` 是可选的：
- 不指定 → 自动选第一个检测到的 TAC 设备（单板时推荐）
- 多板时指定 port 名（如 `--port VTP21`）避免误操作

```bash
python alpaca.py off
# 等 2-3 秒
python alpaca.py edl

# 多板时指定 port：
# python alpaca.py --port <PORT> off
# python alpaca.py --port <PORT> edl
```

验证 EDL 枚举成功：
```bash
PCAT.exe -devices
# 预期：EDL | <SN>
```

> **WSL2 vs SSH session：** WSL2 里的 `python.exe` 运行在 Windows 进程树中，
> 可以正常枚举 TAC/COM 设备。SSH session 无法访问 USB/COM，`TACDev.GetDeviceCount()` 返回 0。

### Step 3a — 标准刷机（RB8 / RB4 / RB3Gen2 — UFS）

```bash
PCAT.exe -PLUGIN SD -DEVICE <SN> \
  -BUILD "<WIN_BUILD_PATH>" \
  -MEMORYTYPE UFS
```

等待 PCAT 输出 `PASS`。

### Step 3b — Hamoa 两阶段（IQ-X7181-EVK）

详见 `references/hamoa-two-phase.md`。简要流程：

```bash
# Phase 1: spinor — 绝对不加额外参数
PCAT.exe -PLUGIN SD -DEVICE <SN> \
  -BUILD "<WIN_BUILD_PATH>\spinor" \
  -MEMORYTYPE spinor

# Phase 1 完成后板子重启进 HLOS，需再次触发 EDL
python alpaca.py off
python alpaca.py edl

# Phase 2: UFS — 用 .qcomflash 根目录
PCAT.exe -PLUGIN SD -DEVICE <SN> \
  -BUILD "<WIN_BUILD_PATH>" \
  -MEMORYTYPE UFS
```

### Step 4 — 开机

```bash
python alpaca.py on
# 多板时：python alpaca.py --port <PORT> on
```

---

## 二、Fastboot Flash（仅刷 kernel + DTB，速度快）

适合 DTS 调试阶段，只更新 efi.bin + dtb.bin，不刷整个 rootfs。

```bash
# 切到 fastboot
adb -s <serial> reboot bootloader

# 刷
fastboot -s <serial> flash efi  <BUILD_PATH>/efi.bin
fastboot -s <serial> flash dtb_a <BUILD_PATH>/dtb.bin
fastboot -s <serial> reboot

# 等设备起来
adb wait-for-device && adb shell uname -r
```

---

## 三、查找最新 build 路径

```bash
ssh <BUILD_SERVER> \
  "ls -dt <WORKSPACE>/build/tmp/deploy/images/<MACHINE>/*.qcomflash 2>/dev/null | head -1"
```

---

## Pitfalls

**1. PCAT binary 名**
正确是 `PCAT.exe`，不是 `xPCAT.exe`。

**2. Hamoa Phase 1 加了额外参数 → `DEVICE_INVALID_PACKET`**
`-SLOT`、`-SKIPSAHARA`、`-FHINITTIME` 等任何额外参数会触发 `skipSahara=true`，
Sahara 握手失败。Phase 1 只用三个参数：
`-PLUGIN SD -DEVICE <SN> -BUILD <path>\spinor -MEMORYTYPE spinor`。
调试时看 `C:\ProgramData\Qualcomm\PCAT\logs\PCATCli\` 下日志，搜 `"skipSahara"`。

**3. 全新 Hamoa 板 / 刷过 Ubuntu 的板 → `DEVICE_RESPONSE_ERROR`**
UFS 未初始化，需先做 provision（见 `references/hamoa-two-phase.md`）。

**4. PCAT Image Management Service 锁**
上次 PCAT 被强制关闭后报 `Image Management Service has been locked`。
用 PowerShell kill PCAT 进程（不需要重启 QUTS，不需要管理员权限）：
```powershell
Get-Process | Where-Object {$_.Name -like "*PCAT*"} | Stop-Process -Force
```

**5. sh01/sh03 无 Windows 映射**
先 rsync image 到 sh02/sh04/sh05，再刷机。

**6. 直接 edl 有时失败**
推荐 off → edl 序列：
```bash
python alpaca.py --port <PORT> off
python alpaca.py --port <PORT> edl
```

**7. Hamoa Phase 1 完成后不自动进 EDL**
Phase 1 完成后板子重启进 HLOS，Phase 2 前需手动再次触发 EDL。

**8. 网络映射盘未挂载**
PCAT 会报找不到路径。先确认：`cmd.exe /c "dir <WIN_DRIVE>:\ 2>nul || echo NOT_MOUNTED"`

---

## Next step

After successful boot: proceed to `qli-bt-debug` for on-target BT validation.
