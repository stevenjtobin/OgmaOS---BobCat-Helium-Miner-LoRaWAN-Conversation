# Packet‑forwarder config (`global_conf.json`)

Start from the Semtech `sx1302_hal` EU868 sample:

```bash
cd /root/sx1302_hal/packet_forwarder
cp global_conf.json.sx1250.EU868 global_conf.json
```

## SPI device
Set `com_path` to your board's concentrator SPI device (this build uses `/dev/spidev0.0`).

## Radio / channel plan (EU868)
The sample already configures the standard 8‑channel EU868 plan — two SX1250 radios (centres ~867.5 and 868.5 MHz), channels 0–7 at 125 kHz, SF5–SF12. You normally don't need to touch this.

## `gateway_conf` — where uplinks go
By default the forwarder sends to `:1700` (a local network server). This build inserts a small **fan‑out** so uplinks reach **both** a local ChirpStack **and** The Things Network. To enable it, point the forwarder at the fan‑out's port instead:

```jsonc
"gateway_conf": {
    "server_address": "localhost",
    "serv_port_up":   1710,   // was 1700 — now the ogma-ttn-forward fan-out
    "serv_port_down": 1710,
    // ...
}
```

`ogma-ttn-forward.py` then relays:
- **→ ChirpStack** `127.0.0.1:1700` (full uplink + downlink authority stays local)
- **→ TTN** `eu1.cloud.thethings.network:1700` (**uplink only** — TTN downlinks are dropped so it can't drive your radio)

**To disable TTN and go local‑only again:** set `serv_port_up/down` back to `1700` and stop `ogma-ttn-forward`. Fully reversible.

## Gateway EUI
The forwarder derives the gateway EUI from the concentrator (e.g. `0016c00100000000`‑style). Register **that** EUI in ChirpStack (and/or TTN) as your gateway.
```
