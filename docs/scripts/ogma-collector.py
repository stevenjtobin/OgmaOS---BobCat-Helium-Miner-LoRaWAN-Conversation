#!/usr/bin/env python3
# OgmaOS Listening Post collector: sniffs the Semtech UDP feed (lora_pkt_fwd -> :1700)
# on loopback (no deps), decodes LoRaWAN headers, records every frame into a persistent
# SQLite census DB, and fires a phone push (ntfy) the first time a new device is heard.
import socket, struct, json, base64, time, sqlite3, os, urllib.request

DB = "/root/ogma-data/ogma.db"
PORT = 1700
PRUNE_DAYS = 60
COMMIT_EVERY = 5
NTFY_TOPIC = "<YOUR_NTFY_TOPIC>"   # subscribe to this in the ntfy app; change to taste
NTFY_URL = "https://ntfy.sh/" + NTFY_TOPIC
ALERTS_ON = True
WATCH_VENDORS = {"Adeunis"}   # vendors we ALSO ping on REPEAT sightings (roaming field-test/coverage devices)
REPEAT_COOLDOWN = 120         # min seconds between repeat pings per device (anti-spam)

MTYPE = {0: "JoinRequest", 1: "JoinAccept", 2: "UnconfirmedUp", 3: "UnconfirmedDown",
         4: "ConfirmedUp", 5: "ConfirmedDown", 6: "RejoinRequest", 7: "Proprietary"}

OUI_V = {"a81758": "Elsys", "24e124": "Milesight", "a84041": "Dragino", "ac1f09": "RAK",
         "647fda": "Tektelic", "0018b2": "Adeunis", "0025ca": "Laird", "2cf7f1": "SenseCAP",
         "58a0cb": "Browan", "20635f": "Abeeway", "7076ff": "Kerlink"}
FP_V = {85: "Milesight", 5: "Elsys", 2: "Dragino", 100: "Browan", 102: "Browan",
        103: "Browan", 106: "Browan", 136: "Browan", 18: "Abeeway", 1: "Adeunis"}
def vendor(kind, dev, fport):
    if kind == "DevEUI" and dev and len(dev) >= 6:
        return OUI_V.get(dev[:6].lower(), "unknown")
    if kind == "DevAddr":
        return FP_V.get(fport, "unknown")
    return None

def hexrev(b):
    return b[::-1].hex()

def parse_phy(data_b64):
    try:
        d = base64.b64decode(data_b64)
    except Exception:
        return None, None, None, None, None
    if not d:
        return None, None, None, None, None
    mt = d[0] >> 5
    typ = MTYPE.get(mt, "MType%d" % mt)
    if mt in (2, 4) and len(d) >= 8:          # data uplink
        fopts = d[5] & 0x0F
        off = 8 + fopts
        fport = plen = None
        if len(d) > off + 4:                   # FPort + MIC present
            fport = d[off]
            plen = len(d) - off - 1 - 4         # FRMPayload byte count
        return typ, hexrev(d[1:5]), "DevAddr", fport, plen
    if mt == 0 and len(d) >= 17:               # join request
        return typ, hexrev(d[9:17]), "DevEUI", None, None
    return typ, None, None, None, None

def parse_datr(datr):
    try:
        if isinstance(datr, str) and datr.startswith("SF"):
            return int(datr[2:].split("BW")[0]), int(datr.split("BW")[1])
    except Exception:
        pass
    return None, None

def notify(dev, kind, typ, rssi, snr, freq, sf, vendor=None,
           title="New LoRaWAN device heard", tags="satellite", priority="default"):
    if not ALERTS_ON:
        return
    vtag = (" [%s]" % vendor) if (vendor and vendor != "unknown") else ""
    body = "%s %s%s\n%s dBm / SNR %s\n%.1f MHz  SF%s" % (kind or "device", dev, vtag, rssi, snr, freq or 0, sf)
    try:
        req = urllib.request.Request(NTFY_URL, data=body.encode("utf-8"), headers={
            "Title": title, "Tags": tags, "Priority": priority})
        urllib.request.urlopen(req, timeout=8).read()
    except Exception as e:
        print("ntfy-warn:", str(e)[:60], flush=True)

def opendb():
    c = sqlite3.connect(DB, timeout=10)
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA synchronous=NORMAL")
    c.execute("""CREATE TABLE IF NOT EXISTS frames(
        id INTEGER PRIMARY KEY, t INTEGER, type TEXT, dev TEXT, kind TEXT,
        freq REAL, sf INTEGER, bw INTEGER, rssi INTEGER, snr REAL, size INTEGER, chan INTEGER)""")
    c.execute("CREATE INDEX IF NOT EXISTS ix_t ON frames(t)")
    c.execute("CREATE INDEX IF NOT EXISTS ix_dev ON frames(dev)")
    for col in ("fport INTEGER", "plen INTEGER", "vendor TEXT"):   # add if upgrading an older DB
        try: c.execute("ALTER TABLE frames ADD COLUMN %s" % col)
        except Exception: pass
    c.commit()
    return c

def main():
    con = opendb()
    known = set(r[0] for r in con.execute("SELECT DISTINCT dev FROM frames WHERE dev IS NOT NULL AND dev!='-'"))
    last_alert = {}   # dev -> last ntfy timestamp (rate-limits repeat/tracking pings)
    print("ogma-collector: census %s, %d known devices, alerts->%s (watch=%s)" % (
        DB, len(known), NTFY_TOPIC, ",".join(sorted(WATCH_VENDORS)) or "-"), flush=True)
    s = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.htons(0x0003))
    s.bind(("lo", 0))
    last_commit = time.time(); last_prune = time.time()
    while True:
        try:
            raw = s.recv(65535)
        except Exception:
            time.sleep(0.2); continue
        try:
            if len(raw) >= 42 and struct.unpack("!H", raw[12:14])[0] == 0x0800 and raw[14 + 9] == 17:
                ihl = (raw[14] & 0x0F) * 4
                udp = 14 + ihl
                if PORT in (struct.unpack("!H", raw[udp + 2:udp + 4])[0], struct.unpack("!H", raw[udp:udp + 2])[0]):
                    payload = raw[udp + 8:]
                    if len(payload) >= 12 and payload[3] == 0x00:
                        j = json.loads(payload[12:].decode("utf-8", "replace"))
                        now = int(time.time())
                        for p in (j.get("rxpk") or []):
                            sf, bw = parse_datr(p.get("datr"))
                            typ, dev, kind, fport, plen = parse_phy(p.get("data", ""))
                            vd = vendor(kind, dev, fport)
                            con.execute(
                                "INSERT INTO frames(t,type,dev,kind,freq,sf,bw,rssi,snr,size,chan,fport,plen,vendor) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                                (now, typ, dev, kind, p.get("freq"), sf, bw, p.get("rssi"), p.get("lsnr"), p.get("size"), p.get("chan"), fport, plen, vd))
                            print("FRAME %s %s rssi=%s snr=%s %.1fMHz SF%s" % (typ, dev, p.get("rssi"), p.get("lsnr"), p.get("freq") or 0, sf), flush=True)
                            if dev and dev != "-":
                                if dev not in known:
                                    known.add(dev)
                                    con.commit()
                                    notify(dev, kind, typ, p.get("rssi"), p.get("lsnr"), p.get("freq"), sf, vendor=vd)
                                    last_alert[dev] = now
                                    print("NEW DEVICE -> alert:", dev, flush=True)
                                elif vd in WATCH_VENDORS and (now - last_alert.get(dev, 0)) >= REPEAT_COOLDOWN:
                                    notify(dev, kind, typ, p.get("rssi"), p.get("lsnr"), p.get("freq"), sf,
                                           vendor=vd, title="Tracking: %s device nearby" % vd, tags="round_pushpin")
                                    last_alert[dev] = now
                                    print("REPEAT -> alert:", dev, vd, flush=True)
        except Exception as e:
            print("parse-warn:", str(e)[:60], flush=True)
        now = time.time()
        if now - last_commit > COMMIT_EVERY:
            try: con.commit()
            except Exception: pass
            last_commit = now
        if now - last_prune > 3600:
            try:
                con.execute("DELETE FROM frames WHERE t < ?", (int(now) - PRUNE_DAYS * 86400,))
                con.commit()
            except Exception: pass
            last_prune = now

if __name__ == "__main__":
    main()
