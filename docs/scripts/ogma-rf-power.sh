#!/bin/sh
# Bobcat 29X concentrator bring-up (generic sx1302_hal omits this).
# GPIO147 (gpio4.19) enables the Bobcat's RF FRONT-END / LNA+PA amplifier rail.
# Without it the receive front-end is unpowered -> concentrator hears NOTHING.
# (lora_3v3 rail on GPIO121 is handled by the DT regulator; GPIO149 = reset.)
FEM=147
[ -d /sys/class/gpio/gpio$FEM ] || echo $FEM > /sys/class/gpio/export
echo out > /sys/class/gpio/gpio$FEM/direction
echo 1   > /sys/class/gpio/gpio$FEM/value
sleep 0.2
sh /root/sx1302_hal/packet_forwarder/reset_lgw.sh start
exit 0
