#!/bin/bash
# ogma-rx-watchdog: detect SX1302 RX stall (no RF packets heard for WINDOW), attempt ONE
# soft gateway restart, then escalate via ntfy. NOTE: the known failure mode needs a
# physical MAINS power-cycle to clear - software cannot do that - so we alert the human.
WINDOW="40 min ago"
STATE=/run/ogma-rx-watchdog.state
now=$(date +%s)

# count report intervals in WINDOW that heard >0 RF packets (independent of the collector)
rx_hits=$(journalctl -u ogma-gateway --since "$WINDOW" --no-pager 2>/dev/null \
          | grep "RF packets received by concentrator" | grep -vcE ": 0$")

push(){ python3 - "$1" "$2" "$3" "$4" <<'PY'
import sys, urllib.request
t,tg,pr,m = sys.argv[1:5]
try:
    urllib.request.urlopen(urllib.request.Request(
        "https://ntfy.sh/<YOUR_NTFY_TOPIC>", data=m.encode(),
        headers={"Title": t, "Tags": tg, "Priority": pr}), timeout=10).read()
except Exception as e: print("ntfy", e)
PY
}

if [ "${rx_hits:-0}" -gt 0 ]; then
  rm -f "$STATE" 2>/dev/null          # healthy -> reset stall state
  exit 0
fi

# --- stalled: no RF packets heard in WINDOW ---
phase=$(cat "$STATE" 2>/dev/null)
if [ -z "$phase" ]; then
  logger -t ogma-rx-watchdog "RX stall: 0 RF packets in '$WINDOW' -> soft restart ogma-gateway"
  systemctl restart ogma-gateway
  echo "restarted:$now" > "$STATE"
  push "Bobcat RX stalled" "warning" "high" \
       "No RF packets for 40+ min. Auto-restarted the gateway. If still nothing shortly, it needs a MAINS power-cycle (unplug ~30s) - a soft restart usually won't fix this one."
  exit 0
fi
if [ "${phase%%:*}" = "restarted" ] && [ $(( now - ${phase#*:} )) -gt 1200 ]; then
  logger -t ogma-rx-watchdog "RX still stalled 20min after restart -> escalate"
  echo "alerted:$now" > "$STATE"
  push "Bobcat RX STILL down" "rotating_light" "urgent" \
       "Still deaf 20 min after an auto-restart. Needs a PHYSICAL mains power-cycle: unplug the Bobcat ~30s, plug back in. (Confirmed: only a cold power-cycle clears this fault.)"
fi
exit 0
