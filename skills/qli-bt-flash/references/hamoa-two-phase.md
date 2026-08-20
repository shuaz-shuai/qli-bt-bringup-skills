# Hamoa Two-Phase Flash

Detailed guide for flashing IQ-X7181-EVK (Hamoa, x1e80100 / X Elite chipset),
which requires two separate PCAT flash operations.

---

## Why two phases?

The Hamoa platform uses:
- **Phase 1**: SPI-NOR flash (boot ROM + primary bootchain) — PCAT parameter: `-MEMORYTYPE spinor`
- **Phase 2**: UFS (main filesystem, kernel, rootfs) — PCAT parameter: `-MEMORYTYPE UFS`

Both phases are required; you cannot skip Phase 1 even for kernel-only
updates after initial provisioning. Phase 1 only needs to be re-flashed
if the bootchain changes.

---

## Image directory structure

After extracting the build tarball:
```
iq-x7181-evk-<timestamp>/
├── spinor/              ← Phase 1 target
│   ├── prog_firehose_ddr.elf
│   └── *.xml
└── *.qcomflash          ← Phase 2 target (root dir)
    ├── prog_firehose_ddr.elf
    └── *.xml
```

---

## Phase 1 — spinor flash

```
xPCAT.exe -PROGRAM -MEMORYTYPE spinor -IMAGE <path>\iq-x7181-evk-<ts>\spinor\ -DEVICE <ID>
```

### Critical: No extra parameters on Phase 1

The following parameters **must not** be added to Phase 1:
- `-SLOT`
- `-FLAVOR`
- `-SKIPEDLRESET`
- Any other flags not shown above

Adding extra parameters causes PCAT to set `skipSahara=true` internally.
This results in:
```
Error: DEVICE_INVALID_PACKET
```
The flash appears to start but fails immediately after the first packet.

After Phase 1 completes, the board stays powered on but does **not**
automatically re-enter EDL. You must trigger it manually before Phase 2.

---

## Re-enter EDL between phases

```
python C:\mcp-serial\alpaca.py VTP21 off
# Wait 2 seconds
python C:\mcp-serial\alpaca.py VTP21 edl
```

Or:
```
xPCAT.exe -MODE EDL -DEVICE <ID>
```

Confirm EDL mode: Device Manager should show `Qualcomm HS-USB QDLoader 9008`.

---

## Phase 2 — UFS flash

```
xPCAT.exe -PROGRAM -MEMORYTYPE UFS -IMAGE <path>\iq-x7181-evk-<ts>\ -DEVICE <ID>
```

Note: the `-IMAGE` path points at the **root** of the image directory
(where the `.qcomflash` files and `prog_firehose_ddr.elf` are), not the
`spinor/` subdirectory.

---

## First-time flash on a new board

New Hamoa boards ship without UFS provisioned. Without provisioning,
Phase 2 fails with:
```
Error: DEVICE_RESPONSE_ERROR
```

Use PCAT's UFS provisioning command before the first regular flash:
```
xPCAT.exe -PROVISIONING -MEMORYTYPE UFS -DEVICE <ID>
```

Then proceed with Phase 1 + Phase 2 as normal.

---

## Complete flash sequence checklist

```
[ ] 1. Board powered off
[ ] 2. Trigger EDL:   alpaca.py VTP21 edl
[ ] 3. Confirm EDL:   Device Manager shows QDLoader 9008
[ ] 4. Phase 1:       xPCAT -PROGRAM -MEMORYTYPE spinor -IMAGE ...\spinor\ -DEVICE <ID>
[ ] 5. Re-enter EDL:  alpaca.py VTP21 off; wait 2s; alpaca.py VTP21 edl
[ ] 6. Phase 2:       xPCAT -PROGRAM -MEMORYTYPE UFS -IMAGE ...\ -DEVICE <ID>
[ ] 7. Boot HLOS:     alpaca.py VTP21 hlos
```
