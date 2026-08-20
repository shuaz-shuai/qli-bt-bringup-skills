# DTS Patterns for BT Enablement

Full DTS skeletons for BT bring-up on Qualcomm QLI platforms.

---

## Pattern B2 — QCA2066 / QCA6174 (no PMU wrapper)

**Chips:** QCA2066 (Cologne), QCA6174  
**Key binding:** `qcom,qca2066-bt.yaml`  
**Distinguishing feature:** No `wcn-pmu` wrapper; `enable-gpios` and `clocks`
directly on the `bluetooth{}` child node.

```dts
/* In board.dts */

&tlmm {
    /* BT enable GPIO — MUST have both output-low AND bias-pull-down */
    bt_en_default: bt-en-default-state {
        pins = "gpioNN";         /* TBD from schematic */
        function = "gpio";
        drive-strength = <2>;
        bias-pull-down;
        output-low;
    };

    /* BT UART pinctrl — MUST have all 4 pins (TX/RX/CTS/RTS) */
    bt_uart_default: bt-uart-default-state {
        pins = "gpioTX", "gpioRX", "gpioCTS", "gpioRTS";
        function = "qup<N>_se<M>";
        drive-strength = <2>;
        bias-pull-up;
    };
};

&uartNN {   /* TBD from schematic */
    status = "okay";
    pinctrl-names = "default";
    pinctrl-0 = <&bt_uart_default>;

    bluetooth {
        compatible = "qcom,qca2066-bt";
        clocks = <&CLOCK_SOURCE>;  /* 32.768 kHz LPO — TBD from schematic */
        enable-gpios = <&tlmm NN GPIO_ACTIVE_HIGH>;

        pinctrl-names = "default";
        pinctrl-0 = <&bt_en_default>;
    };
};
```

**What to fill in from schematic:**
- `gpioNN` in `bt_en_default` — which tlmm GPIO is BT_EN?
- `gpioTX/RX/CTS/RTS` — all 4 UART pins (confirm from schematic, not aliases)
- `CLOCK_SOURCE` — 32.768 kHz source (divclk? PMIC clkbuf? TCXO div?)
- `uartNN` — which UART instance (confirm from schematic)

**bt_en_default note:**
- `output-low` keeps BT chip in reset at boot (correct)
- `bias-pull-down` prevents floating when GPIO is released
- Missing either one is a common DTS mistake

**bt-enable-gpios hardwired pull-up case:**
If the schematic shows BT_EN tied to VCC (always-on pull-up), the GPIO
may not be needed in DTS. Confirm with hardware team before omitting —
if there's no pull-up, an absent gpio line leaves BT_EN floating.

---

## Pattern B1 — WCN3988 / WCN7850 (PMU wrapper)

**Chips:** WCN3988, WCN7850  
**Key binding:** `qcom,wcn3988-bt.yaml` or `qcom,wcn7850-bt.yaml`  
**Distinguishing feature:** `wcn-pmu` parent node in SoC dtsi; BT_EN is
`bt-enable-gpios` on the PMU wrapper, not on the bluetooth{} node itself;
supplies come from PMU LDO outputs.

```dts
/* In SoC dtsi (already present; shown here for reference) */
wcn_pmu: wcn-pmu {
    compatible = "qcom,wcn3988-pmu";   /* or wcn7850-pmu */
    /* ... supplies, clocks from SoC dtsi ... */
};

/* In board.dts — only override what the SoC dtsi doesn't set */
&wcn_pmu {
    bt-enable-gpios = <&tlmm NN GPIO_ACTIVE_HIGH>;  /* TBD from schematic */

    vddpmu-supply = <&vreg_ldo_NN>;    /* 1.8V — TBD from schematic */
    vddio-supply  = <&vreg_ldo_NN>;    /* 1.8V */
    vddaon-supply = <&vreg_ldo_NN>;    /* 0.9V */
    vdddig-supply = <&vreg_ldo_NN>;    /* 0.9V */
    /* Add others as listed in the binding's "required" section */
};

&uartNN {
    status = "okay";
    pinctrl-names = "default";
    pinctrl-0 = <&bt_uart_default>;

    bluetooth {
        compatible = "qcom,wcn3988-bt";  /* or wcn7850-bt */
    };
};
```

**What to fill in from schematic:**
- `bt-enable-gpios` GPIO — on the PMU wrapper, not bluetooth{} node
- All required supply phandles (check binding YAML `required:` list)
- UART instance

---

## Pattern C — M.2 Key E / PCIe + pwrseq-pcie-m2 (dynamic serdev)

**Chips:** QCA6696 (Hamilton), QCA6750, WCN6750  
**Key driver:** `pwrseq-pcie-m2.c`  
**Distinguishing feature:** No static `bluetooth{}` child node. The
`pwrseq-pcie-m2` driver creates the serdev device dynamically when the
PCIe BT function is enumerated.

```dts
/* In board.dts */

/* The M.2 slot power sequencer node */
pwrseq_m2: pwrseq-m2 {
    compatible = "qcom,pwrseq-pcie-m2";
    vddpcie-supply = <&vreg_ldo_NN>;    /* PCIe VDD — TBD */
    vddio-supply   = <&vreg_ldo_NN>;    /* I/O VDD — TBD */
    w-disable1-gpios = <&tlmm NN GPIO_ACTIVE_HIGH>;  /* PCIe enable */
    w-disable2-gpios = <&tlmm NN GPIO_ACTIVE_HIGH>;  /* UART enable */
    /* perst-gpios, reset-gpios per binding */
};

/* UART used for BT HCI (enabled, but no bluetooth{} child) */
&uartNN {
    status = "okay";
};
```

**For Pattern C debugging:**  
If BT doesn't come up, use `patch_pwrseq_m2.py` (in `qli-bt-debug/scripts/`)
to insert `trace_printk` points into `pwrseq-pcie-m2.c`. This covers the
full power-on sequence and serdev creation path.

Required kernel config for trace_printk:
```
CONFIG_FTRACE=y
CONFIG_DYNAMIC_FTRACE=y
```
Add to `bsp-additions.cfg` if not present.

---

## UART 4-wire pinctrl requirement

All patterns require the BT UART pinctrl to cover all 4 pins.

**Wrong (common mistake):**
```dts
bt_uart_default: bt-uart-default-state {
    pins = "gpio12", "gpio13";   /* TX/RX only — WRONG */
    ...
};
```

**Correct:**
```dts
bt_uart_default: bt-uart-default-state {
    pins = "gpio12", "gpio13", "gpio14", "gpio15";  /* TX/RX/CTS/RTS */
    ...
};
```

A 2-wire-only pinctrl causes intermittent UART noise and CRC errors under
load. The chip initializes but FW download times out or BT disconnects.
