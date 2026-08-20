---
name: qli-bt-sync-build
description: Pull meta-qcom, configure downloads mirror, and run kas build for a QLI BT bringup board
---

# qli-bt-sync-build

Pull meta-qcom, set up a build workspace, and run a full `kas build` for
a Qualcomm QLI board (QLI 0.0 mainline or QLI 2.0 6.18 LTS).

This is Step 1 of the BT bringup flow. Complete this before moving to
`qli-bt-kernel-prep` or `qli-bt-dts`.

---

## Step 0 — Determine QLI version and board

**First check whether this platform uses standard meta-qcom.** If the board
is not standard meta-qcom (e.g. it uses `meta-qcom-3rdparty` or any other
repo), do not assume repo naming, branch names, or kas yml paths mirror
meta-qcom — **ask the user for the complete sync command(s) and the complete
build command(s)**, and save them verbatim to `configs/<board>.yaml` under
`build.sync_cmd` / `build.build_cmd`. Then skip straight to running those
commands (Step 1 and Step 5 below don't apply — go to Step 2/3/3b/4/6 only
insofar as they're still relevant, e.g. tmux wrapping and output verification).

For **standard meta-qcom**, ask the user (or read from context):

| Input | Example |
|---|---|
| QLI version | QLI 0.0 (mainline) or QLI 2.0 (6.18 LTS) |
| Board | IQ-9075-EVK, IQ-8275-EVK, RB3Gen2, IQ-X7181-EVK, IQ10, … |
| Build server | server2 (sh02), server3 (sh03), server4 (sh04) |
| Workspace root | e.g. `/local/mnt/workspace/<user>/qclinux/QLI2.0/<BOARD>/` |

Server alias mapping:

| Alias | Hostname |
|---|---|
| server2 | <build-server-2> |
| server3 | <build-server-3> |
| server4 | <build-server-4> |

QLI version → branch / recipe correspondence:

| QLI version | meta-qcom branch | kernel recipe | kernel branch |
|---|---|---|---|
| QLI 0.0 / mainline | master | linux-qcom-next_git.bb | qcom-next |
| QLI 2.0 | wrynose | linux-qcom_6.18.bb | qcom-6.18.y |

---

## Step 1 — Clone meta-qcom on the build server

If `configs/<board>.yaml` has `build.sync_cmd` set, run that verbatim instead
of this step (it's a non-standard-repo platform — see Step 0).

```bash
# Replace <WORKSPACE> with your workspace root, e.g.:
# /local/mnt/workspace/<user>/qclinux/QLI2.0/<BOARD>
ssh <BUILD_SERVER>

mkdir -p <WORKSPACE>
cd <WORKSPACE>

# QLI 2.0
git clone https://github.com/qualcomm-linux/meta-qcom.git -b wrynose

# QLI 0.0 (mainline)
# git clone https://github.com/qualcomm-linux/meta-qcom.git -b master
```

---

## Step 2 — Install kas (if not already installed)

```bash
# On build server
pip3 install kas
# or in a venv on a shared machine:
python3 -m venv ~/kas-venv && source ~/kas-venv/bin/activate && pip3 install kas
```

---

## Step 3 — Create downloads.yml + symlink local downloads cache

Two mechanisms speed up the build. **Both are determined by checking the
filesystem — do not ask the user which one to use; this is not a choice,
it's a fact about the environment.**

**1. downloads.yml** — pulls from internal NFS mirror (for packages not in local cache)

Check first, unconditionally, before deciding anything:
```bash
ls /prj/qct/quic/oe_filer_scratch/DOWNLOADS/whinlatter | head -3
```
- **Path accessible** → create `downloads.yml` (below) and include it in the
  `kas build` command in Step 5.
- **Path not accessible** → skip `downloads.yml` entirely, omit it from the
  `kas build` command, and just tell the user the first pull will be slower
  (~30GB) — do not ask them to pick between mirror options.

`meta-qcom` does NOT ship this file. Create it manually:

```bash
cat > <WORKSPACE>/meta-qcom/ci/downloads.yml << 'EOF'
header:
  version: 14
local_conf_header:
  mirror: |
    SOURCE_MIRROR_URL = "file:///prj/qct/quic/oe_filer_scratch/DOWNLOADS/whinlatter"
    INHERIT += "own-mirrors"
EOF
```

**2. Local downloads cache symlink** — reuses already-downloaded packages across workspaces

Check first, unconditionally:
```bash
ls /local/mnt/workspace/<user>/qclinux/downloads 2>/dev/null && echo EXISTS || echo NONE
```
- **Exists** → create the symlink (below).
- **Doesn't exist** → skip silently, nothing to ask.

```bash
mkdir -p <WORKSPACE>/build
ln -s ../../../downloads <WORKSPACE>/build/downloads
```

The relative path `../../../downloads` resolves from `build/` up to `qclinux/downloads` — works regardless of absolute path.

---

## Step 3b — Add BT debug tools to image (before building)

BT debug tools must be in the rootfs — they cannot be added later via fastboot
(fastboot only replaces kernel + DTB, not rootfs).

Add to the image bbappend **before running `kas build`**:

```bash
# Standard image (qcom-multimedia-image)
cat >> <WORKSPACE>/meta-qcom/recipes-products/images/qcom-multimedia-image.bbappend << 'EOF'
CORE_IMAGE_BASE_INSTALL:append = " \
    bluez5 \
    bluez5-noinst-tools \
    libgpiod \
    libgpiod-tools \
    pciutils \
"
EOF

# IQ10 only (qcom-console-image) — use :append not +=
cat >> <WORKSPACE>/meta-qcom-distro/recipes-products/images/qcom-console-image.bbappend << 'EOF'
CORE_IMAGE_BASE_INSTALL:append = " \
    bluez5 \
    bluez5-noinst-tools \
    libgpiod \
    libgpiod-tools \
    pciutils \
"
EOF
```

Also add to `bsp-additions.cfg` for trace_printk support:
```
CONFIG_REGULATOR_DEBUG=y
CONFIG_FTRACE=y
CONFIG_FUNCTION_TRACER=y
CONFIG_DYNAMIC_FTRACE=y
```

---

## Step 4 — Board → kas yml mapping

| Board | MACHINE | kas yml |
|---|---|---|
| IQ-9075-EVK | iq-9075-evk | `meta-qcom/ci/iq-9075-evk.yml` |
| IQ-8275-EVK | iq-8275-evk | `meta-qcom/ci/iq-8275-evk.yml` |
| RB3Gen2 | rb3gen2-core-kit | `meta-qcom/ci/rb3gen2-core-kit.yml` |
| IQ-X7181-EVK (Hamoa) | iq-x7181-evk | `meta-qcom/ci/iq-x7181-evk.yml` |
| IQ10 | iq-10-rrd | `meta-qcom/ci/iq-10-rrd.yml` |

---

## Step 5 — Run the build in a tmux session

If `configs/<board>.yaml` has `build.build_cmd` set (non-standard-repo
platform, see Step 0), run that verbatim inside tmux instead of the `kas
build` line below — do not assume the yml path pattern matches meta-qcom.

**Always use tmux** — SSH disconnect kills the build otherwise.

```bash
ssh <BUILD_SERVER>
cd <WORKSPACE>
umask 0022

# Start tmux session
tmux new -s bt-build

# Inside tmux — QLI 2.0, IQ-9075-EVK, with internal mirror:
kas build meta-qcom/ci/iq-9075-evk.yml:meta-qcom/ci/qcom-distro.yml:meta-qcom/ci/downloads.yml

# Without mirror (if NFS not accessible):
# kas build meta-qcom/ci/iq-9075-evk.yml:meta-qcom/ci/qcom-distro.yml

# Debug profile (looser optimization, useful for kernel debug later):
# kas build meta-qcom/ci/iq-9075-evk.yml:meta-qcom/ci/qcom-distro.yml:meta-qcom/ci/debug.yml:meta-qcom/ci/downloads.yml
```

Detach from tmux: `Ctrl-b d`
Re-attach: `tmux attach -t bt-build`
Check progress: `tmux capture-pane -t bt-build -p | tail -30`

---

## Step 6 — Verify build output

```bash
# Build artifacts land in:
ls <WORKSPACE>/build/tmp/deploy/images/<MACHINE>/

# Key files for flashing:
# - *.qcomflash directory (or *.tar.gz if archived)
# - Image  (kernel)
# - *.dtb  (DTB)

# Check if kernel-source is available for externalsrc (rm_work may have cleared it):
ls <WORKSPACE>/build/tmp/work-shared/<MACHINE>/kernel-source/ | head -5
# Expected: arch/ block/ certs/ drivers/ ...
# If empty or missing → see Step 6b
```

---

## Step 6b — If work-shared/kernel-source is empty after build

`rm_work` (enabled by default in meta-qcom `base.yml`) clears kernel source after
the full build completes. If `build/tmp/work-shared/<MACHINE>/kernel-source/` is
empty, run a standalone kernel build to repopulate it:

```bash
kas shell meta-qcom/ci/<BOARD>.yml:meta-qcom/ci/downloads.yml -c 'bitbake virtual/kernel'
```

This is fast (most tasks are sstate cache hits). After it completes,
`kernel-source/` will be populated and ready to `cp -a` out for externalsrc.

---

## Troubleshooting

**`kas: command not found`** — not in PATH; try `~/.local/bin/kas` or activate venv.

**`bitbake: ERROR: No targets were given`** — malformed kas yml path; check for typo and that file exists.

**`Fetcher failure`** — network issue; check if internal mirror is mounted, or try without downloads.yml.

**Build killed (OOM)** — add to `<WORKSPACE>/build/conf/local.conf`:
```
BB_NUMBER_THREADS = "16"
PARALLEL_MAKE = "-j16"
```

---

## Auto-poll after build starts

After launching `kas build` in tmux, **do not wait for the user** — set up a
cron job to poll every 5 minutes and automatically continue to the next stage
when the build completes.

**Poll checks (every 20 min):**
```bash
# 1. Is tmux session still alive?
tmux has-session -t bt-build 2>/dev/null && echo "RUNNING" || echo "DONE_OR_DEAD"

# 2. Is .qcomflash ready?
ls <WORKSPACE>/build/tmp/deploy/images/<MACHINE>/*.qcomflash 2>/dev/null | head -1

# 3. Is kernel-source populated?
ls <WORKSPACE>/build/tmp/work-shared/<MACHINE>/kernel-source/arch 2>/dev/null && echo "KS_READY" || echo "KS_NOT_READY"
```

**Decision logic:**
- tmux session gone + `.qcomflash` exists → build succeeded → check kernel-source
  - kernel-source populated → proceed to Stage 3 (`qli-bt-kernel-prep`) automatically
  - kernel-source empty → run Step 6b (`bitbake virtual/kernel`) first, then Stage 3
- tmux session gone + no `.qcomflash` → build failed → report error from log and stop
- tmux session alive → still building → reschedule next check

**CronCreate prompt to use for polling (every 20 min, `*/20 * * * *`):**
```
Poll ventuno-q build on <build-server>. Workspace: /local/mnt/workspace/<user>/qclinux/QLI0.0/ventuno-q. Machine: ventuno-q. Check: (1) tmux bt-build alive? (2) .qcomflash exists? (3) kernel-source/arch exists? If build done and succeeded, automatically continue to qli-bt-kernel-prep. If build failed, report the last 30 lines of /tmp/bt-build-ventuno-q.log.
```

---

## Next step

Once the full build succeeds: proceed to `qli-bt-kernel-prep` to copy the
kernel source out and configure externalsrc for fast iterative BT DTS/driver
changes.
