# Reference board: IQ-X7181-EVK (Hamoa, x1e80100)
# BT chip: WCN7850, Pattern B1 (PMU wrapper)
# Status: bringup complete

board:
  name: iq-x7181-evk
  machine: iq-x7181-evk
  kas_yml: meta-qcom/ci/iq-x7181-evk.yml
  soc: x1e80100 (Hamoa)

bt:
  chip: wcn7850
  pattern: B1
  binding_yaml: Documentation/devicetree/bindings/net/bluetooth/qcom,wcn7850-bt.yaml
  uart_instance: uart14
  bt_en_gpio: "tlmm 116 GPIO_ACTIVE_HIGH"
  bt_en_hardware_pullup: "no"
  clock_source: "not required (WCN7850 B1 pattern, clock handled by PMU wrapper)"
  pmu_wrapper_node: wcn7850-pmu

## DTS changes required (3 additions to hamoa-iot-evk.dts)

### 1. Add bt-enable-gpios + pinctrl to wcn7850-pmu node
```dts
wcn7850-pmu {
    ...
    bt-enable-gpios = <&tlmm 116 GPIO_ACTIVE_HIGH>;
    pinctrl-0 = <&wcn_wlan_en>, <&wcn_bt_en>;   /* append wcn_bt_en */
    pinctrl-names = "default";
    ...
};
```

### 2. Add wcn_bt_en pinctrl state in &tlmm
```dts
wcn_bt_en: wcn-bt-en-state {
    pins = "gpio116";
    function = "gpio";
    drive-strength = <2>;
    bias-disable;
};
```

### 3. Add bluetooth child node under &uart14
```dts
&uart14 {
    status = "okay";

    bluetooth {
        compatible = "qcom,wcn7850-bt";
        max-speed = <3200000>;

        vddaon-supply   = <&vreg_pmu_aon_0p59>;
        vddwlcx-supply  = <&vreg_pmu_wlcx_0p8>;
        vddwlmx-supply  = <&vreg_pmu_wlmx_0p85>;
        vddrfacmn-supply = <&vreg_pmu_rfa_cmn>;
        vddrfa0p8-supply = <&vreg_pmu_rfa_0p8>;
        vddrfa1p2-supply = <&vreg_pmu_rfa_1p2>;
        vddrfa1p8-supply = <&vreg_pmu_rfa_1p8>;
    };
};
```

## Notes
- vreg_pmu_* labels come from regulators{} block inside wcn7850-pmu — no new regulators needed
- bt-enable-gpios is on the PMU wrapper node, NOT on bluetooth{} node
- UART pinctrl already has 4 pins in base DTS — no override needed
- Flash: two-phase (spinor + UFS), PCAT SN 5DEE301B
