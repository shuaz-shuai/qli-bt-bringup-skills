---
name: qli-bt-debug
description: On-target BT validation: dmesg triage, GPIO check, btmon, and trace_printk deep debug
---

# qli-bt-debug

On-target BT validation and deep debug for Qualcomm QLI boards.

This is Step 5 (final) of the BT bringup flow, after `qli-bt-flash`.

---

## 自动化执行前提

**板子通常连在 Windows PC 上，不直接连编译机。访问路径：**

```
Claude → bt-mcp (device_exec / ssh_exec / adb_exec) → WSL2 → SSH/ADB → 板子
```

| 执行方式 | 说明 |
|---|---|
| **有 `bt-mcp`** | Claude 通过 `device_exec` / `ssh_exec` 直接在板子上执行命令，全自动 |
| **无 MCP** | 用户手动通过串口或 SSH 在板子上执行本 skill 的命令 |

有 `bt-mcp` 时，告诉 Claude 设备名（如 `rb4`），Claude 自动执行所有板上命令：

```python
mcp__bt-mcp__device_exec(name="rb4", command="dmesg | grep -i hci_qca")
mcp__bt-mcp__device_exec(name="rb4", command="hciconfig hci0 up")
mcp__bt-mcp__device_exec(name="rb4", command="cat /sys/kernel/debug/gpio | grep -i bt_en")
```

---

## Two paths:

| Path | Interface | Typical chips | Key driver |
|------|-----------|--------------|------------|
| A — UART on-board | UART (hci_qca) | QCA2066, QCA6696/6698 | `hci_qca` |
| B — M.2 Key E | PCIe → serdev UART | QCA2066 M.2, NFA765A | `pwrseq-pcie-m2` + `hci_qca` |

> **Note:** Debug tools (bluez5, libgpiod, pciutils) and kernel config
> (CONFIG_FTRACE etc.) must be added before the first `kas build` — see
> `qli-bt-sync-build` Step 3b. They cannot be added later via fastboot.

---

## Step 1 — dmesg 5-step quick triage

```bash
dmesg | grep -E "geni_serial|ttyHS"          # 1. UART controller probe 了吗？
dmesg | grep -i "wcn.*pmu|pwrseq"            # 2. PMU wrapper bind 了吗？（Pattern B1）
dmesg | grep -i "hci_qca|wcn.*bt|serdev"    # 3. hci_qca attach 到 serdev 了吗？
dmesg | grep -i "qca.*fw|patch.*download"   # 4. FW download OK？
dmesg | grep -i "hci0|bluetooth.*register"  # 5. HCI 设备注册了吗？
```

正常启动序列：
```
geni_serial <addr>: Geni Serial Driver registered
wcnXXXX-pmu: Enabled
hci_qca <ttyHS>: wcnXXXX setup
Bluetooth: hci0: QCA Downloading qca/hpbtfw21.tlv
Bluetooth: hci0: QCA setup on UART is completed
Bluetooth: hci0: HCI device and connection manager registered
```

哪步没有输出，就是那里出了问题。

---

## Step 2 — HCI 接口验证

```bash
hciconfig hci0 up
hciconfig -a           # 期望 hci0 UP RUNNING，显示 BD address
btmon &                # 并行监控 HCI 流量
hcitool scan           # 经典 BT 扫描
hcitool lescan         # BLE 扫描
```

---

## Step 3 — FW 文件检查

```bash
ls /lib/firmware/qca/
dmesg | grep -i "qca.*request\|firmware.*qca"   # 确认 driver 请求的文件名
```

| 芯片 | FW | NVM |
|------|----|-----|
| QCA2066 (Cologne) | `hpbtfw21.tlv` | `hpnv21.bin` |
| QCA6696 (Hamilton) | `crbtfw21.tlv` | `hpnv21.bin` |
| QCA6698 (Hamilton Auto) | `crbtfw21.tlv` | `hpnv21g.bin` |

> PITFALL: NVM `.bin` vs `.g.bin` 选错 — FW 下载成功但 TX power/BD address 异常。

---

## Step 4 — GPIO 验证（BT_EN）

```bash
gpiodetect                              # 列出所有 GPIO chip
cat /sys/kernel/debug/gpio | grep -i "bt.en\|bt_en"

# 手动读/写验证
gpioget <chip> <line>                   # boot 后默认应为 0（output-low）
gpioset <chip> <line>=1                 # 手动拉高
gpioget <chip> <line>                   # 确认读回 1

# hciconfig hci0 up 之后
cat /sys/kernel/debug/gpio | grep -i "bt.en"   # 应显示 output-high
```

> PITFALL: `gpioset` 只在进程存活期间保持电平，退出后恢复默认。长时间保持用 `gpioset --mode=wait`。

---

## Step 5 — Regulator 状态检查（Pattern B1）

```bash
for r in /sys/kernel/debug/regulator/*; do
  name=$(basename $r)
  state=$(cat $r/state 2>/dev/null)
  volt=$(cat $r/voltage 2>/dev/null)
  echo "$name: $state $volt"
done | grep -i "bt\|wcn\|pmu\|rfa\|aon\|wlcx\|wlmx"
```

- `state = disabled` → supply phandle 未配置或解析失败，修 DTS
- `voltage = 0` → regulator enable 失败

---

## Fail Pattern 分析

### Fail pattern 1 — hci_qca 没有 probe，dmesg 完全没有 serdev 相关 log

```bash
ls /dev/ttyHS*                              # 不存在 = UART 没 probe 或 serdev 没创建
dmesg | grep -i "geni_serial|ttyHS"         # 没有 = qupv3 firmware 未加载
dmesg | grep -i "qupv3fw|qup.*firmware"     # 没有 = /lib/firmware/qcom/<soc>/qupv3fw.elf 缺失
grep -n 'aliases\|serial[0-9]' arch/arm64/boot/dts/qcom/<board>.dts
# 没有 serialN = &uartX alias = serdev 不知道用哪个 tty
```

---

### Fail pattern 2 — "Reading QCA version information failed (-110)"

```
hci_uart_qca serial0-0: supply vddXXX not found, using dummy regulator
Bluetooth: hci0: command 0xfc00 tx timeout
Bluetooth: hci0: Reading QCA version information failed (-110)
```

`command 0xfc00` = HCI 上电后第一条命令。timeout = chip 完全没响应 → **chip 没上电**。
`supply dummy` 是次要症状，不是根因。

**排查顺序：**

**Step 1 — DTS 有没有配置 bt_en GPIO（最常见根因）**
```bash
grep -rn 'bt.enable.gpio\|bt_en\|bt-en' \
  arch/arm64/boot/dts/qcom/<board>.dts \
  arch/arm64/boot/dts/qcom/<board>*.dtsi
```
没有 `bt-enable-gpios` → BT_EN 从未拉高 → chip 没上电 → 所有 HCI 命令 timeout。

**Step 2 — PMU wrapper 有没有 probe（Pattern B1）**
```bash
dmesg | grep -i "wcn.*pmu|pmu.*wcn|pwrseq"
# 没有 = PMU wrapper 节点缺失或 compatible 不对 → BT_EN 没人控制
```

**Step 3 — libgpiod 验证 BT_EN 实际电平**
```bash
cat /sys/kernel/debug/gpio | grep -i "bt.en\|bt_en"
gpioget <chip> <line>    # 返回 0 = 低（正常初始状态）；返回 1 = 已拉高（时序错误）
```

**Step 4 — btmon 确认有无 HCI response**
```bash
btmon &
hciconfig hci0 up
# 正常：能看到 HCI Reset command + response event
# 异常：只有 command，没有任何 event = chip 完全没响应
```

---

### Fail pattern 3 — FW 文件缺失

```
Bluetooth: hci0: QCA Downloading qca/hpbtfw21.tlv
Bluetooth: hci0: QCA Failed to request file: qca/hpbtfw21.tlv (-2)
```

```bash
ls /lib/firmware/qca/
dmesg | grep -i "request.*file\|firmware.*qca"   # 确认 driver 请求的确切文件名
```

文件名必须完全匹配（大小写）。文件存在但报错 → driver 里 `soc_type` 写错，
见 `qli-bt-driver-enablement` skill。

---

### Fail pattern 4 — "QCA Downloading ... tx timeout"（FW 下载阶段 timeout）

```
Bluetooth: hci0: QCA Downloading qca/hpbtfw21.tlv
Bluetooth: hci0: command 0xfc01 tx timeout
```

能读到 SOC/ROM version = HCI 基本通信 OK，chip 已上电。
FW 下载阶段 timeout = chip 不响应 FW 命令 → **最常见根因：chip 进入 EDL mode**。

EDL mode 由 chip 的 bootstrap pin 决定，与 DTS/kernel 无关：
- bootstrap pin 拉错电平 → chip 进 EDL → UART 仍工作但 FW 命令不响应
- **必须找硬件确认 schematic 上 bootstrap pin 的实际接法**

排查 UART flow control（次要原因）：
```bash
grep -rn 'qup_uart.*default' arch/arm64/boot/dts/qcom/<board>*.dtsi
# pins 必须有 4 个（TX/RX/CTS/RTS），2-pin 大数据传输时会丢数据
```

---

## 常见错误速查表

| 症状 | 根因 | 修法 |
|------|------|------|
| `supply vddXXX not found, using dummy regulator` + `command 0xfc00 tx timeout` | BT_EN GPIO 未配置，chip 没上电（dummy 是次要症状） | 加 `bt-enable-gpios`；检查 PMU wrapper |
| `hci_qca: wcnXXXX setup failed` | BT_EN GPIO 极性错或 supply 未上电 | 检查 GPIO 极性；libgpiod 验证 |
| FW 下载 `tx timeout` | chip 进 EDL mode（bootstrap pin 接法错） | 找硬件确认 schematic |
| `QCA: Failed to download patch` | FW 文件缺失或文件名不对 | `ls /lib/firmware/qca/` |
| `hci0` up 但扫描为空 | FW 下载后 BT_EN 被拉低 | 检查 `hci_qca` power-down 逻辑 |
| M.2: `lspci` 有设备但无 serdev | `pwrseq-pcie-m2` 未 bind 或 DTS 节点缺失 | 检查 `compatible`；检查 `CONFIG_PWRSEQ_PCIE_M2` |
| M.2: PCIe 设备未枚举 | W_DISABLE# GPIO 被拉低 | 驱动 W_DISABLE# 为高（active-low）|

---

## 深度调试 — trace_printk

### Path A — UART trace（qcom_geni_serial.c，8 处插入）

当 dmesg 看不出卡在哪步时，在 `qcom_geni_serial.c` 加 trace 覆盖完整 UART 通信流程。

**读取 trace log 前的必要步骤（缺一不可）：**

```bash
# 1. 确认 debugfs 已挂载
mount -t debugfs debugfs /sys/kernel/debug   # 目录不存在时执行

# 2. 开启 tracing（默认为 0，不开不记录，开机前的 log 已丢失）
cat /sys/kernel/debug/tracing/tracing_on
echo 1 > /sys/kernel/debug/tracing/tracing_on

# 3. 确认 kernel 编入 ftrace
zcat /proc/config.gz | grep -E "CONFIG_FTRACE|CONFIG_FUNCTION_TRACER|CONFIG_DYNAMIC_FTRACE"
# 三个都需要 =y

# 4. 清空旧 buffer
echo > /sys/kernel/debug/tracing/trace

# 5. 触发 BT 上电
hciconfig hci0 up

# 6. 读 log
cat /sys/kernel/debug/tracing/trace | grep "BT "
cat /sys/kernel/debug/tracing/trace_pipe | grep "BT "   # 实时
```

**8 处插入点（物理地址过滤，只打目标 UART）：**

```c
/* 顶部加宏（以 IQ10 uart17 为例，其他板子改物理地址）*/
#define BT_UART_PHYS 0x0088c000UL   /* 从 .dtsi serial@XXXXXXXX 确认 */

/* 1. startup — hci_qca open ttyHS */
/* 2. shutdown — hci_qca close ttyHS */
/* 3. set_termios — baud rate 切换（115200 → 3Mbps） */
/* 4. start_tx_dma — TX 开始发送 */
/* 5. ISR 入口 — 每次中断 */
/* 6. DMA TX done */
/* 7. DMA RX done — chip 有数据回来，最关键 */
/* 8. 加 trace.h include */
```

完整脚本通过 scp+Python 远程修改（见 `references/remote-ops.md`）。

**trace log 解读：**

| 出现的 log | 结论 |
|---|---|
| `BT STARTUP` | hci_qca 成功 open ttyHS，serdev OK |
| `BT SET_TERMIOS baud=115200` | 初始波特率 OK |
| `BT SET_TERMIOS baud=3000000` | baud rate 切换 OK |
| `BT TX start` + `BT TX DMA DONE` | TX 成功发出并完成 |
| `BT TX start`，无 `BT TX DMA DONE` | TX 卡住，DMA 问题 |
| `BT TX DMA DONE`，无 `BT RX DMA DONE` | TX 发出但 chip 没回复 → 硬件/EDL 问题 |
| `BT RX DMA DONE` | chip 有数据回来，UART 通信 OK |
| 无 `BT STARTUP` | serdev 未 attach，DTS/alias 问题 |

---

### Path B — M.2 trace（pwrseq-pcie-m2.c）

```bash
dmesg | grep -i "pcie|qcom-pcie"          # 1. PCIe RC up？
lspci | grep -i "qualcomm|qca"            # 2. M.2 枚举了吗？（Cologne PCI ID: 17cb:1103）
dmesg | grep -i "pwrseq.*m2|m2.*pwrseq"  # 3. pwrseq-pcie-m2 bind 了吗？
dmesg | grep -i "serdev|ttyHS"            # 4. serdev 动态创建了吗？
dmesg | grep -i "hci_qca|qca.*fw|hci0"   # 5. hci_qca + FW + 注册？
```

卡住时在 `pwrseq-pcie-m2.c` 加 trace，覆盖 probe/上电/serdev 创建全流程。
完整 13 处插入脚本见 `scripts/patch_pwrseq_m2.py`。

**trace log 解读：**

| 出现的 log | 结论 |
|---|---|
| 无 `PWRSEQ_M2 PROBE` | compatible 不匹配或 driver 未编进 kernel |
| `POWER_ON start`，无后续 | power on 卡在某步 regulator/GPIO |
| `VDD enable: ret=0` | 3V3 上电 OK |
| `VDD enable: ret=-ENODEV` | regulator phandle 解析失败，修 DTS |
| `BT_EN set high` | chip 上电信号已发出 |
| `W_DISABLE val=0` | W_DISABLE# 被拉低，module disabled → 修 GPIO 极性 |
| `SERDEV register` | serdev 动态创建 OK |
| 无 `SERDEV register` | power on 成功但 serdev 注册失败 |

---

## See also

- `references/remote-ops.md` — SSH 安全规则 + scp+Python 远程改文件
- `scripts/patch_pwrseq_m2.py` — pwrseq-pcie-m2.c 的 13 处 trace_printk 注入脚本
