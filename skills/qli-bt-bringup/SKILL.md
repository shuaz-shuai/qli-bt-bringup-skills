---
name: qli-bt-bringup
description: End-to-end BT bringup router for QLI boards — guides through sync/build, flash, kernel-prep, DTS, and on-target debug
---

# qli-bt-bringup

End-to-end BT host bring-up guide for Qualcomm QLI platforms. This skill
collects your context and routes you to the right sub-skill at each stage.

---

## Step 0 — Collect minimum context

Ask only what cannot be derived automatically:

| Question | Why needed |
|---|---|
| Board | Determines kas yml, machine name, reference board lookup |
| BT chip | Determines Pattern (B1/B2/C) and binding YAML |
| QLI version | Determines meta-qcom branch and kernel recipe |
| Build server | Needed for SSH access |

Everything else (UART instance, GPIO, clock, Windows drive letter, PCAT SN)
is resolved automatically from (shared board data at the repo top level):
1. `configs/<board>.yaml` — if board has been done before
2. `boards/<board>.md` — reference board for same chip
3. SYSIO Excel / schematic — only if not found in 1 or 2

If the user says "starting from scratch" → begin at Stage 1.
If the user names a specific stage → jump directly there.

---

## Stage 1 — Sync & Build

**Sub-skill:** `/qli-bt-sync-build`

What it covers:
- Clone `meta-qcom` on the build server
- Create `downloads.yml` for internal mirror
- **Add BT debug tools to image bbappend before building** (bluez5, libgpiod, etc.)
- Run `kas build` in tmux

Invoke when: user needs to set up a fresh workspace and run the first full build.

**Auto-check after build starts:**

Poll every 5 minutes until build completes:
```bash
# Check if build is still running
tmux capture-pane -t bt-build -p | tail -5

# Check if image is ready
ls <WORKSPACE>/build/tmp/deploy/images/<MACHINE>/*.qcomflash 2>/dev/null | head -1

# Check if kernel-source is available
ls <WORKSPACE>/build/tmp/work-shared/<MACHINE>/kernel-source/arch 2>/dev/null && echo "READY" || echo "NOT READY"
```

Only proceed to Stage 2 when **both** conditions are met:
1. `.qcomflash` directory exists in deploy/images
2. `kernel-source/arch` exists in work-shared

If kernel-source is empty after image is ready → run Step 6b from `qli-bt-sync-build`
to repopulate before proceeding.

**Handoff to Stage 2:** image and kernel-source both confirmed ready.

---

## Stage 2 — Flash (first time, full image via PCAT/EDL)

**Sub-skill:** `/qli-bt-flash`

What it covers:
- Map Linux build path to Windows drive letter
- Power board into EDL (Alpaca TAC)
- Flash full image via PCAT (`-MEMORYTYPE UFS` for most boards)
- Hamoa two-phase flash (spinor → UFS) for IQ-X7181-EVK
- Boot into HLOS

Invoke when: flashing the complete image to the board for the first time.

**Handoff to Stage 3:** board boots to Linux shell with all debug tools present in rootfs.

---

## Stage 3 — Kernel Prep (externalsrc)

**Sub-skill:** `/qli-bt-kernel-prep`

What it covers:
- Copy kernel source from `work-shared` → `kernel-source/`
- Add `EXTERNALSRC` + `EXTERNALSRC_BUILD` to the kernel `.bb` recipe
- Add `CONFIG_LOCALVERSION_AUTO=n` to `bsp-additions.cfg`
- Run `cleansstate` + rebuild kernel

Invoke when: board is running and user needs to edit kernel files (DTS, driver)
without waiting for a full `kas build` every time.

**Auto-check after cleansstate + rebuild:**

```bash
# Verify externalsrc is active
bitbake -e virtual/kernel | grep "^EXTERNALSRC="
# Expected: EXTERNALSRC="/path/to/kernel-source"

# Verify kernel-source is populated
ls <WORKSPACE>/kernel-source/arch 2>/dev/null && echo "READY" || echo "NOT READY"
```

Only proceed to Stage 4 when both checks pass.

**Handoff to Stage 4:** externalsrc confirmed active; `bitbake virtual/kernel` takes minutes.

---

## Stage 4 — DTS Enablement

**Sub-skill:** `/qli-bt-dts`

What it covers:
- Read binding YAML to extract required properties checklist
- Ask user for schematic details (UART instance, GPIO, clock, supplies)
- Draft the BT DTS node (Pattern B1 / B2 / C)
- Verify with `dtbs_check`
- Rebuild kernel only: `bitbake virtual/kernel`
- Flash updated kernel + DTB via **fastboot** (incremental, no full PCAT/EDL needed)

Key questions this stage will ask the user:
1. Path to the chip's binding YAML in the kernel tree
2. UART instance (from schematic, not aliases)
3. BT_EN GPIO pin number
4. 32.768 kHz clock source
5. Does BT_EN have a hardware pull-up?

**Fastboot incremental update (after bitbake virtual/kernel):**
```bash
adb -s <serial> reboot bootloader
fastboot flash efi   <BUILD_PATH>/efi.bin
fastboot flash dtb_a <BUILD_PATH>/dtb.bin
fastboot reboot
```

**Auto-check after fastboot:**

```bash
# Verify kernel version matches expected
adb -s <serial> shell uname -r

# Verify DTB contains BT node
adb -s <serial> shell "grep -r bluetooth /proc/device-tree/soc/ 2>/dev/null | head -3"
```

**Handoff to Stage 5:** board reboots with new kernel + DTB, BT node confirmed in device tree.

---

## Stage 5 — On-target Debug

**Sub-skill:** `/qli-bt-debug`

What it covers:
- dmesg 5-step triage (UART → PMU → hci_qca → FW → hci0)
- GPIO state verification
- `hciconfig` / `btmon` validation
- FW file check
- Regulator state (Pattern B1)
- `trace_printk` deep debug via `patch_pwrseq_m2.py` (Pattern C / M.2)

Invoke when: board boots but BT does not come up, or partial bring-up needs
deeper investigation.

---

## Routing logic

```
User: "I want to do BT bringup for IQ-9075-EVK with QCA2066"
→ Collect: board=IQ-9075-EVK, chip=QCA2066, QLI version?, build server?
→ "Starting from scratch?" → Stage 1: /qli-bt-sync-build

User: "Build is done, ready to flash"
→ Stage 2: /qli-bt-flash

User: "Board is running, need to set up externalsrc"
→ Stage 3: /qli-bt-kernel-prep

User: "externalsrc works, need to write the DTS"
→ Stage 4: /qli-bt-dts

User: "Board boots but hci0 doesn't appear"
→ Stage 5: /qli-bt-debug
```

After each sub-skill completes, return here and confirm:
- Did the stage succeed?
- Any blockers that need resolving before the next stage?
- Route to next stage or loop back if the current stage has issues.

---

## Chip → pattern reference

| Chip | Pattern | Sub-skill note |
|---|---|---|
| QCA2066 (Cologne) | B2 | `enable-gpios` + `clocks` on bluetooth{} node |
| WCN3988 / WCN7850 | B1 | PMU wrapper; `bt-enable-gpios` on `wcn-pmu` node |
| QCA6696 / QCA6750 (Hamilton M.2) | C | `pwrseq-pcie-m2`; no static bluetooth{} node; trace_printk needed for deep debug |

## Driver support check

Before Stage 4 DTS drafting, confirm the chip's `.compatible` string exists
in the kernel's `hci_qca.c` `qca_bluetooth_of_match[]` table:

```bash
grep -n "compatible\|qca_bluetooth_of_match" kernel-source/drivers/bluetooth/hci_qca.c | head -40
```

If the chip is not listed → stop and add driver support first (add the
`.compatible` entry to `qca_bluetooth_of_match[]` in `hci_qca.c`, plus any
chip-specific setup) before continuing with DTS work.
