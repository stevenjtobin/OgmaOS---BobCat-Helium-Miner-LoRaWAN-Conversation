# docs — full configuration reference

The **real, working files** from a running OgmaOS Bobcat gateway, **with secrets removed**. Copy them onto your own box and set your own values (search for `<PLACEHOLDER>` — mainly `<YOUR_NTFY_TOPIC>`).

> Paths below assume the layout this build uses: scripts in `/root`, the packet forwarder in `/root/sx1302_hal`, unit files in `/etc/systemd/system`. Adjust to taste.

## Install order

### 1. RF bring‑up + gateway (the part that makes a Bobcat actually receive)
```bash
# the front-end power script (see the two-fixes section of the main README)
sudo install -m 755 scripts/ogma-rf-power.sh /root/sx1302_hal/ogma-rf-power.sh

# the packet-forwarder service + its ExecStartPre drop-in
sudo cp services/ogma-gateway.service /etc/systemd/system/
sudo mkdir -p /etc/systemd/system/ogma-gateway.service.d
sudo cp services/10-rf-power.conf /etc/systemd/system/ogma-gateway.service.d/
sudo systemctl daemon-reload && sudo systemctl enable --now ogma-gateway
journalctl -u ogma-gateway -f      # wait for "concentrator started" then RF packets
```

### 2. Census collector + phone alerts
```bash
sudo cp scripts/ogma-collector.py /root/
# edit /root/ogma-collector.py -> set NTFY_TOPIC = "<your private ntfy topic>"
sudo cp services/ogma-collector.service /etc/systemd/system/
sudo systemctl enable --now ogma-collector
```

### 3. (Optional) Fan‑out to The Things Network
Point the packet forwarder at `:1710` (see [`config/global_conf.md`](config/global_conf.md)), then:
```bash
sudo cp scripts/ogma-ttn-forward.py /root/
sudo cp services/ogma-ttn-forward.service /etc/systemd/system/
sudo systemctl enable --now ogma-ttn-forward
```

### 4. Dashboard
```bash
sudo cp services/ogma-panel.service /etc/systemd/system/   # runs /root/ogma-panel.py on :8088
sudo systemctl enable --now ogma-panel
```

### 5. Self‑healing watchdog
```bash
sudo cp scripts/ogma-rx-watchdog.sh /root/ && sudo chmod +x /root/ogma-rx-watchdog.sh
# edit the ntfy topic inside it
sudo cp services/ogma-rx-watchdog.service services/ogma-rx-watchdog.timer /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now ogma-rx-watchdog.timer
```

## File map

| File | Role |
|---|---|
| `scripts/ogma-rf-power.sh` | Drives the FEM/LNA enable GPIO + resets the concentrator (the RX fix) |
| `scripts/ogma-collector.py` | Sniffs loopback Semtech‑UDP → SQLite census, vendor fingerprint, ntfy alerts |
| `scripts/ogma-ttn-forward.py` | Dependency‑free Semtech‑UDP fan‑out → ChirpStack + TTN (uplink only) |
| `scripts/ogma-rx-watchdog.sh` | Detects an RX stall, soft‑restarts once, then alerts you to mains‑cycle |
| `services/*.service`, `*.timer` | systemd units for each of the above |
| `config/global_conf.md` | Notes on the EU868 packet‑forwarder config + the fan‑out port change |

## Not included here (by design)
- **ChirpStack** — use the upstream [`chirpstack/chirpstack-docker`](https://github.com/chirpstack/chirpstack-docker) compose stack.
- **Grafana** — standard container + the `frser-sqlite-datasource` plugin pointed at the census DB.
- **The dashboard's `ogma-panel.py`** — large and site‑specific; the service unit is here, the app you tailor to your own layout.
- **Any secrets** — ntfy topic, passwords, Tailscale hostnames. Set your own.
