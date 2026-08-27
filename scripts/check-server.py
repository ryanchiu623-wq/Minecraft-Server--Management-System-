#!/usr/bin/env python3
"""Health-check the Minecraft server end to end - no game client needed.

Speaks both status protocols directly:
  Java    TCP  handshake(state=1) + status request  -> JSON
  Bedrock UDP  RakNet unconnected ping              -> semicolon-separated MOTD

Checks, in order: the local server, DNS, the public tunnels, an outside
vantage point, and the published map.

Usage:  python check-server.py
"""

import json
import os
import socket
import struct
import sys
import time
import urllib.request

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# This module is also imported by web-console.py and console-gui.py through a
# file path, so its own directory is not necessarily on sys.path yet.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import settings  # noqa: E402

JAVA_HOST = settings.require("java", "host")
BE_HOST = settings.require("bedrock", "host")
BE_PORT = settings.get("bedrock", "tunnelPort", default=19132)
MAP_URL = settings.get("mapUrl", default="")
JAVA_LOCAL_PORT = settings.get("java", "localPort", default=25565)
BE_LOCAL_PORT = settings.get("bedrock", "localPort", default=19132)

OK, FAIL, WARN = "OK  ", "FAIL", "WARN"


# ---------------------------------------------------------------- Java status
def _varint(n):
    out = b""
    while True:
        b = n & 0x7F
        n >>= 7
        out += bytes([b | (0x80 if n else 0)])
        if not n:
            return out


def _read_varint(sock):
    n = shift = 0
    while True:
        b = sock.recv(1)
        if not b:
            raise IOError("connection closed")
        b = b[0]
        n |= (b & 0x7F) << shift
        if not b & 0x80:
            return n
        shift += 7


def java_status(host, port, timeout=8):
    """Return (ok, detail, latency_ms)."""
    started = time.time()
    try:
        sock = socket.create_connection((host, port), timeout=timeout)
    except Exception as exc:
        return False, f"連不上 ({type(exc).__name__})", None

    try:
        with sock:
            hs = (b"\x00" + _varint(775) + _varint(len(host)) + host.encode()
                  + struct.pack("!H", port) + b"\x01")
            sock.sendall(_varint(len(hs)) + hs)
            sock.sendall(_varint(1) + b"\x00")

            _read_varint(sock)          # packet length
            _read_varint(sock)          # packet id
            n = _read_varint(sock)      # json length
            buf = b""
            while len(buf) < n:
                chunk = sock.recv(n - len(buf))
                if not chunk:
                    break
                buf += chunk

        latency = int((time.time() - started) * 1000)
        d = json.loads(buf.decode("utf-8"))
        ver = d.get("version", {}).get("name", "?")
        pl = d.get("players", {})
        return True, f"{ver}  {pl.get('online', '?')}/{pl.get('max', '?')} 人", latency
    except Exception as exc:
        return False, f"回應無法解析 ({type(exc).__name__})", None


# ------------------------------------------------------------- Bedrock status
MAGIC = bytes.fromhex("00ffff00fefefefefdfdfdfd12345678")


def bedrock_status(host, port, timeout=6):
    started = time.time()
    pkt = (b"\x01" + struct.pack(">Q", int(time.time() * 1000)) + MAGIC
           + struct.pack(">Q", 0x1234567890ABCDEF))
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(timeout)
    try:
        s.sendto(pkt, (host, port))
        data, _ = s.recvfrom(4096)
    except socket.timeout:
        return False, "逾時，沒有回應", None
    except Exception as exc:
        return False, f"連不上 ({type(exc).__name__})", None
    finally:
        s.close()

    if not data or data[0] != 0x1C:
        return False, "非預期的封包", None

    latency = int((time.time() - started) * 1000)
    off = 1 + 8 + 8 + 16
    strlen = struct.unpack(">H", data[off:off + 2])[0]
    fields = data[off + 2:off + 2 + strlen].decode("utf-8", "replace").split(";")
    ver = fields[3] if len(fields) > 3 else "?"
    online = fields[4] if len(fields) > 4 else "?"
    mx = fields[5] if len(fields) > 5 else "?"
    return True, f"{ver}  {online}/{mx} 人", latency


# ------------------------------------------------------------------ DNS / web
def resolve(host):
    try:
        return sorted({r[4][0] for r in socket.getaddrinfo(host, None)})
    except Exception as exc:
        return [f"解析失敗 ({type(exc).__name__})"]


def http_status(url, timeout=15):
    started = time.time()
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "mc-healthcheck"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return True, f"HTTP {resp.status}", int((time.time() - started) * 1000)
    except Exception as exc:
        return False, f"{type(exc).__name__}", None


def external_view(host, timeout=25):
    """Ask a third party - the only way to see the tunnel from outside."""
    url = f"https://api.mcstatus.io/v2/status/java/{host}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "mc-healthcheck"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            d = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        return False, f"查詢失敗 ({type(exc).__name__})", None

    if not d.get("online"):
        return False, "外部看到的是離線", None
    ver = (d.get("version") or {}).get("name_clean", "?")
    pl = d.get("players") or {}
    return True, f"{ver}  {pl.get('online', '?')}/{pl.get('max', '?')} 人", None


# --------------------------------------------------------------------- report
def row(label, ok, detail, latency=None):
    mark = OK if ok else FAIL
    lat = f"{latency} ms" if latency is not None else ""
    print(f"  [{mark}] {label:<34} {detail:<26} {lat}")
    return ok


def main():
    print()
    print("Minecraft 伺服器健康檢查   " + time.strftime("%Y-%m-%d %H:%M:%S"))
    print("=" * 78)
    results = []

    print("\n本機（伺服器本身活著嗎）")
    ok, detail, lat = java_status("127.0.0.1", 25565)
    results.append(row("Java  127.0.0.1:25565", ok, detail, lat))
    ok, detail, lat = bedrock_status("127.0.0.1", 19132)
    results.append(row("基岩  127.0.0.1:19132", ok, detail, lat))

    print("\nDNS（網域指到正確的地方嗎）")
    for h in (JAVA_HOST, BE_HOST):
        addrs = resolve(h)
        bad = any("失敗" in a for a in addrs)
        v6 = [a for a in addrs if ":" in a]
        note = "  含 IPv6，可能造成連線逾時" if v6 else ""
        results.append(row(h, not bad and not v6, ", ".join(addrs) + note))

    print("\n隧道（從這台打得到公開位址嗎）")
    ok, detail, lat = bedrock_status(BE_HOST, BE_PORT)
    results.append(row(f"基岩  {BE_HOST}:{BE_PORT}", ok, detail, lat))
    print("  [    ] Java  隧道                  playit 擋自連，看下一項")

    print("\n外部視角（別人連得進來嗎）")
    ok, detail, _ = external_view(JAVA_HOST)
    results.append(row("mcstatus.io ->  " + JAVA_HOST, ok, detail))

    print("\n網頁地圖")
    ok, detail, lat = http_status(MAP_URL)
    results.append(row(MAP_URL, ok, detail, lat))

    print("\n" + "=" * 78)
    failed = results.count(False)
    if failed:
        print(f"  {failed} 項失敗 — 從最上面的失敗項開始查，下層問題通常是上層造成的。")
    else:
        print("  全部通過。")
    print()
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
