---
name: qli-bt-dts
description: Read binding YAML, draft BT DTS node, run dtbs_check, and deploy into Yocto SRC_URI
---

# qli-bt-dts

Draft, verify, and deploy a BT DTS node for a Qualcomm QLI board.

This is Step 3 of the BT bringup flow, after `qli-bt-kernel-prep`.

---

## Config-driven workflow

Before asking the user anything, check these two sources in order:

**1. Check `configs/<board>.yaml`**

If a config file exists for this board, use all values from it directly —
do NOT ask the user for information that's already there.

```bash
ls references/boards/        # check available reference boards
ls configs/                  # check if board config already exists
```

**2. Check `references/boards/<board>.md`**

If a reference board entry exists (same chip, previously bringup'd),
read it first to understand the DTS structure and reusable values.

**Reusable from reference board (same chip):**
- DTS node structure (PMU wrapper layout, supply names, compatible string)
- `max-speed` value
- `vreg_pmu_*` label names

**Must confirm per board — from the SYSIO Excel first, schematic only as fallback:**
- GPIO pin numbers (always board-specific)
- UART instance
- Any supply not coming from PMU wrapper

The board-specific pins above come from the **SYSIO IO-assignment Excel**
(the preferred, structured source — see Step 1). The schematic is only needed
for signals the SYSIO sheet does not carry (typically the 32.768 kHz sleep
clock source and PMIC supplies).

---

## Step 0 — Read the binding YAML first (before looking up any pins)

The binding YAML is authoritative for what properties are required, optional,
or deprecated. Reading it first tells you exactly which pins to look for —
so in Step 1 you only extract the signals you actually need.

```bash
# Find the binding for your chip in the kernel source:
find kernel-source/Documentation/devicetree/bindings/net/bluetooth/ -name "qcom,*.yaml"

# Common bindings:
# qcom,qca2066-bt.yaml    — QCA2066 / Cologne (Pattern B2)
# qcom,wcn3988-bt.yaml    — WCN3988 / WCN7850 (Pattern B1, PMU wrapper)
# qcom,wcn6750-bt.yaml    — WCN6750 / Hamilton M.2 (Pattern C)
```

From the binding, extract a checklist of what you need:

- Required supplies (regulators): note voltage levels and supply names
- `bt-enable-gpios` / `enable-gpios`: note whether a pull-up matters.
  The SYSIO sheet's **Default Pull** column answers this directly in Step 1
  (PD = internal pull-down, no external pull-up → GPIO is effectively required;
  PU = pull-up present). Only ask the user if the sheet is unavailable:
  > "Does the hardware have a pull-up resistor on BT_EN?"
  - If **pull-up present**: gpio property is truly optional, can be omitted
  - If **no pull-up** (PD): treat as **required** regardless of what the
    binding says — omitting it leaves BT_EN floating
- `clocks`: note expected frequency (usually 32.768 kHz LPO)
- UART pinctrl pins: must have 4 pins (TX/RX/CTS/RTS)

---

## Step 1 — Extract pins from the SYSIO Excel (preferred), schematic as fallback

The **SYSIO / IO-assignment Excel** (e.g. `MONACO_SYSIO_v2.3.xlsx`) is the
preferred source. It is already structured — one row per SoC GPIO, with the
board net, the pinmux Function columns, and the Default Pull — so it maps
BT nets straight to GPIO numbers and QUP instances with no schematic reading.

**1a. Ask the user for the SYSIO Excel path** (preferred).
Only if they don't have one, fall back to the schematic (Step 1c).

**1b. Run the parser** to pull the BT pins automatically:

```bash
python3 scripts/parse_sysio.py <path/to/SYSIO.xlsx>
```

It reports, from the binding checklist in Step 0:
- **BT_EN** — GPIO number + Default Pull (PD ⇒ no external pull-up)
- **BT UART** — TX / RX / CTS / RFR(RTS) → GPIO numbers + the QUP instance
  (e.g. `QUP0_SE2`), and the 4-pin pinctrl list

Options: `--all-uart` lists every UART pin; `--dump-row N` prints all columns
of `GPIO[N]` when a signal name doesn't match the default keywords.

Example (Monza / QCS8275, from `MONACO_SYSIO_v2.3.xlsx`):
```
[BT_EN]    GPIO55  default-pull=PD   → bias-pull-down + output-low
[BT UART]  TX GPIO35  RX GPIO36  CTS GPIO33  RFR GPIO34   → QUP0_SE2
```

**1c. Schematic fallback** — only if no SYSIO sheet is available, or to
confirm a signal the sheet doesn't carry. Ask the user for:
1. Schematic file path (PDF or image)
2. BT page number (optional, saves time)

Then look up **only** the required signals from the Step 0 checklist:
- UART instance: BT chip UART_TX/RX/CTS/RTS pins → trace to SoC QUP instance
- BT_EN GPIO: BT_EN / BT_REG_ON signal → tlmm pin number + active polarity
- Regulator supplies: VDD/VDDIO pins → PMIC LDO (only if binding requires them)

**1d. Always confirm from another source (not in the SYSIO GPIO sheet):**
- **32.768 kHz sleep clock**: usually a PMIC output, not a SoC GPIO. Get it
  from the PMIC section of the schematic or from the reference board entry.
- PMIC-fed supplies (Pattern B1 supplies come from the PMU wrapper instead).

Do not read the whole schematic — only what the binding YAML marked required.

---

## Step 2 — Identify the hardware pattern

| Pattern | Chip examples | Distinguishing feature |
|---|---|---|
| B1 | WCN3988, WCN7850 | PMU wrapper node (`wcn-pmu`) in DTS; BT_EN on PMU wrapper; supplies come from PMU LDO outputs |
| B2 | QCA2066, QCA6174 | No PMU wrapper; `enable-gpios` directly on `bluetooth{}` node; `clocks` property required |
| C | QCA6696, QCA6750 (M.2) | PCIe + `pwrseq-pcie-m2`; no static `bluetooth{}` node; serdev created dynamically |

For Pattern C, stop here and see `references/dts-patterns.md` §Pattern C —
the DTS structure is fundamentally different.

---

## Step 3 — Draft the DTS node

### Pattern B2 (QCA2066 / no PMU wrapper)

```dts
/* board.dts */

&tlmm {
    bt_en_default: bt-en-default-state {
        pins = "gpioNN";          /* replace NN with actual pin */
        function = "gpio";
        drive-strength = <2>;
        bias-pull-down;           /* BOTH output-low AND bias-pull-down required */
        output-low;
    };
};

&uartNN {                         /* replace NN with actual UART instance */
    status = "okay";

    bluetooth {
        compatible = "qcom,qca2066-bt";
        clocks = <&CLOCK_SOURCE>;  /* replace with actual 32.768 kHz source */
        enable-gpios = <&tlmm NN GPIO_ACTIVE_HIGH>;  /* replace NN */

        pinctrl-names = "default";
        pinctrl-0 = <&bt_en_default>;
    };
};
```

### Pattern B1 (WCN7850 — PMU wrapper, IQ-X7181-EVK actual example)

For WCN7850 on IQ-X7181-EVK (hamoa-iot-evk.dts), the PMU wrapper node already
exists in the DTS. Only three additions are needed:

**1. Add `bt-enable-gpios` and pinctrl ref to `wcn7850-pmu` node:**
```dts
wcn7850-pmu {
    ...
    wlan-enable-gpios = <&tlmm 117 GPIO_ACTIVE_HIGH>;
    bt-enable-gpios = <&tlmm 116 GPIO_ACTIVE_HIGH>;   /* add this */

    pinctrl-0 = <&wcn_wlan_en>, <&wcn_bt_en>;         /* append wcn_bt_en */
    pinctrl-names = "default";
    ...
};
```

**2. Add `wcn_bt_en` pinctrl state in `&tlmm` block (after wcn_wlan_en):**
```dts
wcn_bt_en: wcn-bt-en-state {
    pins = "gpio116";
    function = "gpio";
    drive-strength = <2>;
    bias-disable;           /* no hardware pull-up on BT_EN */
};
```

**3. Add `bluetooth` child node under `&uart14`:**
```dts
&uart14 {
    status = "okay";

    bluetooth {
        compatible = "qcom,wcn7850-bt";
        max-speed = <3200000>;

        vddaon-supply = <&vreg_pmu_aon_0p59>;
        vddwlcx-supply = <&vreg_pmu_wlcx_0p8>;
        vddwlmx-supply = <&vreg_pmu_wlmx_0p85>;
        vddrfacmn-supply = <&vreg_pmu_rfa_cmn>;
        vddrfa0p8-supply = <&vreg_pmu_rfa_0p8>;
        vddrfa1p2-supply = <&vreg_pmu_rfa_1p2>;
        vddrfa1p8-supply = <&vreg_pmu_rfa_1p8>;
    };
};
```

> **Note:** The regulator labels (`vreg_pmu_*`) come from the `regulators {}`
> block inside `wcn7850-pmu` — no need to add new regulators.

> **Note:** `bt-enable-gpios` is not in the wcn7850-bt binding but is in
> the PMU wrapper (`qcom,wcn7850-pmu`). Check the PMU binding YAML, not the
> BT binding, for GPIO properties.

### UART pinctrl (required for all patterns)

The UART pinctrl **must** have all 4 pins. A 2-pin-only pinctrl is a common
mistake that causes intermittent UART errors under load.

```dts
&tlmm {
    bt_uart_default: bt-uart-default-state {
        pins = "gpioTX", "gpioRX", "gpioCTS", "gpioRTS";  /* all 4 */
        function = "qup<N>_se<M>";  /* from schematic / SoC TRM */
        drive-strength = <2>;
        bias-pull-up;
    };
};
```

---

## Step 4 — Rebuild with cleansstate after DTS changes

After modifying DTS in `kernel-source/`, do NOT run `kas build` directly —
it will hit sstate cache and skip kernel compilation even with externalsrc active.

**Correct two-step procedure:**

```bash
cd <WORKSPACE>
umask 0022

# Step 1: cleansstate kernel only
kas shell meta-qcom/ci/<board>.yml:meta-qcom/ci/qcom-distro.yml:meta-qcom/ci/downloads.yml \
  -c 'bitbake -c cleansstate linux-qcom-next'

# Step 2: full image build (same command as original kas build)
kas build meta-qcom/ci/<board>.yml:meta-qcom/ci/qcom-distro.yml:meta-qcom/ci/downloads.yml
```

For IQ-X7181-EVK specifically:
```bash
kas shell meta-qcom/ci/iq-x7181-evk.yml:meta-qcom/ci/qcom-distro.yml:meta-qcom/ci/downloads.yml \
  -c 'bitbake -c cleansstate linux-qcom-next'

kas build meta-qcom/ci/iq-x7181-evk.yml:meta-qcom/ci/qcom-distro.yml:meta-qcom/ci/downloads.yml
```

Verify the DTB was actually rebuilt (timestamp should match the build time):
```bash
ls -la build/tmp/deploy/images/<MACHINE>/<board>.dtb
```

Then confirm the change is in the DTB:
```bash
fdtdump build/tmp/deploy/images/<MACHINE>/<board>.dtb | grep "bt-enable\|wcn7850-bt"
```

---

## Step 5 — Verify with dtbs_check

```bash
cd kernel-source

# Build with dtbs_check (reports binding violations):
make -j$(nproc) ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- \
  DT_SCHEMA_FILES=Documentation/devicetree/bindings/net/bluetooth/qcom,qca2066-bt.yaml \
  dtbs_check 2>&1 | grep -E "ERROR|WARNING|your_board"

# Just build DTBs (faster check for syntax errors):
make -j$(nproc) ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- \
  qcom/<board>.dtb

# NOTE: use "qcom/<board>.dtb" NOT "arch/arm64/boot/dts/qcom/<board>.dtb"
# The longer form fails with "No rule to make target".
```

---

## Step 5 — Deploy into Yocto via SRC_URI

Once the DTS draft passes `dtbs_check`, add it to the board's recipe so
it's included in the next `kas build`.

Find the board's `.bb` or `.bbappend`:
```bash
find <WORKSPACE>/meta-qcom -name "*<board>*" -name "*.bb*"
```

Add your DTS patch as a SRC_URI entry:
```bitbake
SRC_URI += "file://0001-arm64-dts-qcom-add-bt-for-<board>.patch"
```

Place the patch file in the recipe's `files/` directory:
```bash
# Generate the patch from your kernel-source changes:
cd kernel-source
git diff arch/arm64/boot/dts/ > /tmp/0001-arm64-dts-qcom-add-bt-for-<board>.patch
# Copy to meta-qcom recipe files dir:
cp /tmp/0001-arm64-dts-qcom-add-bt-for-<board>.patch \
   <WORKSPACE>/meta-qcom/recipes-kernel/linux/linux-qcom-next/
```

Then rebuild:
```bash
bitbake -c cleansstate linux-qcom-next && bitbake virtual/kernel
```

---

## Step 6 — Commit convention (for upstream submission later)

One DTS commit per subsystem. Use `git commit -s`:

```
arm64: dts: qcom: <board>: Add Bluetooth support

Add BT DTS node for <chip> connected to <uart> on <board>.

Signed-off-by: Your Name <you@example.com>
```

---

See also:
- `scripts/parse_sysio.py` — extract BT_EN / BT UART pins from a SYSIO Excel (Step 1)
- `references/dts-patterns.md` — Pattern B1/B2/C full skeletons
- `references/common-mistakes.md` — frequent DTS mistakes and fixes

## Next step

After DTS is verified and deployed: proceed to `qli-bt-flash` to flash
the new image to the board, then `qli-bt-debug` for on-target validation.
