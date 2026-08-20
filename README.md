# QLI Bluetooth Bring-up Skills

A set of [Agent Skills](https://docs.claude.com/en/docs/claude-code/skills) for
bringing up Bluetooth on Qualcomm QLI (Qualcomm Linux) boards — from a fresh
Yocto build all the way to a working `hci0` on target.

These skills turn an AI coding agent (Claude Code, and other skill-compatible
hosts) into a guided BT bring-up assistant: it collects the minimum context,
routes you to the right stage, and runs the concrete commands for sync/build,
flashing, kernel iteration, device-tree enablement, and on-target debug.

> **Note on values:** Server names, credentials, and site-specific paths in
> these skills have been replaced with placeholders like `<build-server>`,
> `<user>`, and `<device-password>`. Fill in your own before use. Board names
> (IQ-9075-EVK, Hamoa, Monza, RB3Gen2, …) are public Qualcomm product names.

---

## Skills

| Skill | Stage | What it does |
|---|---|---|
| **qli-bt-bringup** | Router | End-to-end router — collects context and dispatches to the stage skills below |
| **qli-bt-sync-build** | 1 | Clone `meta-qcom`, configure the downloads mirror, add BT debug tools, run `kas build` |
| **qli-bt-flash** | 2 | Flash the full image via PCAT/EDL (incl. Hamoa two-phase spinor→UFS), boot to HLOS |
| **qli-bt-kernel-prep** | 3 | Set up `externalsrc` so kernel edits rebuild in minutes instead of a full `kas build` |
| **qli-bt-dts** | 4 | Draft the BT DTS node from the binding YAML + **SYSIO Excel**, `dtbs_check`, deploy via SRC_URI |
| **qli-bt-debug** | 5 | On-target triage: dmesg 5-step, GPIO check, `btmon`, `trace_printk` deep debug |

---

## The bring-up pipeline

```
 1. sync-build  →  2. flash  →  3. kernel-prep  →  4. dts  →  5. debug
   kas build       PCAT/EDL      externalsrc       BT node    hci0 up
```

Each stage hands off to the next; `qli-bt-bringup` is the entry point that
decides where to start based on what you've already done.

## Chip → DTS pattern

| Chip | Pattern | Note |
|---|---|---|
| QCA2066 (Cologne) | B2 | `enable-gpios` + `clocks` on the `bluetooth{}` node |
| WCN3988 / WCN7850 | B1 | PMU wrapper; `bt-enable-gpios` on the `wcn-pmu` node |
| QCA6696 / QCA6750 (M.2) | C | `pwrseq-pcie-m2`; no static `bluetooth{}` node; `trace_printk` for deep debug |

---

## Highlight: SYSIO-driven DTS

`qli-bt-dts` prefers the board's **SYSIO IO-assignment Excel** over reading a
schematic PDF. The included `scripts/parse_sysio.py` extracts the BT pins
directly — BT_EN GPIO, the BT UART's four lines (TX/RX/CTS/RFR), the QUP
instance, and each pin's default pull:

```bash
python3 skills/qli-bt-dts/scripts/parse_sysio.py <board>_SYSIO.xlsx
```

```
[BT_EN]    GPIO55  default-pull=PD   → bias-pull-down + output-low
[BT UART]  TX GPIO35  RX GPIO36  CTS GPIO33  RFR GPIO34   → QUP0_SE2
```

This is structured and deterministic — no schematic image reading. The 32.768
kHz sleep clock is a PMIC output (not in the GPIO sheet), so it is still
confirmed from the PMIC section or a reference board.

---

## Repository layout

```
qli-bt-bringup-skills/
├── skills/                 # installable Agent Skills (one dir each)
│   ├── qli-bt-bringup/     #   router
│   ├── qli-bt-sync-build/
│   ├── qli-bt-flash/
│   ├── qli-bt-kernel-prep/
│   ├── qli-bt-dts/         #   includes scripts/parse_sysio.py
│   └── qli-bt-debug/
├── configs/                # shared: structured per-board config (<board>.yaml)
│   └── _template.yaml
└── boards/                 # shared: per-board reference notes (<board>.md)
    └── iq-x7181-evk.md
```

**Completed-platform data is shared, at the top level** — not inside any one
skill — because a board's values are used across every stage (flash needs the
Windows drive, dts needs the GPIO/UART, debug needs the pattern):

- `configs/<board>.yaml` — machine-readable values. When present, the skills
  read it directly and **skip asking you**. Copy `_template.yaml` to start.
- `boards/<board>.md` — human/agent notes: the actual DTS changes that worked,
  pitfalls, flash quirks. Read first when bringing up a **new board with the
  same chip** to reuse the structure.

After finishing a board, save both files here so the next bring-up reuses them.

---

## Installation

Clone into your Claude Code skills directory:

```bash
git clone https://github.com/shuaz-shuai/qli-bt-bringup-skills.git
cp -r qli-bt-bringup-skills/skills/qli-bt-* ~/.claude/skills/
```

The skills read `configs/` and `boards/` relative to the repo root, so keep the
clone around (or copy those two dirs alongside wherever you run from).

### Dependencies

- `openpyxl` — for `parse_sysio.py` (`pip install openpyxl`)
- A QLI build environment (kas, bitbake) on the build server for stages 1–4
- `adb` / `fastboot` and PCAT/EDL tooling for flashing

---

## License

MIT
