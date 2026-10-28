#!/usr/bin/env python3
"""Health-check the Minecraft server end to end - no game client needed.

Speaks both status protocols directly:
  Java    TCP  handshake(state=1) + status request  -> JSON
  Bedrock UDP  RakNet unconnected ping              -> semicolon-separated MOTD

Checks, in order: the local server, DNS, the public tunnels, an outside
vantage point, and the published map.

Each public path is checked the way players actually use it, chosen per path
by config.json "tunnel": {"java": ..., "bedrock": ..., "web": ...}:
  java playit       The SRV record points at playit's own hostname, and
                    playit routes on the hostname in the handshake - an IP or
                    our domain is refused. So the check follows the SRV record
                    and sends the target name, exactly as the game client does.
  java cloudflared  A Cloudflare Tunnel only carries raw TCP to a client that
                    runs cloudflared access, so mcstatus.io always sees it
                    offline. The check runs cloudflared access itself.
  bedrock warden    Geyser's NetherNet goes through Warden, which answers
                    HTTPS, not a RakNet ping.
  bedrock playit    RakNet ping through the UDP tunnel.

Usage:  python check-server.py
"""

import json
import os
import re
import shutil
import socket
import struct
import subprocess
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


def _routes():
    """(java, bedrock, web) - also accepts the older single "type" key."""
    t = settings.get("tunnel", default={}) or {}
    cf = t.get("type") == "cloudflared"
    return (t.get("java") or ("cloudflared" if cf else "playit"),
            t.get("bedrock") or ("warden" if cf else "playit"),
            t.get("web") or ("cloudflared" if cf else "pages"))


JAVA_VIA, BE_VIA, WEB_VIA = _routes()

OK, FAIL, WARN = "OK  ", "FAIL", "WARN"

# The consoles import this module and run with pythonw, which has no console:
# every console program it starts would otherwise open a window of its own.
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


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


def java_status(host, port, timeout=8, connect_to=None):
    """Return (ok, detail, latency_ms). `host` goes in the handshake;
    `connect_to` is the address actually dialled, when that differs."""
    started = time.time()
    try:
        sock = socket.create_connection((connect_to or host, port), timeout=timeout)
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


def _dns_name(buf, off):
    """Read a possibly compressed DNS name; return (name, offset after it)."""
    labels, jumped, end = [], False, off
    while True:
        n = buf[off]
        if n & 0xC0 == 0xC0:
            if not jumped:
                end = off + 2
            off, jumped = ((n & 0x3F) << 8) | buf[off + 1], True
            continue
        if n == 0:
            return ".".join(labels), (end if jumped else off + 1)
        labels.append(buf[off + 1:off + 1 + n].decode("ascii", "replace"))
        off += 1 + n


def srv_lookup(name, servers=("1.1.1.1", "8.8.8.8"), timeout=4):
    """(target, port) of the first SRV record, or None. The standard library
    has no SRV lookup, so this sends one plain DNS query itself."""
    qid = int(time.time() * 1000) & 0xFFFF
    q = struct.pack(">HHHHHH", qid, 0x0100, 1, 0, 0, 0)
    q += b"".join(bytes([len(p)]) + p.encode() for p in name.split(".")) + b"\x00"
    q += struct.pack(">HH", 33, 1)                      # SRV, IN
    for server in servers:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(timeout)
        try:
            s.sendto(q, (server, 53))
            buf = s.recv(2048)
        except OSError:
            continue
        finally:
            s.close()
        rid, _, qd, an = struct.unpack(">HHHH", buf[:8])
        if rid != qid:
            continue
        off = 12
        for _ in range(qd):
            off = _dns_name(buf, off)[1] + 4
        for _ in range(an):
            off = _dns_name(buf, off)[1]
            rtype, _, _, rdlen = struct.unpack(">HHIH", buf[off:off + 10])
            off += 10
            if rtype == 33:
                port = struct.unpack(">H", buf[off + 4:off + 6])[0]
                return _dns_name(buf, off + 6)[0], port
            off += rdlen
        return None
    return None


def java_via_playit(host):
    """Ping through playit exactly as a player's client does: follow the SRV
    record and put its target - playit's hostname - in the handshake."""
    srv = srv_lookup("_minecraft._tcp." + host)
    if not srv:
        return False, "找不到 SRV 記錄", None
    target, port = srv
    try:
        # playit publishes AAAA too but does not route IPv6, so dial IPv4 -
        # which is also what the Java client prefers by default.
        ip = socket.getaddrinfo(target, port, socket.AF_INET)[0][4][0]
    except OSError:
        return False, f"解析不到 {target}", None
    return java_status(target, port, connect_to=ip)


def playit_running():
    try:
        out = subprocess.run(["sc", "query", "playitd"], capture_output=True,
                             text=True, timeout=15, creationflags=NO_WINDOW).stdout
        return "RUNNING" in out
    except Exception:
        return False


def tunnel_services():
    """[(name, running)] for the tunnel agents this setup depends on."""
    out = []
    if "playit" in (JAVA_VIA, BE_VIA):
        out.append(("playit", playit_running()))
    if "cloudflared" in (JAVA_VIA, WEB_VIA):
        out.append(("cloudflared", cloudflared_ready()[0]))
    return out


def http_status(url, timeout=15):
    started = time.time()
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "mc-healthcheck"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return True, f"HTTP {resp.status}", int((time.time() - started) * 1000)
    except Exception as exc:
        return False, f"{type(exc).__name__}", None


# ---------------------------------------------------------- cloudflared tunnel
def cloudflared_ready(timeout=3):
    """Ask the local cloudflared how many edge connections it holds.

    cloudflared serves /ready on the first free port of 20241-20245. A count
    above zero means Cloudflare's edge can route visitors to this machine.
    """
    for port in range(20241, 20246):
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/ready",
                                        timeout=timeout) as resp:
                d = json.loads(resp.read().decode("utf-8"))
        except Exception:
            continue
        n = d.get("readyConnections", 0)
        if n:
            return True, f"Cloudflare 邊緣 {n} 條連線", None
        return False, "cloudflared 沒有連上 Cloudflare", None
    return False, "cloudflared 未執行", None


def _cloudflared_exe():
    # A shortcut started from Explorer keeps the PATH Explorer had at logon,
    # which misses cloudflared until the next logon after installing it.
    found = shutil.which("cloudflared")
    if found:
        return found
    for base in (os.environ.get("ProgramFiles(x86)"), os.environ.get("ProgramFiles")):
        if base and os.path.exists(os.path.join(base, "cloudflared", "cloudflared.exe")):
            return os.path.join(base, "cloudflared", "cloudflared.exe")
    return "cloudflared"


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def java_via_access(host, timeout=12):
    """Ping the server the way a remote Java player reaches it.

    Opens cloudflared access tcp to the public hostname, so the request goes
    out to Cloudflare's edge and back in through the tunnel.
    """
    port = _free_port()
    try:
        proc = subprocess.Popen(
            [_cloudflared_exe(), "access", "tcp", "--hostname", host,
             "--url", f"127.0.0.1:{port}"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=NO_WINDOW)
    except OSError:
        return False, "找不到 cloudflared", None
    try:
        deadline = time.time() + timeout
        while time.time() < deadline:
            if proc.poll() is not None:
                return False, "cloudflared access 結束了", None
            try:
                socket.create_connection(("127.0.0.1", port), timeout=1).close()
                break
            except OSError:
                time.sleep(0.3)
        else:
            return False, "cloudflared access 沒有開啟", None
        ok, detail, lat = java_status("127.0.0.1", port)
        return ok, detail if ok else "隧道" + detail, lat
    finally:
        proc.kill()


def warden_status(host):
    ok, detail, lat = http_status(f"https://{host}")
    return ok, detail if ok else f"Warden {detail}", lat


def warden_reachability():
    """Warden's own verdict, which it checks from several regions.

    Geyser logs it as "NXS: IPv4 is available for player connections" each
    time it registers; the newest such line in latest.log is the current one.
    """
    path = os.path.join(settings.server_dir(), "logs", "latest.log")
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            lines = [l for l in fh if "NXS:" in l and "player connections" in l]
    except OSError:
        return None, "讀不到伺服器日誌", None
    if not lines:
        return None, "Warden 尚未回報", None
    ok = bool(re.search(r"\bis available", lines[-1]))
    return ok, "Warden 檢測可連" if ok else "Warden 檢測連不到", None


_TUNNEL_CACHE = {"at": 0.0, "result": None}


def java_public():
    if JAVA_VIA == "cloudflared":
        return java_via_access(JAVA_HOST)
    return java_via_playit(JAVA_HOST)


def bedrock_public():
    if BE_VIA == "warden":
        return warden_status(BE_HOST)
    return bedrock_status(BE_HOST, BE_PORT)


def tunnel_status(max_age=60):
    """(ok, detail, latency) for both public game paths, as the consoles show
    them. Checks go out to the internet (and cloudflared access starts a
    process), so the consoles' fast polls reuse a result for max_age seconds.
    """
    now = time.time()
    if _TUNNEL_CACHE["result"] and now - _TUNNEL_CACHE["at"] < max_age:
        return _TUNNEL_CACHE["result"]
    jok, jdetail, jlat = java_public()
    bok, bdetail, _ = bedrock_public()
    detail = f"Java {jdetail}　基岩 {bdetail}"
    result = (jok and bok, detail, jlat)
    _TUNNEL_CACHE.update(at=now, result=result)
    return result


def java_outside():
    if JAVA_VIA == "cloudflared":
        # mcstatus.io cannot speak through a Cloudflare Tunnel; what the edge
        # itself reports is the outside view there.
        return cloudflared_ready()
    return _mcstatus(JAVA_HOST)


def external_view(host=None, timeout=25):
    """(ok, detail, None): can outsiders get in, judged by third parties -
    mcstatus.io or Cloudflare's edge for Java, Warden's regional check for
    Bedrock. `host` is accepted for older callers and ignored."""
    jok, jdetail, _ = java_outside()
    parts, ok = [f"Java {jdetail}"], jok
    if BE_VIA == "warden":
        wok, wdetail, _ = warden_reachability()
        parts.append(wdetail)
        # None means Warden has not reported yet - not a failure.
        ok = ok and wok is not False
    return ok, "　".join(parts), None


def _mcstatus(host, timeout=25):
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
    if JAVA_VIA == "playit":
        # No A record on purpose: the SRV target must be playit's own name.
        srv = srv_lookup("_minecraft._tcp." + JAVA_HOST)
        results.append(row(f"Java  SRV {JAVA_HOST}", bool(srv),
                           "→ %s:%d" % srv if srv else "找不到 SRV 記錄"))
    else:
        addrs = resolve(JAVA_HOST)
        results.append(row(JAVA_HOST, not any("失敗" in a for a in addrs), ", ".join(addrs)))
    addrs = resolve(BE_HOST)
    bad = any("失敗" in a for a in addrs)
    # playit announces IPv6 it does not route; Warden sits on Cloudflare,
    # where IPv6 works.
    v6 = BE_VIA == "playit" and any(":" in a for a in addrs)
    results.append(row(BE_HOST, not bad and not v6,
                       ", ".join(addrs) + ("  含 IPv6，可能造成連線逾時" if v6 else "")))

    print("\n隧道（從這台打得到公開位址嗎）")
    for name, running in tunnel_services():
        results.append(row(f"{name} 服務", running, "執行中" if running else "沒在執行"))
    ok, detail, lat = java_public()
    how = "SRV → playit" if JAVA_VIA == "playit" else "cloudflared access"
    results.append(row(f"Java  {how}", ok, detail, lat))
    ok, detail, lat = bedrock_public()
    where = f"https://{BE_HOST}" if BE_VIA == "warden" else f"{BE_HOST}:{BE_PORT}"
    results.append(row(f"基岩  {where}", ok, detail, lat))

    print("\n外部視角（別人連得進來嗎）")
    ok, detail, _ = java_outside()
    who = "mcstatus.io" if JAVA_VIA == "playit" else "Cloudflare 邊緣"
    results.append(row(f"Java  {who}", ok, detail))
    if BE_VIA == "warden":
        ok, detail, _ = warden_reachability()
        results.append(row("基岩  Warden 區域檢測", ok is not False, detail))

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
