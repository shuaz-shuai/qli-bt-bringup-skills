#!/usr/bin/env python3
"""
Parse a Qualcomm SYSIO / IO-assignment Excel sheet and extract the pins
needed to write a BT DTS node: BT_EN GPIO, BT UART (QUP instance + 4 lines),
and the default pull of each pin.

This is the PREFERRED data source for qli-bt-dts Step 1 — it is structured
(no schematic image reading) and already maps board nets to SoC GPIO numbers
and pinmux functions.

Usage:
    python3 parse_sysio.py <file.xlsx> [--sheet NAME] [--all-uart] [--dump-row N]

What it prints:
    - BT_EN pin      (GPIO number + default pull)
    - BT UART pins   (CTS/RFR(RTS)/TX/RX → GPIO numbers + QUP function)
    - a best-effort DTS hint (uart alias + gpio list)

Notes / limitations:
    - The 32.768 kHz sleep clock is usually a PMIC output, NOT a SoC GPIO,
      so it is typically absent from this sheet. Confirm it from the PMIC
      section or the reference board.
    - Column layout varies slightly between chips; this script scans every
      cell of a row for the signal keywords rather than hard-coding columns.
"""
import argparse
import re
import sys

try:
    import openpyxl
except ImportError:
    sys.exit("openpyxl not installed. Run: pip install openpyxl")


# BT UART line role -> regex matched against the cell text (case-insensitive)
UART_ROLES = [
    ("CTS", re.compile(r"BT\d*_UART_CTS", re.I)),
    ("RFR", re.compile(r"BT\d*_UART_(RFR|RTS)", re.I)),
    ("TX",  re.compile(r"BT\d*_UART_TX", re.I)),
    ("RX",  re.compile(r"BT\d*_UART_RX", re.I)),
]
BT_EN_RE = re.compile(r"BT_EN", re.I)
GPIO_NUM_RE = re.compile(r"GPIO\[(\d+)\]")
QUP_RE = re.compile(r"(QUP\d+_SE\d+)", re.I)


def gpio_num(cell0):
    """Return integer GPIO number from a col-0 label like 'GPIO[36]', else None."""
    if not cell0:
        return None
    m = GPIO_NUM_RE.search(str(cell0))
    return int(m.group(1)) if m else None


def row_text(row):
    return " ".join(str(c) for c in row if c is not None)


def find_functions(row):
    """Collect QUP function tokens from a row (pinmux Function columns)."""
    funcs = []
    for c in row:
        if c is None:
            continue
        m = QUP_RE.search(str(c))
        if m:
            funcs.append(m.group(1).upper())
    return funcs


def pull_of(row):
    """Default Pull is a short PU/PD/NP token; find the first such standalone cell."""
    for c in row:
        if c is None:
            continue
        s = str(c).strip().upper()
        if s in ("PU", "PD", "NP", "KEEPER", "PULL-UP", "PULL-DOWN"):
            return s
    return "?"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("xlsx")
    ap.add_argument("--sheet", default=None, help="sheet name (default: first)")
    ap.add_argument("--all-uart", action="store_true",
                    help="also list every UART pin in the sheet")
    ap.add_argument("--dump-row", type=int, default=None,
                    help="print all columns of the row for GPIO[N] (debug)")
    args = ap.parse_args()

    wb = openpyxl.load_workbook(args.xlsx, read_only=True, data_only=True)
    ws = wb[args.sheet] if args.sheet else wb.worksheets[0]
    rows = list(ws.iter_rows(min_row=1, values_only=True))

    if args.dump_row is not None:
        for row in rows:
            if gpio_num(row[0]) == args.dump_row:
                for i, c in enumerate(row):
                    if c is not None:
                        print(f"  col[{i}] = {c}")
                return
        sys.exit(f"GPIO[{args.dump_row}] not found")

    bt_en = None            # (gpio, pull, text)
    uart = {}               # role -> (gpio, func, pull, text)
    all_uart = []

    for row in rows:
        g = gpio_num(row[0])
        txt = row_text(row)
        txtu = txt.upper()

        if BT_EN_RE.search(txtu) and g is not None and bt_en is None:
            bt_en = (g, pull_of(row), txt)

        for role, rx in UART_ROLES:
            if role in uart:
                continue
            if rx.search(txtu) and g is not None:
                funcs = find_functions(row)
                uart[role] = (g, funcs[0] if funcs else "?", pull_of(row), txt)

        if args.all_uart and "UART" in txtu and g is not None:
            all_uart.append((g, txt[:70]))

    print("=" * 64)
    print(f"SYSIO: {args.xlsx}  (sheet: {ws.title})")
    print("=" * 64)

    print("\n[BT_EN]")
    if bt_en:
        g, pull, _ = bt_en
        print(f"  GPIO{g}   default-pull={pull}")
        if pull == "PD":
            print("  -> internal pull-down: no external pull-up assumed "
                  "(bias-pull-down + output-low in pinctrl)")
        elif pull == "PU":
            print("  -> internal pull-up present")
    else:
        print("  NOT FOUND — check schematic / PMIC section")

    print("\n[BT UART]  (QUP instance + 4 lines)")
    if uart:
        qups = {v[1] for v in uart.values() if v[1] != "?"}
        for role in ("TX", "RX", "CTS", "RFR"):
            if role in uart:
                g, func, pull, _ = uart[role]
                print(f"  {role:3} GPIO{g:<4} {func:<12} pull={pull}")
            else:
                print(f"  {role:3} NOT FOUND")
        print(f"  -> QUP instance: {', '.join(sorted(qups)) or '?'}")
        gpios = sorted(v[0] for v in uart.values())
        print(f"  -> pinctrl pins: {gpios}")
    else:
        print("  NOT FOUND — check schematic")

    print("\n[32.768 kHz sleep clock]")
    print("  Not in this sheet (PMIC output). Confirm from PMIC section "
          "or reference board.")

    if args.all_uart:
        print("\n[all UART pins in sheet]")
        for g, t in all_uart:
            print(f"  GPIO{g:<4} {t}")

    print("\n" + "=" * 64)
    print("Next: feed GPIO numbers + QUP instance into the DTS pattern "
          "(Step 2/3).")
    print("Only the sleep-clock source still needs confirming from another "
          "source.")


if __name__ == "__main__":
    main()
