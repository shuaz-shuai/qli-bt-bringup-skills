# Board reference notes

One `<board>.md` per board that has been fully brought up. Each note records
the values and steps that actually worked, so the next bring-up of the same
board — or a new board with the same BT chip — can reuse them instead of
starting from the schematic.

There are none yet. Add a note here after completing a board.

## What a good note contains

- Board identity: name, machine, kas yml, SoC
- BT chip + pattern (B1 / B2 / C)
- The **actual DTS changes** that worked (not a template — the real diff)
- Board-specific values: UART instance, BT_EN GPIO, pull, clock source
- Pitfalls hit and how they were resolved
- Flash quirks (e.g. two-phase, PCAT notes)

Pair each note with a matching `configs/<board>.yaml` (structured values that
the skills read automatically).
