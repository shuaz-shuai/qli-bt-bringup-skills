# Remote Operations — SSH Safety Rules

Guidelines for working on build servers and target devices over SSH during
BT kernel development.

---

## General SSH rules

### 1. Never run bare `find` on large directories

```bash
# WRONG — hangs the terminal for minutes on a large workspace:
find /local/mnt/workspace/ -name "*.dtb"

# CORRECT — limit depth and scope:
find /local/mnt/workspace/myuser/qclinux/ -maxdepth 5 -name "*.dtb"
find /local/mnt/workspace/myuser/qclinux/QLI2.0/board/kernel-source/arch/arm64/boot/dts/ -name "*.dtb"
```

### 2. No interactive tools

Do not run these over SSH — they require a TTY and will hang or misbehave:
- `vim`, `nano`, `emacs`
- `top`, `htop`
- `python3` REPL (without `-c`)
- `git rebase -i`

For text editing: use the scp+Python pattern below.

### 3. Long tasks in tmux

For any task that takes more than ~30 seconds (build, flash, long test):

```bash
# Create session:
tmux new -s my-task

# Run the task inside tmux, then detach:
<command>
Ctrl-b d

# Poll output without re-attaching:
tmux capture-pane -t my-task -p | tail -20

# Re-attach when needed:
tmux attach -t my-task
```

---

## Remote file edit — use scp + Python, not sed

`sed` with multi-line patterns is unreliable:
- Pattern matching across lines requires careful escaping
- Failures are silent (sed succeeds with exit 0 but makes no change)
- Large files with similar content cause false matches

**Correct approach: scp the file to a local temp location, edit with
Python (which handles multi-line strings correctly), scp back.**

### Pattern: insert a block after a known anchor line

```python
#!/usr/bin/env python3
# Run locally after scp-ing the file, then scp the result back

FILE = "/tmp/target_file.c"

with open(FILE, 'r') as f:
    content = f.read()

# Define anchor and replacement (must be unique in the file)
old = "static int my_func(struct device *dev)\n{"
new = ("static int my_func(struct device *dev)\n{\n"
       '\ttrace_printk("MY_DRIVER ENTRY: dev=%s\\n", dev_name(dev));\n')

# Assert the anchor exists (fail loud, not silent)
assert old in content, f"Anchor not found: {repr(old[:80])}"

content = content.replace(old, new, 1)

with open(FILE, 'w') as f:
    f.write(content)

print("Done.")
```

### Full workflow

```bash
# 1. Copy file from build server to local:
scp <BUILD_SERVER>:/path/to/kernel-source/drivers/foo/bar.c /tmp/bar.c

# 2. Edit /tmp/bar.c using Python script (assert-guarded replacements)
python3 my_edit_script.py

# 3. Copy file back:
scp /tmp/bar.c <BUILD_SERVER>:/path/to/kernel-source/drivers/foo/bar.c

# 4. Rebuild:
ssh <BUILD_SERVER> "cd <WORKSPACE> && umask 0022 && bitbake virtual/kernel"
```

---

## Copying files to the target device

If the build server can reach the device directly (same network):
```bash
scp <BUILD_SERVER>:/path/to/Image root@<DEVICE_IP>:/boot/
ssh root@<DEVICE_IP> "sync; reboot"
```

If not (build server can't reach device but your laptop can reach both):
```bash
# Step 1: build server → local
scp <BUILD_SERVER>:/path/to/Image /tmp/

# Step 2: local → device
scp /tmp/Image root@<DEVICE_IP>:/boot/
```

---

## Polling build output without attaching

```bash
# Single snapshot:
tmux capture-pane -t bt-build -p | tail -40

# Watch loop (run from local machine):
while true; do
    ssh <BUILD_SERVER> "tmux capture-pane -t bt-build -p 2>/dev/null | tail -5"
    sleep 30
done
```
