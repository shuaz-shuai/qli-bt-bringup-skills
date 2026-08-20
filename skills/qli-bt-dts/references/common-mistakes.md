# Common BT DTS Mistakes

Frequently encountered errors when writing BT DTS nodes for Qualcomm QLI.

---

## 1. bt_en pinctrl missing output-low or bias-pull-down

**Symptom:** BT chip not powering on; `hci_qca` attaches but times out on
power-on sequence. Or: BT_EN line floats at unexpected level.

**Wrong:**
```dts
bt_en_default: bt-en-default-state {
    pins = "gpioNN";
    function = "gpio";
    drive-strength = <2>;
    bias-pull-down;     /* missing output-low */
};
```

**Correct:**
```dts
bt_en_default: bt-en-default-state {
    pins = "gpioNN";
    function = "gpio";
    drive-strength = <2>;
    bias-pull-down;
    output-low;     /* both required */
};
```

`output-low` keeps BT in reset at boot. `bias-pull-down` prevents floating
when the GPIO is in input mode.

---

## 2. UART pinctrl only covers TX/RX (missing CTS/RTS)

**Symptom:** BT enumerates but FW download times out; CRC errors under load;
intermittent disconnects.

**Wrong:**
```dts
pins = "gpio12", "gpio13";     /* only 2 pins */
```

**Correct:**
```dts
pins = "gpio12", "gpio13", "gpio14", "gpio15";   /* all 4: TX/RX/CTS/RTS */
```

---

## 3. Wrong DTB target path in make command

**Symptom:** `make: *** No rule to make target 'arch/arm64/boot/dts/qcom/<board>.dtb'`

**Wrong:**
```bash
make ARCH=arm64 arch/arm64/boot/dts/qcom/<board>.dtb
```

**Correct:**
```bash
make ARCH=arm64 qcom/<board>.dtb
```

The build system resolves the path from the arch directory automatically.
The full path form is not a valid make target.

---

## 4. bt-enable-gpios omitted because binding says "optional"

**Symptom:** BT doesn't power on; BT_EN pin measured floating.

**Cause:** The binding marks `bt-enable-gpios` as optional because some
boards have hardware pull-ups. Omitting it without a hardware pull-up leaves
the pin floating.

**Rule:** Always ask the hardware team or check the schematic:
- If there's a pull-up resistor to VCC on BT_EN → omitting the gpio in DTS is fine.
- If there's no pull-up → the gpio property is required even if binding says optional.

---

## 5. Guessing UART instance from aliases

**Symptom:** BT UART attaches to wrong controller; `geni_serial` probe fails
or wrong UART speed.

**Cause:** `serial1 = &uart17` in the SoC dtsi may be a placeholder or may
already be used by another peripheral. The alias doesn't guarantee BT is on
that UART.

**Rule:** Always confirm UART instance from schematic (look for UART_TX/RX
signals with BT label).

---

## 6. Pattern B1: bt-enable-gpios on bluetooth{} instead of PMU wrapper

**Symptom:** `dtbs_check` error: `enable-gpios: Unknown property` on the
bluetooth node, or PMU probe fails.

**Cause:** For WCN3988/WCN7850 (Pattern B1), BT_EN control is on the PMU
wrapper node (`wcn-pmu`), not on the child `bluetooth{}` node.

**Wrong (B1):**
```dts
bluetooth {
    compatible = "qcom,wcn3988-bt";
    bt-enable-gpios = <&tlmm NN GPIO_ACTIVE_HIGH>;  /* wrong place */
};
```

**Correct (B1):**
```dts
&wcn_pmu {
    bt-enable-gpios = <&tlmm NN GPIO_ACTIVE_HIGH>;  /* on PMU wrapper */
};
```

---

## 7. Adding serial alias that already exists

**Symptom:** `dtbs_check` warning: `aliases: Duplicate property`.

**Cause:** The SoC dtsi or board base dts already defines `serial1 = &uartNN`.
Adding it again in the overlay causes a conflict.

**Rule:** Before adding an alias, grep the full DTS include chain:
```bash
grep -r "serial1" arch/arm64/boot/dts/qcom/ --include="*.dts" --include="*.dtsi"
```
If it exists, do NOT add it again.

---

## 8. FW file not found at runtime

**Symptom:** `dmesg` shows `qca_download_firmware: failed to open firmware`.

**Cause:** The kernel's `btqca.c` constructs the firmware filename from the
`soc_type` field. If the driver entry in `hci_qca.c`'s `qca_bluetooth_of_match`
table doesn't exist for your chip, the wrong filename is constructed.

**Check:** The expected FW files:
| Chip | FW | NVM |
|---|---|---|
| QCA2066 (Cologne) | hpbtfw21.tlv | hpnv21.bin |
| QCA6696 (Hamilton) | crbtfw21.tlv | hpnv21.bin |
| QCA6698 (Hamilton Auto) | crbtfw21.tlv | hpnv21g.bin |

If FW files exist but aren't found, the `soc_type` in the driver table is
wrong — check the chip's entry in `hci_qca.c` to add/fix driver support.
