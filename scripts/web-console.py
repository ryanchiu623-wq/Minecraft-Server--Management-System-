#!/usr/bin/env python3
"""LAN-only monitoring and control page for the Minecraft server.

Reuses the probes that already exist rather than re-implementing them:
check-server.py for the Java/Bedrock/tunnel checks and rcon.py for commands.

Three layers keep this off the public internet:

  1. Every request is checked against the private address ranges and refused
     otherwise - a misconfigured router or a port forward added by accident
     still gets nothing.
  2. Anything that changes state needs a token. Reading the dashboard does
     not, so a phone on the sofa can glance at it without typing anything.
  3. A firewall rule scoped to the local subnet keeps the port from being
     reachable off-network in the first place.

Binding defaults to every interface so both the LAN address and 127.0.0.1
work; pass --host to bind one address if you want that narrower still.

IMPORTANT: never point a playit tunnel at this port. The agent connects from
127.0.0.1, which passes the address check, so the tunnel would hand the page
to the whole internet and only the token would be left standing.

Usage:
    python web-console.py                    (all interfaces, port 8099)
    python web-console.py --port 9000
    python web-console.py --host 192.168.1.5 (bind one address only)
"""

import argparse
import ipaddress
import json
import os
import secrets
import socket
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import settings  # noqa: E402

BACKUP_DIR = settings.get("backupDir", default="")
WINDOWS_DIR = os.path.join(os.path.dirname(HERE), "windows")
SERVER_DIR = settings.server_dir()
CONFIG_PATH = os.path.join(HERE, "web-console.config.json")
AUDIT_PATH = os.path.join(HERE, "web-console.log")
PAGE_PATH = os.path.join(HERE, "web-console.html")
LOG_PATH = os.path.join(SERVER_DIR, "logs", "latest.log")
START_BAT = settings.get("startBat",
                        default=os.path.join(SERVER_DIR, "start.bat"))

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def log(message):
    """Record to a file, not just stdout.

    Under pythonw there is no stdout at all, and this is the one interface
    that can stop the server or run arbitrary console commands - losing the
    record of who did what is not acceptable just because it runs windowless.
    """
    line = "%s  %s" % (time.strftime("%Y-%m-%d %H:%M:%S"), message)
    try:
        print(line, flush=True)
    except Exception:
        pass
    try:
        if (os.path.exists(AUDIT_PATH)
                and os.path.getsize(AUDIT_PATH) > 512 * 1024):
            with open(AUDIT_PATH, encoding="utf-8", errors="replace") as fh:
                tail = fh.readlines()[-300:]
            with open(AUDIT_PATH, "w", encoding="utf-8") as fh:
                fh.writelines(tail)
        with open(AUDIT_PATH, "a", encoding="utf-8") as fh:
            fh.write(line + chr(10))
    except OSError:
        pass


def _load(name, filename):
    """Import a sibling script whose filename is not a valid module name."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(name,
                                                  os.path.join(HERE, filename))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


probe = _load("probe", "check-server.py")
rconmod = _load("rconmod", "rcon.py")


# --------------------------------------------------------------- collectors
def run(cmd, timeout=60):
    try:
        p = subprocess.run(cmd, cwd=HERE, capture_output=True, text=True,
                           timeout=timeout, creationflags=NO_WINDOW,
                           encoding="utf-8", errors="replace")
        return p.returncode == 0, (p.stdout or "") + (p.stderr or "")
    except Exception as exc:
        return False, str(exc)


def service_running(name="playitd"):
    return "RUNNING" in run(["sc", "query", name], timeout=20)[1]


def latest_backup():
    try:
        files = [f for f in os.listdir(BACKUP_DIR)
                 if f.startswith("world-") and f.endswith(".zip")]
        if not files:
            return None
        newest = max(files,
                     key=lambda f: os.path.getmtime(os.path.join(BACKUP_DIR, f)))
        path = os.path.join(BACKUP_DIR, newest)
        return {"name": newest,
                "age_h": round((time.time() - os.path.getmtime(path)) / 3600, 1),
                "mb": round(os.path.getsize(path) / 1048576, 1),
                "count": len(files)}
    except OSError:
        return None


def last_sync_hours():
    path = os.path.join(HERE, "sync-map.log")
    try:
        return round((time.time() - os.path.getmtime(path)) / 3600, 1)
    except OSError:
        return None


def jvm_heap():
    """Committed / used MB for the running server, via jcmd."""
    try:
        out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq java.exe",
                              "/FO", "CSV"], capture_output=True, text=True,
                             timeout=20, creationflags=NO_WINDOW).stdout
        pids = [ln.split('","')[1] for ln in out.splitlines()
                if ln.startswith('"java.exe')]
        for pid in pids:
            r = subprocess.run(["jcmd", pid, "GC.heap_info"],
                               capture_output=True, text=True, timeout=20,
                               creationflags=NO_WINDOW).stdout
            if "garbage-first heap" in r:
                committed = int(r.split("committed ")[1].split("K")[0]) / 1024
                used = int(r.split("used ")[1].split("K")[0]) / 1024
                return round(committed), round(used)
    except Exception:
        pass
    return None, None


def parse_tps(text):
    # "TPS from last 1m, 5m, 15m: 20.0, 20.0, 20.0"
    try:
        return [float(v) for v in text.split(":")[-1].split(",")][:3]
    except Exception:
        return None


def parse_players(text):
    # "There are 2 of a max of 20 players online: a, b"
    try:
        head, _, names = text.partition(":")
        nums = [int(w) for w in head.replace(",", " ").split() if w.isdigit()]
        online, cap = (nums + [0, 0])[:2]
        return {"online": online, "max": cap,
                "names": [n.strip() for n in names.split(",") if n.strip()]}
    except Exception:
        return None


# --------------------------------------------------------------- state poll
class Monitor:
    """One background poller feeding every connected browser.

    Without this each open tab would run its own RCON round trip and its own
    external check; the tunnel probe alone takes seconds.
    """

    FAST = 6        # seconds between local checks
    SLOW = 60       # seconds between the outside-view check

    def __init__(self):
        self.lock = threading.Lock()
        self.state = {"ready": False}
        self._outside = None
        self._outside_at = 0.0
        threading.Thread(target=self._loop, daemon=True).start()

    def snapshot(self):
        with self.lock:
            return dict(self.state)

    def _loop(self):
        while True:
            try:
                st = self._collect()
                with self.lock:
                    self.state = st
            except Exception as exc:
                with self.lock:
                    self.state = {"ready": True, "error": str(exc)}
            time.sleep(self.FAST)

    def _collect(self):
        st = {"ready": True, "at": time.time()}

        ok, detail, lat = probe.java_status("127.0.0.1", 25565)
        st["java"] = {"ok": ok, "detail": detail, "ms": lat}

        bok, bdetail, blat = probe.bedrock_status("127.0.0.1", 19132)
        st["bedrock"] = {"ok": bok, "detail": bdetail, "ms": blat}

        st["playit"] = service_running()
        if st["playit"]:
            tok, tdetail, tlat = probe.bedrock_status(probe.BE_HOST,
                                                      probe.BE_PORT)
        else:
            tok, tdetail, tlat = False, "playit 未執行", None
        st["tunnel"] = {"ok": tok, "detail": tdetail, "ms": tlat}

        now = time.time()
        if now - self._outside_at > self.SLOW:
            self._outside_at = now
            try:
                # external_view returns (ok, detail, latency); the page only
                # needs the verdict, and None when the checker itself was
                # unreachable - which must not read as "server is down".
                result = probe.external_view(probe.JAVA_HOST)
                self._outside = result[0] if isinstance(result, tuple) else result
            except Exception:
                self._outside = None
        st["outside"] = self._outside

        committed, used = jvm_heap()
        st["heap"] = {"committed": committed, "used": used}
        st["backup"] = latest_backup()
        st["sync_h"] = last_sync_hours()

        if ok:
            good, out = rconmod.execute(["tps", "list"])
            if good:
                parts = out.split(chr(10))
                st["tps"] = parse_tps(parts[0]) if parts else None
                st["players"] = parse_players(parts[1]) if len(parts) > 1 else None
        st.setdefault("tps", None)
        st.setdefault("players", None)

        st["addresses"] = {"java": probe.JAVA_HOST,
                           "bedrock": probe.BE_HOST,
                           "bedrock_port": probe.BE_PORT,
                           "map": probe.MAP_URL}
        return st


# --------------------------------------------------------------- access gate
# Spelled out rather than using ip.is_private, which also covers the
# documentation and reserved ranges (192.0.2.0/24, 203.0.113.0/24, 240/4...).
# Those are not routable, but "internal network" should mean exactly the
# networks a home LAN actually uses.
LAN_NETWORKS = [ipaddress.ip_network(n) for n in (
    "127.0.0.0/8", "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16",
    "169.254.0.0/16", "::1/128", "fc00::/7", "fe80::/10",
)]


def is_private(addr):
    try:
        ip = ipaddress.ip_address(addr)
    except ValueError:
        return False
    return any(ip in net for net in LAN_NETWORKS if ip.version == net.version)


def load_config():
    cfg = {}
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, encoding="utf-8") as fh:
                cfg = json.load(fh)
        except (OSError, ValueError):
            cfg = {}
    if not cfg.get("token"):
        cfg["token"] = secrets.token_urlsafe(18)
        with open(CONFIG_PATH, "w", encoding="utf-8") as fh:
            json.dump(cfg, fh, indent=2)
    return cfg


CONFIG = load_config()
MONITOR = Monitor()


def lan_address():
    """Best guess at this machine's address on the local network."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


# --------------------------------------------------------------- the handler
class Handler(BaseHTTPRequestHandler):
    server_version = "mc-console"

    def log_message(self, fmt, *args):
        pass  # too chatty; mutating actions are logged explicitly below

    # -- helpers ----------------------------------------------------------
    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        data = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(data)

    def _json(self, code, obj):
        self._send(code, json.dumps(obj, ensure_ascii=False))

    def _gate(self):
        if not is_private(self.client_address[0]):
            self._json(403, {"error": "只接受內網連線"})
            return False
        return True

    def _body(self):
        try:
            n = int(self.headers.get("Content-Length") or 0)
            return json.loads(self.rfile.read(n) or b"{}")
        except Exception:
            return {}

    def _authed(self, payload):
        return secrets.compare_digest(str(payload.get("token", "")),
                                      CONFIG["token"])

    def _audit(self, what):
        log("%s  <- %s" % (what, self.client_address[0]))

    # -- routes -----------------------------------------------------------
    def do_GET(self):
        if not self._gate():
            return
        path = self.path.split("?")[0]

        if path in ("/", "/index.html"):
            try:
                with open(PAGE_PATH, "rb") as fh:
                    self._send(200, fh.read(), "text/html; charset=utf-8")
            except OSError:
                self._send(500, b"web-console.html not found", "text/plain")
            return

        if path == "/api/status":
            self._json(200, MONITOR.snapshot())
            return

        if path == "/api/log":
            try:
                with open(LOG_PATH, encoding="utf-8", errors="replace") as fh:
                    lines = fh.readlines()[-120:]
                self._json(200, {"lines": [ln.rstrip() for ln in lines]})
            except OSError as exc:
                self._json(200, {"lines": ["讀不到伺服器日誌：%s" % exc]})
            return

        self._json(404, {"error": "not found"})

    def do_POST(self):
        if not self._gate():
            return
        path = self.path.split("?")[0]
        payload = self._body()

        if not self._authed(payload):
            self._json(401, {"error": "權杖不正確"})
            return

        if path == "/api/rcon":
            command = str(payload.get("command", "")).strip()
            if not command:
                self._json(400, {"error": "沒有指令"})
                return
            self._audit("rcon: " + command)
            ok, out = rconmod.execute([command])
            self._json(200, {"ok": ok, "output": out})
            return

        if path == "/api/action":
            action = str(payload.get("action", ""))
            self._audit("action: " + action)
            self._json(200, self._do_action(action))
            return

        self._json(404, {"error": "not found"})

    def _do_action(self, action):
        if action == "start":
            if MONITOR.snapshot().get("java", {}).get("ok"):
                return {"ok": False, "message": "伺服器已經在執行"}
            subprocess.Popen(
                ["cmd", "/c", "start", '"MC Server"', "/min", START_BAT,
                 "/nopause"],
                cwd=HERE, creationflags=NO_WINDOW)
            return {"ok": True, "message": "已送出啟動指令，約 40 秒後上線"}

        if action == "stop":
            ok, out = rconmod.execute(["save-all", "stop"])
            return {"ok": ok, "message": out or "已送出關閉指令"}

        if action == "backup":
            ok, out = run(["powershell.exe", "-NoProfile", "-WindowStyle",
                           "Hidden", "-ExecutionPolicy", "Bypass", "-File",
                           os.path.join(WINDOWS_DIR, "backup-world.ps1"), "-Keep",
                           "7"], timeout=900)
            return {"ok": ok, "message": out.strip()[-400:] or "備份完成"}

        if action == "render":
            ok, out = run(["powershell.exe", "-NoProfile", "-WindowStyle",
                           "Hidden", "-ExecutionPolicy", "Bypass", "-File",
                           os.path.join(WINDOWS_DIR, "sync-map.ps1")], timeout=900)
            return {"ok": ok, "message": out.strip()[-400:] or "同步完成"}

        if action == "playit":
            run(["sc", "start", "playitd"], timeout=30)
            return {"ok": True, "message": "已嘗試啟動 playit 服務"}

        return {"ok": False, "message": "不認得的動作：%s" % action}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host",
                    default=settings.get("webConsole", "host",
                                         default="0.0.0.0"),
                    help="bind address (default: every interface)")
    ap.add_argument("--port", type=int,
                    default=settings.get("webConsole", "port", default=8099))
    args = ap.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    shown = lan_address() if args.host == "0.0.0.0" else args.host

    print("=" * 62)
    print(" Minecraft 內網控制台")
    print("=" * 62)
    print(" 網址   http://%s:%d   （區網其他裝置用這個）" % (shown, args.port))
    if args.host in ("0.0.0.0", "127.0.0.1"):
        print("        http://127.0.0.1:%d   （這台機器上）" % args.port)
    print(" 權杖   %s" % CONFIG["token"])
    print("        （只有按鈕和指令需要，看狀態不用）")
    print(" 保存於 %s" % CONFIG_PATH)
    print("=" * 62)
    print(" 非私有位址的連線一律拒絕。不要幫這個埠開 playit 隧道。")
    print("=" * 62, flush=True)

    log("console started on %s:%d" % (args.host, args.port))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n收到中斷，關閉中…")
        server.shutdown()


if __name__ == "__main__":
    main()
