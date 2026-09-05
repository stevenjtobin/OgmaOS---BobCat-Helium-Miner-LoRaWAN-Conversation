# Device‑tree fix — `lora-3v3-regulator`

**Why:** on the Bobcat 29X the `lora-3v3-regulator` node has its `vin-supply` mis‑pointed at a pinctrl node, so it fails to probe (`-EPROBE_DEFER / -517`) and the SX1302's RF section is never powered. Repointing `vin-supply` to the always‑on `vcc3v3_sys` rail fixes it. **This is the one board‑specific step — back up first.**

## Method A — device‑tree overlay (recommended, portable, reversible)

```bash
# 1. compile the overlay
sudo apt install -y device-tree-compiler
sudo dtc -@ -I dts -O dtb -o /boot/overlay-user/lora-3v3-fix.dtbo lora-3v3-fix.dts

# 2. enable it (Armbian) — appends to the boot env
grep -q lora-3v3-fix /boot/armbianEnv.txt || \
  echo "user_overlays=lora-3v3-fix" | sudo tee -a /boot/armbianEnv.txt

# 3. reboot and confirm the rail is enabled
sudo reboot
# after reboot:
sudo cat /sys/kernel/debug/regulator/regulator_summary | grep lora
```
Overlay paths/mechanism vary by distro — on non‑Armbian, add the `.dtbo` to your bootloader's overlay list (`extlinux.conf` `fdtoverlays`, U‑Boot, etc.).

## Method B — patch the base DTB directly (if overlays aren't set up)

```bash
DTB=/boot/dtb/rockchip/rk3566-bobcat-29x.dtb   # adjust to your board's dtb
sudo cp "$DTB" "$DTB.orig"                      # BACK UP
# decompile, edit the lora-3v3-regulator's vin-supply to &vcc3v3_sys, recompile:
dtc -I dtb -O dts "$DTB" -o /tmp/board.dts
#   -> edit /tmp/board.dts: in node `lora-3v3-regulator { ... }` set
#      vin-supply = <&vcc3v3_sys>;  (the phandle for vcc3v3_sys on your tree)
sudo dtc -I dts -O dtb /tmp/board.dts -o "$DTB"
sudo reboot
```

## Rollback
```bash
# Method A: remove the user_overlays line from /boot/armbianEnv.txt, reboot.
# Method B: sudo cp /boot/dtb/rockchip/rk3566-bobcat-29x.dtb.orig \
#             /boot/dtb/rockchip/rk3566-bobcat-29x.dtb && sudo reboot
```

## Verify it worked
```bash
sudo cat /sys/kernel/debug/regulator/regulator_summary | grep -i lora
# expect: lora_3v3 ... enabled ... 3300mV
```
Once the rail is up, the `ogma-rf-power.sh` script (front‑end/FEM enable) + the packet forwarder will start hearing packets.
