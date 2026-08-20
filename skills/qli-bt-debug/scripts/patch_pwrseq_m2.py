#!/usr/bin/env python3
"""
Add trace_printk log points to pwrseq-pcie-m2.c for BT M.2 bringup debug.

Usage:
  # Set FILE path below to match your kernel-source location, then:
  python3 patch_pwrseq_m2.py

  # Or run remotely:
  scp patch_pwrseq_m2.py <BUILD_SERVER>:/tmp/
  ssh <BUILD_SERVER> "python3 /tmp/patch_pwrseq_m2.py"

Adds 13 trace_printk points covering the full pwrseq power-on sequence.

Read log on target (enable tracing first):
  echo 1 > /sys/kernel/debug/tracing/tracing_on
  cat /sys/kernel/debug/tracing/trace | grep "PWRSEQ_M2"
  cat /sys/kernel/debug/tracing/trace_pipe | grep "PWRSEQ_M2"   # live

Requires CONFIG_FTRACE=y + CONFIG_DYNAMIC_FTRACE=y in bsp-additions.cfg.
"""

# Edit this path to match your kernel-source location:
FILE = "/path/to/kernel-source/drivers/power/sequencing/pwrseq-pcie-m2.c"

with open(FILE, 'r') as f:
    content = f.read()

patches = [
    # 1. Add trace.h include after the last existing include
    (
        "add_trace_include",
        "#include <linux/slab.h>",
        "#include <linux/slab.h>\n#include <linux/trace_printk.h>",
    ),

    # 2. vregs_enable — regulator bulk enable
    (
        "vregs_enable",
        "static int pwrseq_pcie_m2_vregs_enable(struct pwrseq_device *pwrseq)\n{\n\tstruct pwrseq_pcie_m2_ctx *ctx = pwrseq_device_get_drvdata(pwrseq);\n\n\treturn regulator_bulk_enable(ctx->num_vregs, ctx->regs);",
        "static int pwrseq_pcie_m2_vregs_enable(struct pwrseq_device *pwrseq)\n{\n\tstruct pwrseq_pcie_m2_ctx *ctx = pwrseq_device_get_drvdata(pwrseq);\n\tint ret;\n\n\ttrace_printk(\"PWRSEQ_M2 VREGS_ENABLE start: num_vregs=%zu\\n\", ctx->num_vregs);\n\tret = regulator_bulk_enable(ctx->num_vregs, ctx->regs);\n\ttrace_printk(\"PWRSEQ_M2 VREGS_ENABLE done: ret=%d\\n\", ret);\n\treturn ret;",
    ),

    # 3. vregs_disable — regulator bulk disable
    (
        "vregs_disable",
        "static int pwrseq_pcie_m2_vregs_disable(struct pwrseq_device *pwrseq)\n{\n\tstruct pwrseq_pcie_m2_ctx *ctx = pwrseq_device_get_drvdata(pwrseq);\n\n\treturn regulator_bulk_disable(ctx->num_vregs, ctx->regs);",
        "static int pwrseq_pcie_m2_vregs_disable(struct pwrseq_device *pwrseq)\n{\n\tstruct pwrseq_pcie_m2_ctx *ctx = pwrseq_device_get_drvdata(pwrseq);\n\tint ret;\n\n\ttrace_printk(\"PWRSEQ_M2 VREGS_DISABLE start\\n\");\n\tret = regulator_bulk_disable(ctx->num_vregs, ctx->regs);\n\ttrace_printk(\"PWRSEQ_M2 VREGS_DISABLE done: ret=%d\\n\", ret);\n\treturn ret;",
    ),

    # 4. uart_enable — w_disable2 GPIO set low (UART enabled)
    (
        "uart_enable",
        "static int pwrseq_pci_m2_e_uart_enable(struct pwrseq_device *pwrseq)\n{\n\tstruct pwrseq_pcie_m2_ctx *ctx = pwrseq_device_get_drvdata(pwrseq);\n\n\treturn gpiod_set_value_cansleep(ctx->w_disable2_gpio, 0);",
        "static int pwrseq_pci_m2_e_uart_enable(struct pwrseq_device *pwrseq)\n{\n\tstruct pwrseq_pcie_m2_ctx *ctx = pwrseq_device_get_drvdata(pwrseq);\n\tint ret;\n\n\ttrace_printk(\"PWRSEQ_M2 UART_ENABLE: w_disable2 -> 0 (UART enabled)\\n\");\n\tret = gpiod_set_value_cansleep(ctx->w_disable2_gpio, 0);\n\ttrace_printk(\"PWRSEQ_M2 UART_ENABLE done: ret=%d\\n\", ret);\n\treturn ret;",
    ),

    # 5. uart_disable — w_disable2 GPIO set high (UART disabled)
    (
        "uart_disable",
        "static int pwrseq_pci_m2_e_uart_disable(struct pwrseq_device *pwrseq)\n{\n\tstruct pwrseq_pcie_m2_ctx *ctx = pwrseq_device_get_drvdata(pwrseq);\n\n\treturn gpiod_set_value_cansleep(ctx->w_disable2_gpio, 1);",
        "static int pwrseq_pci_m2_e_uart_disable(struct pwrseq_device *pwrseq)\n{\n\tstruct pwrseq_pcie_m2_ctx *ctx = pwrseq_device_get_drvdata(pwrseq);\n\tint ret;\n\n\ttrace_printk(\"PWRSEQ_M2 UART_DISABLE: w_disable2 -> 1 (UART disabled)\\n\");\n\tret = gpiod_set_value_cansleep(ctx->w_disable2_gpio, 1);\n\ttrace_printk(\"PWRSEQ_M2 UART_DISABLE done: ret=%d\\n\", ret);\n\treturn ret;",
    ),

    # 6. pcie_enable — w_disable1 GPIO set low (PCIe enabled)
    (
        "pcie_enable",
        "static int pwrseq_pci_m2_e_pcie_enable(struct pwrseq_device *pwrseq)\n{\n\tstruct pwrseq_pcie_m2_ctx *ctx = pwrseq_device_get_drvdata(pwrseq);\n\n\treturn gpiod_set_value_cansleep(ctx->w_disable1_gpio, 0);",
        "static int pwrseq_pci_m2_e_pcie_enable(struct pwrseq_device *pwrseq)\n{\n\tstruct pwrseq_pcie_m2_ctx *ctx = pwrseq_device_get_drvdata(pwrseq);\n\tint ret;\n\n\ttrace_printk(\"PWRSEQ_M2 PCIE_ENABLE: w_disable1 -> 0 (PCIe enabled)\\n\");\n\tret = gpiod_set_value_cansleep(ctx->w_disable1_gpio, 0);\n\ttrace_printk(\"PWRSEQ_M2 PCIE_ENABLE done: ret=%d\\n\", ret);\n\treturn ret;",
    ),

    # 7. pcie_disable — w_disable1 GPIO set high (PCIe disabled)
    (
        "pcie_disable",
        "static int pwrseq_pci_m2_e_pcie_disable(struct pwrseq_device *pwrseq)\n{\n\tstruct pwrseq_pcie_m2_ctx *ctx = pwrseq_device_get_drvdata(pwrseq);\n\n\treturn gpiod_set_value_cansleep(ctx->w_disable1_gpio, 1);",
        "static int pwrseq_pci_m2_e_pcie_disable(struct pwrseq_device *pwrseq)\n{\n\tstruct pwrseq_pcie_m2_ctx *ctx = pwrseq_device_get_drvdata(pwrseq);\n\tint ret;\n\n\ttrace_printk(\"PWRSEQ_M2 PCIE_DISABLE: w_disable1 -> 1 (PCIe disabled)\\n\");\n\tret = gpiod_set_value_cansleep(ctx->w_disable1_gpio, 1);\n\ttrace_printk(\"PWRSEQ_M2 PCIE_DISABLE done: ret=%d\\n\", ret);\n\treturn ret;",
    ),

    # 8. notify — BUS_NOTIFY_ADD_DEVICE: PCI device matched
    (
        "notify_add",
        "\tcase BUS_NOTIFY_ADD_DEVICE:\n\t\tif (pci_match_id(pwrseq_m2_pci_ids, pdev)) {\n\t\t\tret = pwrseq_pcie_m2_create_serdev_one(ctx, pdev);",
        "\tcase BUS_NOTIFY_ADD_DEVICE:\n\t\tif (pci_match_id(pwrseq_m2_pci_ids, pdev)) {\n\t\t\ttrace_printk(\"PWRSEQ_M2 NOTIFY ADD_DEVICE: pci=%s\\n\", pci_name(pdev));\n\t\t\tret = pwrseq_pcie_m2_create_serdev_one(ctx, pdev);",
    ),

    # 9. notify — BUS_NOTIFY_REMOVED_DEVICE
    (
        "notify_remove",
        "\tcase BUS_NOTIFY_REMOVED_DEVICE:\n\t\tif (pci_match_id(pwrseq_m2_pci_ids, pdev))\n\t\t\tpwrseq_pcie_m2_remove_serdev(ctx, pdev);",
        "\tcase BUS_NOTIFY_REMOVED_DEVICE:\n\t\tif (pci_match_id(pwrseq_m2_pci_ids, pdev)) {\n\t\t\ttrace_printk(\"PWRSEQ_M2 NOTIFY REMOVED_DEVICE: pci=%s\\n\", pci_name(pdev));\n\t\t\tpwrseq_pcie_m2_remove_serdev(ctx, pdev);\n\t\t}",
    ),

    # 10. create_serdev_one — serdev_device_add success
    (
        "serdev_add",
        "\tret = serdev_device_add(pci_dev->serdev);\n\tif (ret) {\n\t\tdev_err(dev, \"Failed to add serdev for PCI device (%s): %d\\n\",\n\t\t\tpci_name(pdev), ret);\n\t\tgoto err_free_dt_node;\n\t}\n\n\tserdev_controller_put(serdev_ctrl);",
        "\tret = serdev_device_add(pci_dev->serdev);\n\tif (ret) {\n\t\tdev_err(dev, \"Failed to add serdev for PCI device (%s): %d\\n\",\n\t\t\tpci_name(pdev), ret);\n\t\tgoto err_free_dt_node;\n\t}\n\ttrace_printk(\"PWRSEQ_M2 SERDEV_ADD OK: pci=%s\\n\", pci_name(pdev));\n\n\tserdev_controller_put(serdev_ctrl);",
    ),

    # 11. probe — entry
    (
        "probe_entry",
        "static int pwrseq_pcie_m2_probe(struct platform_device *pdev)\n{\n\tstruct device *dev = &pdev->dev;\n\tstruct pwrseq_pcie_m2_ctx *ctx;",
        "static int pwrseq_pcie_m2_probe(struct platform_device *pdev)\n{\n\tstruct device *dev = &pdev->dev;\n\tstruct pwrseq_pcie_m2_ctx *ctx;\n\n\ttrace_printk(\"PWRSEQ_M2 PROBE: dev=%s\\n\", dev_name(dev));",
    ),

    # 12. probe — done (just before return 0 at end of probe)
    (
        "probe_done",
        "\t/*\n\t * Register a notifier for creating protocol devices for\n\t * non-discoverable busses like UART.\n\t */\n\tret = pwrseq_pcie_m2_register_notifier(ctx);\n\tif (ret)\n\t\tgoto err_remove_serdev;\n\n\treturn 0;",
        "\t/*\n\t * Register a notifier for creating protocol devices for\n\t * non-discoverable busses like UART.\n\t */\n\tret = pwrseq_pcie_m2_register_notifier(ctx);\n\tif (ret)\n\t\tgoto err_remove_serdev;\n\n\ttrace_printk(\"PWRSEQ_M2 PROBE done OK: dev=%s\\n\", dev_name(dev));\n\treturn 0;",
    ),

    # 13. remove — entry
    (
        "remove_entry",
        "static void pwrseq_pcie_m2_remove(struct platform_device *pdev)\n{\n\tstruct pwrseq_pcie_m2_ctx *ctx = platform_get_drvdata(pdev);\n\n\tbus_unregister_notifier(&pci_bus_type, &ctx->nb);",
        "static void pwrseq_pcie_m2_remove(struct platform_device *pdev)\n{\n\tstruct pwrseq_pcie_m2_ctx *ctx = platform_get_drvdata(pdev);\n\n\ttrace_printk(\"PWRSEQ_M2 REMOVE: dev=%s\\n\", dev_name(&pdev->dev));\n\tbus_unregister_notifier(&pci_bus_type, &ctx->nb);",
    ),
]

for name, old, new in patches:
    if old not in content:
        print(f"ERROR: anchor not found [{name}]")
        print(f"  Expected:\n{repr(old[:120])}")
        raise SystemExit(1)
    content = content.replace(old, new, 1)
    print(f"  applied: {name}")

with open(FILE, 'w') as f:
    f.write(content)

print(f"\nDone. {len(patches)} patches applied.")
