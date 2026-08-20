# externalsrc Pitfalls

Common failures when using `externalsrc` for QLI kernel development.

---

## 1. Wrong EXTERNALSRC_BUILD path

**Symptom:** Build succeeds but `bitbake -e` shows the old (fetched) kernel
path; modules don't match the running kernel.

**Cause:** Normal recipes use `${WORKDIR}/build` for `EXTERNALSRC_BUILD`,
but the kernel recipe requires:
```
EXTERNALSRC_BUILD = "${WORKDIR}/${BPN}-${PV}/build"
```

Using `${WORKDIR}/build` causes BitBake to build in the wrong directory;
no error is emitted, but the build output is from the fetched sources, not
your local tree.

**Fix:** Use the exact `${WORKDIR}/${BPN}-${PV}/build` form.

---

## 2. symlink instead of cp -a

**Symptom:** After `bitbake -c cleansstate`, the kernel source directory
disappears or is empty.

**Cause:** `cleansstate` deletes `build/tmp/work-shared/linux-qcom-*/` —
if `kernel-source/` is a symlink into `work-shared`, it now points at nothing.

**Fix:** Always use `cp -a`, never `ln -s`:
```bash
cp -a build/tmp/work-shared/linux-qcom-next-*/linux-qcom-next-*/ kernel-source/
```

---

## 3. CONFIG_LOCALVERSION_AUTO missing

**Symptom:** `insmod` fails with `Invalid module format` or `version magic
'6.13.0-rc3+' should be '6.13.0-rc3'`.

**Cause:** Without `CONFIG_LOCALVERSION_AUTO=n`, the kernel appends a git
hash to its version string. Modules are compiled against the hash-less
version, but the running kernel reports the hash-appended version.

**Fix:** Add `CONFIG_LOCALVERSION_AUTO=n` to `bsp-additions.cfg` and rebuild.

---

## 4. qcom-metadata.dtb missing after cleansstate

**Symptom:** Board boots but device tree bundle is missing; errors like
`qcom-metadata.dtb: No such file`.

**Cause:** `cleansstate` on the kernel recipe also removes intermediate DTB
metadata artifacts.

**Fix:**
```bash
bitbake -c cleansstate qcom-dtb-metadata && bitbake qcom-dtb-metadata
```

---

## 5. Forgetting cleansstate when first switching to externalsrc

**Symptom:** BitBake still uses the old fetched source; edits to
`kernel-source/` have no effect.

**Cause:** BitBake's task cache still points at the fetched tree. The first
switch to externalsrc requires `cleansstate` to invalidate the cache.

**Fix:** Always run `bitbake -c cleansstate <kernel-recipe>` once after
adding `EXTERNALSRC` to the `.bb` file.

---

## 6. Editing the wrong .bb file

**Symptom:** externalsrc config has no effect.

**Cause:** QLI 0.0 uses `linux-qcom-next_git.bb` and QLI 2.0 uses
`linux-qcom_6.18.bb`. Editing one when you're building the other has no effect.

**Check:**
```bash
bitbake -e virtual/kernel | grep "^PN="
# Tells you the actual recipe name being used
```

---

## 7. TOPDIR path assumption

`EXTERNALSRC = "${TOPDIR}/../kernel-source"` assumes the kernel-source
directory is one level above the `build/` directory (i.e. at workspace root).
If your workspace layout differs, adjust accordingly.

`${TOPDIR}` = `<WORKSPACE>/build` by default in a kas/oe-core setup.
