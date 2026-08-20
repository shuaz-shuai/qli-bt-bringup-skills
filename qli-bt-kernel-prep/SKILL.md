---
name: qli-bt-kernel-prep
description: Copy kernel source from work-shared and configure externalsrc for fast BT kernel iteration
---

# qli-bt-kernel-prep

Copy the kernel source out of work-shared, configure `externalsrc` in the
kernel `.bb` recipe, and set `CONFIG_LOCALVERSION_AUTO=n` so kernel modules
load correctly.

This is Step 2 of the BT bringup flow, after `qli-bt-sync-build`.

---

## Step 1 — Copy kernel source out of work-shared

```bash
ssh <BUILD_SERVER>
cd <WORKSPACE>

# kernel-source is at:
# QLI 0.0: build/tmp/work-shared/<MACHINE>/kernel-source/
# QLI 2.0: build/tmp/work-shared/<MACHINE>/kernel-source/

cp -a build/tmp/work-shared/<MACHINE>/kernel-source kernel-source/

# Verify:
ls kernel-source/
# Expected: arch/ drivers/ include/ Makefile fs/ net/ ...
```

> **Note:** Use `cp -a`, NOT symlink — cleansstate deletes work-shared and
> the symlink breaks.

> **Note:** If `kernel-source/` is empty after a full build (rm_work cleaned
> it), run a standalone kernel build to repopulate it first:
> ```bash
> kas shell meta-qcom/ci/<board>.yml:meta-qcom/ci/downloads.yml \
>   -c 'bitbake virtual/kernel'
> ```

---

## Step 2 — Edit the kernel .bb recipe to add externalsrc

```bash
# QLI 0.0
BB_FILE=<WORKSPACE>/meta-qcom/recipes-kernel/linux/linux-qcom-next_git.bb
# QLI 2.0
# BB_FILE=<WORKSPACE>/meta-qcom/recipes-kernel/linux/linux-qcom_6.18.bb

sed -i '/^inherit kernel cml1/a \
\
# Use local kernel source tree instead of fetching from git.\
inherit externalsrc\
EXTERNALSRC = "${TOPDIR}/../kernel-source"\
EXTERNALSRC_BUILD = "${WORKDIR}/${BPN}-${PV}/build"' $BB_FILE

# Verify:
grep -A4 'inherit externalsrc' $BB_FILE
```

> **Note:** Must add `inherit externalsrc` — setting EXTERNALSRC variables
> alone has no effect without inheriting the class.

> **Note:** Add **after** `inherit kernel cml1`, not at the top of the file.

> **Note:** Kernel uses `${WORKDIR}/${BPN}-${PV}/build` for EXTERNALSRC_BUILD,
> not `${WORKDIR}/build` like normal recipes.

---

## Step 3 — Add CONFIG_LOCALVERSION_AUTO=n

```bash
# QLI 0.0
echo 'CONFIG_LOCALVERSION_AUTO=n' >> \
  <WORKSPACE>/meta-qcom/recipes-kernel/linux/linux-qcom-next/configs/bsp-additions.cfg

# QLI 2.0
# echo 'CONFIG_LOCALVERSION_AUTO=n' >> \
#   <WORKSPACE>/meta-qcom/recipes-kernel/linux/linux-qcom-6.18/configs/bsp-additions.cfg
```

> **Note:** Do NOT add this to `kernel-source/` configs (e.g. `qcom.config`) —
> those files come from the `cp -a` and will be lost if you re-copy kernel-source.
> Always add to the recipe's `bsp-additions.cfg` in `meta-qcom/`.

---

## Step 4 — cleansstate and rebuild

```bash
cd <WORKSPACE>
umask 0022
tmux new -s bt-build

kas shell meta-qcom/ci/<board>.yml:meta-qcom/ci/qcom-distro.yml:meta-qcom/ci/downloads.yml \
  -c 'bitbake -c cleansstate linux-qcom-next && bitbake virtual/kernel'

# QLI 2.0:
# kas shell ... -c 'bitbake -c cleansstate linux-qcom-6.18 && bitbake virtual/kernel'
```

After completion, DTB and Image appear in `build/tmp/deploy/images/<MACHINE>/`.

> **Note:** cleansstate is mandatory — skipping triggers `version-going-backwards`
> QA fatal error.

## Auto-poll after kernel rebuild starts

After launching cleansstate + bitbake virtual/kernel in tmux, **do not wait for
the user** — set a CronCreate job to poll every 5 minutes and automatically
continue to the next stage when done.

**CronCreate settings:** `*/5 * * * *`, recurring, session-only.

**Poll checks:**
```bash
# 1. Is tmux session alive?
tmux has-session -t bt-kbuild 2>/dev/null && echo RUNNING || echo GONE

# 2. Is new kernel deployed?
ls <WORKSPACE>/build/tmp/deploy/images/<MACHINE>/vmlinux-<MACHINE>.bin 2>/dev/null && echo KERNEL_READY || echo NOT_READY
```

**Decision logic:**
- tmux RUNNING → still building, do nothing (cron fires again)
- tmux GONE + KERNEL_READY → succeeded → invoke `qli-bt-dts`
- tmux GONE + NOT_READY → failed → fetch last 40 lines of build log and report

**CronCreate prompt template:**
```
Poll ventuno-q kernel rebuild on <build-server>. Workspace: <WORKSPACE>. Machine: <MACHINE>.
Check via mcp__bt-mcp__ssh_exec (host: <SERVER>, username: <user>):
1. tmux has-session -t bt-kbuild 2>/dev/null && echo RUNNING || echo GONE
2. ls <WORKSPACE>/build/tmp/deploy/images/<MACHINE>/vmlinux-<MACHINE>.bin 2>/dev/null && echo KERNEL_READY || echo NOT_READY
If GONE + KERNEL_READY → invoke skill qli-bt-dts.
If GONE + NOT_READY → fetch last 40 lines of build log and report.
```

> **Note:** If build fails with `FileNotFoundError: qcom-metadata.dtb`:
> ```bash
> bitbake -c cleansstate qcom-dtb-metadata
> bitbake qcom-dtb-metadata
> bitbake virtual/kernel
> ```

---

## Daily workflow after setup

```bash
# Edit kernel-source/, then:
bitbake -c compile -f virtual/kernel
bitbake -c deploy -f virtual/kernel
```

---

## Recovery — kernel-source lost or empty

If `kernel-source/` was deleted or emptied (e.g. by cleansstate or rm_work)
while externalsrc is still active, bitbake will skip fetch/unpack and fail.
Follow this sequence to restore it:

```bash
BB_FILE=<WORKSPACE>/meta-qcom/recipes-kernel/linux/linux-qcom-next_git.bb
# QLI 2.0: linux-qcom_6.18.bb

# Step 1: comment out externalsrc (so bitbake can fetch again)
sed -i 's/^inherit externalsrc/#inherit externalsrc/' $BB_FILE
sed -i 's/^EXTERNALSRC =/#EXTERNALSRC =/' $BB_FILE
sed -i 's/^EXTERNALSRC_BUILD =/#EXTERNALSRC_BUILD =/' $BB_FILE

# Step 2: cleanall + unpack to repopulate work-shared
kas shell meta-qcom/ci/<board>.yml:meta-qcom/ci/downloads.yml
bitbake -c cleanall virtual/kernel
bitbake -c unpack virtual/kernel

# Step 3: verify work-shared has content
ls <WORKSPACE>/build/tmp/work-shared/<MACHINE>/kernel-source/ | head -5

# Step 4: cp -a out
cp -a <WORKSPACE>/build/tmp/work-shared/<MACHINE>/kernel-source <WORKSPACE>/kernel-source

# Step 5: restore externalsrc
sed -i 's/^#inherit externalsrc/inherit externalsrc/' $BB_FILE
sed -i 's/^#EXTERNALSRC =/EXTERNALSRC =/' $BB_FILE
sed -i 's/^#EXTERNALSRC_BUILD =/EXTERNALSRC_BUILD =/' $BB_FILE

# Step 6: cleansstate + rebuild
bitbake -c cleansstate linux-qcom-next && bitbake virtual/kernel
# QLI 2.0: bitbake -c cleansstate linux-qcom-6.18 && bitbake virtual/kernel
```

---

## Normal Recipe externalsrc (e.g. bluez5, pipewire)

For non-kernel recipes, use a bbappend instead of editing the original recipe.

### Step 1 — Find and copy source

Normal recipe source is under `build/tmp/work/<arch>/<recipe>/<ver>/sources/<name>/`.
The arch directory name varies — use `find` to confirm:

```bash
find <WORKSPACE>/build/tmp/work -maxdepth 3 -name '<recipe>' -type d
# e.g. find .../build/tmp/work -maxdepth 3 -name 'bluez5' -type d
# → .../build/tmp/work/armv8-2a-qcom-linux/bluez5
```

If not built yet, unpack first:
```bash
bitbake -c unpack <recipe>
```

Then copy out:
```bash
cp -a <WORKSPACE>/build/tmp/work/<arch>/<recipe>/<ver>/sources/<name> \
      <WORKSPACE>/<recipe>-source
ls <WORKSPACE>/<recipe>-source | head -5   # verify top level has source files
```

### Step 2 — Create bbappend

```bash
BBAPPEND=<WORKSPACE>/meta-qcom/recipes-<category>/<recipe>/<recipe>_%.bbappend
mkdir -p $(dirname $BBAPPEND)

cat > $BBAPPEND << 'HEREDOC'
inherit externalsrc
EXTERNALSRC = "${TOPDIR}/../<recipe>-source"
EXTERNALSRC_BUILD = "${WORKDIR}/build"
HEREDOC
```

> **Note:** Use single-quote heredoc (`<< 'HEREDOC'`) — double-quote allows shell
> to expand `${TOPDIR}` to empty string.

> **Note:** Normal recipes use `${WORKDIR}/build` for EXTERNALSRC_BUILD,
> unlike kernel which uses `${WORKDIR}/${BPN}-${PV}/build`.

### Step 3 — cleansstate + compile

```bash
bitbake -c cleansstate <recipe>
bitbake -c compile <recipe>
```

### Daily workflow

```bash
bitbake -c compile -f <recipe>
```


---

## Pitfalls

**1. cleansstate 删掉 work-shared/kernel-source**
必须 `cp -a` 到 `build/tmp` 外面，不能用 symlink。

**2. 普通 recipe source 的 arch 目录名不是 aarch64**
pipewire 等在 `armv8-2a-qcom-linux/`，不是 `aarch64-qcom-linux/`。
用 `find ... -name '<recipe>' -type d` 确认实际路径。

**3. 普通 recipe source 在 sources/<name>/ 子目录下**
不是直接在 `work/<ver>/` 下，cp 时要指定到 `sources/<name>/` 这一层，否则多一层目录。

**4. bbappend 里的变量必须用单引号 heredoc 保护**
直接用双引号 `<< "EOF"` 会让 shell 展开 `${TOPDIR}` 为空。必须用 `<< 'HEREDOC'`。

**5. 两个 bitbake 实例抢同一个 server**
在同一个 kas shell 里不能同时跑两个 bitbake。如果全量编译还在跑，另一个 window 里执行
unpack/compile 会显示 `NOTE: Reconnecting to bitbake server... Retrying server connection (#1)...`
这是正常等待，不是报错，等前者完成后会自动接上。

**6. kas shell 进入后触发 zsh-newuser-install**
<build-server> 上 kas shell 默认进入 zsh，首次进入会弹出 zsh 新用户配置向导。
按 `0`（创建空 .zshrc）一次性解决，之后不再弹出。不要按 `q`（下次还会弹）。

**7. cp 前先确认 work-shared/sources 存在**
目录只有在 bitbake 跑过 unpack 之后才有内容。不存在时先 `bitbake -c unpack <recipe>`，再 cp。

**8. 全量编译进行中时 kernel-source 尚不存在**
在全新 workspace 上同时启动 `kas build` 并想配 externalsrc 时，
`build/tmp/work-shared/<machine>/kernel-source/` 要等 bitbake 跑到 kernel 的 do_unpack task 才会出现。
不能在 kas build 刚启动时就 cp。正确做法：后台轮询等待目录出现：

```bash
nohup bash -c '
for i in $(seq 1 72); do
  if ls <WORKSPACE>/build/tmp/work-shared/<MACHINE>/kernel-source/arch 2>/dev/null; then
    echo "READY at $(date)" > <WORKSPACE>/kernel_ready.flag
    break
  fi
  sleep 50
done
' > /dev/null 2>&1 &

# 检查是否就绪
cat <WORKSPACE>/kernel_ready.flag 2>/dev/null || echo "not ready yet"
```

就绪后再执行 `cp -a` + 修改 .bb + cleansstate + `bitbake virtual/kernel`。

**9. cp -a 后先 ls 验证**
确认顶层直接是源码文件（arch/、meson.build 等），不是多了一层同名子目录。

**10. kernel EXTERNALSRC_BUILD 和普通 recipe 不同**
- kernel：`${WORKDIR}/${BPN}-${PV}/build`
- 普通 recipe（meson）：`${WORKDIR}/build`
不要混用。

**10b. 切换 externalsrc 时必须同时加 CONFIG_LOCALVERSION_AUTO=n**
本地 kernel-source 的 git hash 和原始 recipe 的 SRCREV 不同，编出来的 vermagic 会带 dirty/local hash，
导致 out-of-tree .ko 加载失败（vermagic mismatch）。每次配 externalsrc 时必须同步加这个 config，两个操作绑定在一起。

**11. version-going-backwards QA 错误**
根因：之前编译过的 sstate 里 kernel 版本带 git hash（如 `7.1+7.2-rc3+nord+git0+8102c4a07b-r0`），
加了 `CONFIG_LOCALVERSION_AUTO=n` 后新版本不带 hash，bitbake 认为版本倒退，报 Fatal QA error。

预防：加 externalsrc 和 `CONFIG_LOCALVERSION_AUTO=n` 后，**必须先 cleansstate 再编**。

修复（已经出错时）：
```bash
# QLI 0.0
bitbake -c cleansstate linux-qcom-next && bitbake virtual/kernel
# QLI 2.0
bitbake -c cleansstate linux-qcom-6.18 && bitbake virtual/kernel
```

**12. cleansstate 后 qcom-metadata.dtb 丢失**
`bitbake -c cleansstate linux-qcom-next` 会清空 deploy 目录，`qcom-metadata.dtb`（由 `qcom-dtb-metadata` 生成）也被删掉。
后续 `do_generate_qcom_fitimage` 报 `FileNotFoundError`。

修复：
```bash
bitbake -c cleansstate qcom-dtb-metadata
bitbake qcom-dtb-metadata
bitbake virtual/kernel
# 或直接编完整 image，bitbake 自动处理依赖：
bitbake qcom-multimedia-image
```

**13. qcubuntu 和 Yocto 共用 kernel-source 互相污染**
qcubuntu 编译后留下 `arch/arm64/include/generated/`，Yocto externalsrc 检测到报 `not clean`。
解决：qcubuntu 用独立 clone，或手动删：
```bash
rm -rf kernel-source/arch/arm64/include/generated
rm -f kernel-source/.config
rm -rf kernel-source/include/config/
```

**14. SRC_URI / SRCREV 不需要删**
externalsrc 会覆盖 git fetch，保留原有字段不影响编译，方便随时切回。

**15. DEBUG_BUILD=1 自动启用 debug kernel config**
在 `build/conf/local.conf` 加 `DEBUG_BUILD = "1"` 后 cleansstate 重编，
debug config 自动合并，无需手动改 defconfig。

---

## Next step

Proceed to `qli-bt-dts` to draft the BT DTS node.
