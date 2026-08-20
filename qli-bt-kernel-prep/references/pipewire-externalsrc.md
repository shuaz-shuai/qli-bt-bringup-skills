# pipewire externalsrc — QLI 2.0 / IQ615 操作记录

## 环境

- 工作目录：`/local/mnt/workspace/<user>/qclinux/QLI2.0/IQ615/`
- 编译机：<build-server> (server4)
- pipewire 版本：1.6.6
- recipe 来源：`meta-openembedded/meta-multimedia/recipes-multimedia/pipewire/pipewire_1.6.6.bb`

## 关键路径

```
# work 目录（arch 是 armv8-2a，不是 aarch64）
build/tmp/work/armv8-2a-qcom-linux/pipewire/1.6.6/

# unpack 后 source 位置
build/tmp/work/armv8-2a-qcom-linux/pipewire/1.6.6/sources/pipewire-1.6.6/

# cp 出来的本地 source
IQ615/pipewire-source/

# bbappend 位置
meta-qcom/recipes-multimedia/pipewire/pipewire_%.bbappend
```

## bbappend 内容

```bitbake
# Use local pipewire source tree instead of fetching from upstream.
# Edit files under pipewire-source/ and run:
#   bitbake -c compile -f pipewire
inherit externalsrc
EXTERNALSRC = "${TOPDIR}/../pipewire-source"
EXTERNALSRC_BUILD = "${WORKDIR}/build"
```

## 操作步骤

```bash
# 1. 在 kas shell 里 unpack（如果还没编译过）
bitbake -c unpack pipewire

# 2. cp source 出来
cp -a build/tmp/work/armv8-2a-qcom-linux/pipewire/1.6.6/sources/pipewire-1.6.6 \
      pipewire-source

# 3. 创建 bbappend（用单引号 heredoc 保护变量）
mkdir -p meta-qcom/recipes-multimedia/pipewire
cat > meta-qcom/recipes-multimedia/pipewire/pipewire_%.bbappend << 'HEREDOC'
inherit externalsrc
EXTERNALSRC = "${TOPDIR}/../pipewire-source"
EXTERNALSRC_BUILD = "${WORKDIR}/build"
HEREDOC

# 4. cleansstate + compile
bitbake -c cleansstate pipewire
bitbake -c compile pipewire
```

## 成功日志特征

```
NOTE: pipewire: compiling from external source tree .../IQ615/build/../pipewire-source
NOTE: recipe pipewire-1.6.6-r0: task do_compile: Succeeded
NOTE: Tasks Summary: Attempted 2469 tasks of which 2461 didn't need to be rerun and all succeeded.
```

## 注意事项

- unpack 时如果全量编译正在跑，bitbake server 被占用，会显示 `Retrying server connection`，
  等全量编译完成后自动接上，不是报错。
- `EXTERNALSRC_BUILD = "${WORKDIR}/build"`（meson recipe），
  不是 kernel 用的 `${WORKDIR}/${BPN}-${PV}/build`。
