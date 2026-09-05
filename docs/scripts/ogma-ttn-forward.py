#!/usr/bin/env python3
# OgmaOS Semtech-UDP fan-out: lora_pkt_fwd -> :1710 -> {local ChirpStack :1700, TTN EU1 :1700}
# Uplink to BOTH networks; downlink authority stays with local ChirpStack (TTN PULL_RESP dropped).
# Dependency-free. Reversible: point lora_pkt_fwd back at :1700 and stop this service.
import socket, time

LISTEN = ("0.0.0.0", 1710)
CHIRP = ("127.0.0.1", 1700)
TTN_HOST = "eu1.cloud.thethings.network"
TTN_PORT = 1700
PULL_RESP = 0x03  # downlink from a server -> gateway

def resolve_ttn():
    try:
        return socket.gethostbyname(TTN_HOST)
    except Exception:
        return None

def main():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(LISTEN)
    ttn_ip = resolve_ttn()
    last_dns = time.time()
    gw = None  # learned address of the local packet forwarder
    print("ogma-ttn-forward: :1710 -> ChirpStack %s + TTN %s(%s):%d" % (CHIRP, TTN_HOST, ttn_ip, TTN_PORT), flush=True)
    while True:
        try:
            data, addr = s.recvfrom(4096)
        except Exception:
            time.sleep(0.2); continue
        # refresh TTN DNS occasionally
        if time.time() - last_dns > 600:
            ip = resolve_ttn(); ttn_ip = ip or ttn_ip; last_dns = time.time()
        try:
            if addr[0] == "127.0.0.1" and addr[1] == CHIRP[1]:
                # reply from local ChirpStack (incl. downlink) -> gateway
                if gw: s.sendto(data, gw)
            elif addr[0] == "127.0.0.1":
                # from the local packet forwarder -> fan out to both networks
                gw = addr
                s.sendto(data, CHIRP)
                if ttn_ip:
                    s.sendto(data, (ttn_ip, TTN_PORT))
            else:
                # reply from TTN -> gateway, but never let TTN drive downlink
                if gw and not (len(data) > 3 and data[3] == PULL_RESP):
                    s.sendto(data, gw)
        except Exception as e:
            print("fanout-warn:", str(e)[:60], flush=True)

if __name__ == "__main__":
    main()
