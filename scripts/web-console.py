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

IMPORTANT: never point a tunnel at this port. A tunnel agent connects from
127.0.0.1, which passes the address check, so the tunnel would hand the page
to the whole internet and only the token would be left standing.

The public entrance is a second listener for exactly that case. It binds
127.0.0.1 only (webConsole.publicPort in config.json, 8098 here), the
Cloudflare tunnel points at it, and every request there needs a logged-in
session - username and password from console_auth.py - before the normal page
and its token checks are reached. Failed logins are throttled per address and
in total.

Usage:
    python web-console.py                    (all interfaces, port 8099)
    python web-console.py --port 9000
    python web-console.py --host 192.168.1.5 (bind one address only)
"""

import argparse
import http.cookies
import ipaddress
import json
import os
import re
import secrets
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import settings  # noqa: E402
import console_auth  # noqa: E402

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
panels = _load("plugin_panels", "plugin_panels.py")
panels.setup(rconmod)
# Planned stops and restarts go through the 5-minute countdown the server
# rules promise players; nothing here stops the server outright.
sequence = _load("restart_sequence", "restart-sequence.py")


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


# --------------------------------------------------------------- game rules
# Rule names are NOT the camelCase ones from the wiki on this server - it uses
# snake_case, and several rules dropped their "do" prefix (doTileDrops is
# block_drops, doMobSpawning is spawn_mobs). Rather than trust a hard-coded
# list, every candidate is asked once at startup and only the ones the server
# actually answers are offered. That keeps this working across versions that
# rename things again.
RULE_LABELS = [
    ("keep_inventory", "死亡不掉落"),
    ("show_death_messages", "顯示死亡訊息"),
    ("immediate_respawn", "死亡後立即重生"),
    ("mob_griefing", "生物可破壞方塊"),
    ("spawn_mobs", "生成生物"),
    ("mob_drops", "生物掉落物"),
    ("block_drops", "方塊掉落物"),
    ("entity_drops", "實體掉落物"),
    ("pvp", "玩家互相傷害"),
    ("fall_damage", "墜落傷害"),
    ("fire_damage", "火焰傷害"),
    ("freeze_damage", "凍傷"),
    ("drowning_damage", "溺水傷害"),
    ("raids", "襲擊"),
    ("universal_anger", "全體激怒"),
    ("forgive_dead_players", "原諒死亡玩家"),
    ("ender_pearls_vanish_on_death", "死亡時終界珍珠消失"),
    ("projectiles_can_break_blocks", "投射物可破壞方塊"),
    ("limited_crafting", "限制合成（需先解鎖配方）"),
    ("command_block_output", "指令方塊輸出到聊天"),
    ("send_command_feedback", "指令回饋"),
    ("log_admin_commands", "記錄管理員指令"),
    ("reduced_debug_info", "精簡除錯資訊"),
    ("spectators_generate_chunks", "旁觀者生成區塊"),
    ("global_sound_events", "全域音效事件"),
    ("water_source_conversion", "水源擴散"),
    ("lava_source_conversion", "岩漿源擴散"),
    ("block_explosion_drop_decay", "方塊爆炸掉落衰減"),
    ("mob_explosion_drop_decay", "生物爆炸掉落衰減"),
    ("tnt_explosion_drop_decay", "TNT 爆炸掉落衰減"),
    ("elytra_movement_check", "鞘翅移動檢查"),
    ("random_tick_speed", "隨機刻速度"),
    ("max_entity_cramming", "實體擁擠上限"),
    ("players_sleeping_percentage", "跳過夜晚所需睡覺比例 %"),
]

_RULE_CACHE = {"at": 0.0, "rules": None}


def _parse_rule_reply(text):
    # Up to 26.2 the reply reads "is currently set to: false"; 26.3 dropped
    # the colon. Without it every rule looked unknown and the panel was empty.
    m = re.search(r"is currently set to:?\s*(\S+)", text or "")
    return m.group(1) if m else None


def game_rules(force=False):
    """Current value of every rule this server recognises."""
    now = time.time()
    cached = _RULE_CACHE["rules"]
    if cached is not None and not force and now - _RULE_CACHE["at"] < 20:
        return cached

    names = [n for n, _ in RULE_LABELS]
    # RCON on an idle server drops connections often enough that a single
    # attempt regularly comes back empty, and an empty list is indistinguishable
    # from "this server has no rules". Retry before giving up, and keep serving
    # the last good answer rather than blanking the panel.
    for attempt in range(3):
        ok, replies = rconmod.execute_each(["gamerule " + n for n in names])
        if ok:
            break
        time.sleep(0.6)
    else:
        return cached or []

    labels = dict(RULE_LABELS)
    out = []
    for name, reply in zip(names, replies):
        value = _parse_rule_reply(reply)
        if value is None:
            continue          # this server does not know that rule
        if value in ("true", "false"):
            kind, parsed = "bool", value == "true"
        else:
            try:
                kind, parsed = "int", int(value)
            except ValueError:
                kind, parsed = "text", value
        out.append({"name": name, "label": labels[name],
                    "kind": kind, "value": parsed})

    _RULE_CACHE.update(at=now, rules=out)
    return out


# ------------------------------------------------------------------- memory
RAM_PATTERN = re.compile(rb'(set "M(?:IN|AX)_RAM=)([0-9]+[GgMm])(")')


def total_ram_gb():
    ok, out = run(["powershell.exe", "-NoProfile", "-NonInteractive",
                   "-Command",
                   "[math]::Round((Get-CimInstance Win32_ComputerSystem)"
                   ".TotalPhysicalMemory/1GB,1)"], timeout=60)
    try:
        return float(out.strip().splitlines()[0])
    except (ValueError, IndexError):
        return None


def read_memory():
    """Current -Xms/-Xmx as written in start.bat."""
    try:
        raw = open(START_BAT, "rb").read()
    except OSError as exc:
        return {"error": str(exc)}
    found = {}
    for m in re.finditer(rb'set "(M(?:IN|AX)_RAM)=([0-9]+[GgMm])"', raw):
        found[m.group(1).decode()] = m.group(2).decode().upper()
    return {"min": found.get("MIN_RAM"), "max": found.get("MAX_RAM"),
            "totalGb": total_ram_gb(), "path": START_BAT}


def _to_mb(value):
    n = int(value[:-1])
    return n * 1024 if value[-1] in "Gg" else n


def write_memory(new_min, new_max):
    """Rewrite the two RAM lines in start.bat, in place and byte-for-byte.

    Edited as bytes on purpose: start.bat has to stay pure ASCII with CRLF
    endings or cmd.exe mangles it, and a decode/encode round trip through a
    text editor is exactly how that gets lost.
    """
    for v in (new_min, new_max):
        if not re.fullmatch(r"[0-9]{1,5}[GgMm]", v or ""):
            return False, "格式要像 2G 或 512M，收到：%s" % v

    lo, hi = _to_mb(new_min), _to_mb(new_max)
    if lo < 512:
        return False, "最小值不能低於 512M"
    if hi < lo:
        return False, "最大值不能小於最小值"

    total = total_ram_gb()
    if total and hi > (total - 1) * 1024:
        return False, ("最大值 %s 超過安全上限：這台有 %.1f GB，"
                       "至少要留 1 GB 給系統" % (new_max, total))

    try:
        raw = open(START_BAT, "rb").read()
    except OSError as exc:
        return False, str(exc)

    def repl(m):
        key = m.group(1)
        value = new_min if key == b"MIN_RAM" else new_max
        return b'set "' + key + b"=" + value.upper().encode() + b'"'

    patched, n = re.subn(rb'set "(M(?:IN|AX)_RAM)=[0-9]+[GgMm]"', repl, raw)
    if n != 2:
        return False, "在 start.bat 找不到那兩行設定（找到 %d 行）" % n
    if not all(b < 128 for b in patched):
        return False, "改完會產生非 ASCII 字元，已中止"

    shutil.copy2(START_BAT, START_BAT + ".bak")
    with open(START_BAT, "wb") as fh:
        fh.write(patched)
    return True, "已寫入 %s（原檔備份為 .bak）。下次啟動伺服器才會生效。" % (
        os.path.basename(START_BAT))


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

        bok, bdetail, blat = probe.bedrock_local()
        st["bedrock"] = {"ok": bok, "detail": bdetail, "ms": blat}

        # One agent per path now (playit for Java, cloudflared for the map),
        # so every one of them has to be up for the tunnel tile to be green.
        services = probe.tunnel_services()
        st["services"] = [{"name": n, "running": r} for n, r in services]
        st["tunnel_service"] = all(r for _, r in services)
        down = [n for n, r in services if not r]
        if down:
            tok, tdetail, tlat = False, "、".join(down) + " 未執行", None
        else:
            tok, tdetail, tlat = probe.tunnel_status()
        st["tunnel"] = {"ok": tok, "detail": tdetail, "ms": tlat}

        now = time.time()
        if now - self._outside_at > self.SLOW:
            self._outside_at = now
            try:
                # external_view returns (ok, detail, latency); the page only
                # needs the verdict, and None when the checker itself was
                # unreachable - which must not read as "server is down".
                result = probe.external_view()
                self._outside = result[0]
                self._outside_detail = result[1]
            except Exception:
                self._outside = None
                self._outside_detail = ""
        st["outside"] = self._outside
        st["outside_detail"] = getattr(self, "_outside_detail", "")

        committed, used = jvm_heap()
        st["heap"] = {"committed": committed, "used": used}
        st["backup"] = latest_backup()
        st["sync_h"] = last_sync_hours()

        if ok:
            # minecraft:list: EssentialsX's /list is translated and grouped.
            good, out = rconmod.execute(["tps", "minecraft:list"])
            if good:
                parts = out.split(chr(10))
                st["tps"] = parse_tps(parts[0]) if parts else None
                st["players"] = parse_players(parts[1]) if len(parts) > 1 else None
        st.setdefault("tps", None)
        st.setdefault("players", None)

        st["countdown"] = sequence.pending()

        st["addresses"] = {"java": probe.JAVA_HOST, "java_via": probe.JAVA_VIA,
                           "bedrock": probe.BE_HOST, "bedrock_via": probe.BE_VIA,
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
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
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

    def _who(self):
        """The address to record for this request."""
        return self.client_address[0]

    def _audit(self, what):
        log("%s  <- %s" % (what, self._who()))

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

        if path == "/api/gamerules":
            self._json(200, {"rules": game_rules()})
            return

        if path == "/api/memory":
            self._json(200, read_memory())
            return

        if path == "/api/log":
            try:
                with open(LOG_PATH, encoding="utf-8", errors="replace") as fh:
                    lines = fh.readlines()[-120:]
                self._json(200, {"lines": [ln.rstrip() for ln in lines]})
            except OSError as exc:
                self._json(200, {"lines": ["讀不到伺服器日誌：%s" % exc]})
            return

        # Plugin list and form definitions only - nothing private, so no
        # token, same as the rest of the dashboard.
        if path == "/api/plugins":
            self._json(200, panels.catalogue())
            return

        if path == "/api/icon":
            query = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
            item = query.get("id", [""])[0]
            png = panels.item_icon(item)
            if png:
                self._send(200, png, "image/png")
            else:
                self._send(404, b"", "image/png")
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

        if path == "/api/gamerule":
            rule = str(payload.get("rule", ""))
            value = str(payload.get("value", ""))
            if not any(rule == r["name"] for r in game_rules()):
                self._json(400, {"error": "不認得的規則：%s" % rule})
                return
            self._audit("gamerule %s = %s" % (rule, value))
            ok, out = rconmod.execute(["gamerule %s %s" % (rule, value)])
            game_rules(force=True)
            self._json(200, {"ok": ok, "message": out})
            return

        if path == "/api/memory":
            self._audit("memory %s / %s" % (payload.get("min"),
                                            payload.get("max")))
            ok, msg = write_memory(str(payload.get("min", "")),
                                   str(payload.get("max", "")))
            self._json(200, {"ok": ok, "message": msg})
            return

        if path == "/api/action":
            action = str(payload.get("action", ""))
            self._audit("action: " + action)
            self._json(200, self._do_action(action))
            return

        # Plugin panels. Reading is token-gated too: inventories, block logs
        # and permissions are about other players.
        if path == "/api/plugin/run":
            key = str(payload.get("plugin", ""))
            act = str(payload.get("action", ""))
            try:
                result = panels.run_action(key, act, payload.get("args") or {})
            except panels.BadInput as exc:
                self._json(400, {"error": str(exc)})
                return
            self._audit("plugin %s/%s: %s" % (key, act, " | ".join(result["commands"])))
            self._json(200, result)
            return

        if path == "/api/plugin/data":
            try:
                data = panels.panel_data(str(payload.get("panel", "")),
                                         payload.get("args") or {})
            except panels.BadInput as exc:
                self._json(400, {"error": str(exc)})
                return
            self._json(200, data)
            return

        if path == "/api/plugin/download":
            try:
                name, blob = panels.read_download(str(payload.get("kind", "")),
                                                  str(payload.get("name", "")))
            except panels.BadInput as exc:
                self._json(400, {"error": str(exc)})
                return
            self._audit("download %s/%s" % (payload.get("kind"), name))
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(len(blob)))
            self.send_header("Content-Disposition",
                             "attachment; filename*=UTF-8''%s"
                             % urllib.parse.quote(name))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(blob)
            return

        self._json(404, {"error": "not found"})

    def _do_action(self, action):
        if action == "start":
            if MONITOR.snapshot().get("java", {}).get("ok"):
                return {"ok": False, "message": "伺服器已經在執行"}
            subprocess.Popen(settings.server_launch_command(START_BAT),
                             cwd=HERE, creationflags=NO_WINDOW)
            return {"ok": True, "message": "已送出啟動指令，約 40 秒後上線"}

        if action in ("stop", "restart"):
            ok, msg = sequence.launch(action, by="web " + self._who())
            return {"ok": ok, "message": msg}

        if action == "cancel":
            if not sequence.pending():
                return {"ok": False, "message": "沒有進行中的倒數"}
            sequence.request_cancel()
            return {"ok": True, "message": "已取消倒數，遊戲裡會公告"}

        if action == "backup":
            ok, out = run(["powershell.exe", "-NoProfile", "-WindowStyle",
                           "Hidden", "-ExecutionPolicy", "Bypass", "-File",
                           os.path.join(WINDOWS_DIR, "backup-world.ps1"), "-Keep",
                           "7"], timeout=900)
            return {"ok": ok, "message": out.strip()[-400:] or "備份完成"}

        if action == "render" and probe.WEB_VIA == "cloudflared":
            # The map is served live through the tunnel - nothing to upload,
            # only BlueMap to nudge.
            maps = settings.get("bluemapMaps",
                                default=["world", "world_the_nether", "world_the_end"])
            ok, out = rconmod.execute(["bluemap update %s" % m for m in maps])
            return {"ok": ok, "message": (out or "") + "\n已要求 BlueMap 更新，網頁地圖會自動跟上"}

        if action == "render":
            ok, out = run(["powershell.exe", "-NoProfile", "-WindowStyle",
                           "Hidden", "-ExecutionPolicy", "Bypass", "-File",
                           os.path.join(WINDOWS_DIR, "sync-map.ps1")], timeout=900)
            return {"ok": ok, "message": out.strip()[-400:] or "同步完成"}

        if action == "playit":
            run(["sc", "start", "playitd"], timeout=30)
            return {"ok": True, "message": "已嘗試啟動 playit 服務"}

        return {"ok": False, "message": "不認得的動作：%s" % action}


# ----------------------------------------------------------- public entrance
SESSION_COOKIE = "mcc_session"
SESSION_IDLE = 2 * 3600         # signed out after two hours without a request
SESSION_MAX = 12 * 3600         # and after twelve hours whatever happens
FAIL_WINDOW = 15 * 60
FAILS_PER_ADDRESS = 5           # wrong passwords from one address before it is locked out
FAILS_IN_TOTAL = 30             # from everywhere together, against a spread-out guesser

_SESSIONS = {}                  # cookie value -> {"user", "ip", "created", "seen"}
_FAILS = {}                     # address -> times of recent failed logins
_ALL_FAILS = []
_AUTH_LOCK = threading.Lock()

LOGIN_PAGE = """<!DOCTYPE html>
<html lang="zh-Hant"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>登入 · Minecraft 控制台</title>
<style>
  :root { color-scheme: light dark; --bg:#ddd6c6; --ink:#2a2a26; --card:#f2f1ec; --accent:#4f6238; --bad:#8a3b2c; }
  @media (prefers-color-scheme: dark) { :root { --bg:#1f1f1c; --ink:#ecebe6; --card:#2a2a26; --bad:#f0a08c; } }
  body { margin:0; min-height:100vh; display:grid; place-items:center; background:var(--bg); color:var(--ink);
         font:16px/1.5 "Microsoft JhengHei","Noto Sans TC",system-ui,sans-serif; }
  form { width:min(100vw - 32px, 360px); background:var(--card); padding:28px 24px; }
  h1 { font-size:22px; margin:0 0 4px; }
  p { margin:0 0 20px; opacity:.8; font-size:14px; }
  label { display:block; font-size:14px; margin:14px 0 6px; }
  input { width:100%; box-sizing:border-box; font:inherit; padding:10px 12px; border:0; background:var(--bg); color:var(--ink); }
  button { margin-top:22px; width:100%; min-height:46px; border:0; background:var(--accent); color:#fff; font:inherit; font-weight:700; cursor:pointer; }
  .msg { color:var(--bad); font-weight:700; margin:12px 0 0; opacity:1; }
</style></head><body>
<form method="post" action="/login">
  <h1>Minecraft 控制台</h1>
  <p>Ryan mc 伺服器的遠端管理。登入後，按鈕和指令還需要控制權杖。</p>
  <label for="u">帳號</label>
  <input id="u" name="username" autocomplete="username" required autofocus>
  <label for="p">密碼</label>
  <input id="p" name="password" type="password" autocomplete="current-password" required>
  <button type="submit">登入</button>
  {message}
</form></body></html>
"""


class PublicHandler(Handler):
    """The entrance the Cloudflare tunnel reaches.

    Only cloudflared on this machine can connect (the listener is bound to
    127.0.0.1), so every request here came from the internet. Nothing past
    /login is served without a session; the page itself and its token checks
    then work exactly as on the LAN.
    """

    def _gate(self):
        if self.client_address[0] not in ("127.0.0.1", "::1"):
            self._json(403, {"error": "forbidden"})
            return False
        return True

    def _who(self):
        # Cloudflare's edge sets this on every request and overwrites any copy
        # a client sends, so it is the visitor's real address.
        return self.headers.get("Cf-Connecting-Ip") or self.client_address[0]

    def _session(self):
        cookie = http.cookies.SimpleCookie()
        try:
            cookie.load(self.headers.get("Cookie") or "")
        except http.cookies.CookieError:
            return None
        value = cookie[SESSION_COOKIE].value if SESSION_COOKIE in cookie else ""
        now = time.time()
        with _AUTH_LOCK:
            s = _SESSIONS.get(value)
            if not s:
                return None
            if now - s["seen"] > SESSION_IDLE or now - s["created"] > SESSION_MAX:
                _SESSIONS.pop(value, None)
                return None
            s["seen"] = now
            return s

    def _redirect(self, where, cookie=None):
        self.send_response(303)
        self.send_header("Location", where)
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _login_page(self, message="", code=200):
        if not message and not console_auth.configured_user():
            message = "還沒有設定帳號密碼：請用 Discord 的 /console-password 設定。"
        html = LOGIN_PAGE.replace(
            "{message}", '<p class="msg">%s</p>' % message if message else "")
        self._send(code, html, "text/html; charset=utf-8")

    def _login(self):
        ip = self._who()
        now = time.time()
        with _AUTH_LOCK:
            recent = [t for t in _FAILS.get(ip, []) if now - t < FAIL_WINDOW]
            _FAILS[ip] = recent
            _ALL_FAILS[:] = [t for t in _ALL_FAILS if now - t < FAIL_WINDOW]
            locked = len(recent) >= FAILS_PER_ADDRESS or len(_ALL_FAILS) >= FAILS_IN_TOTAL
        if locked:
            log("login refused, too many failures  <- %s" % ip)
            self._login_page("嘗試太多次，請 15 分鐘後再試。", 429)
            return

        n = min(int(self.headers.get("Content-Length") or 0), 4096)
        form = urllib.parse.parse_qs(self.rfile.read(n).decode("utf-8", "replace"))
        user = form.get("username", [""])[0].strip()
        password = form.get("password", [""])[0]

        if console_auth.verify(user, password):
            token = secrets.token_urlsafe(32)
            with _AUTH_LOCK:
                for k in [k for k, s in _SESSIONS.items()
                          if now - s["seen"] > SESSION_IDLE or now - s["created"] > SESSION_MAX]:
                    del _SESSIONS[k]
                _SESSIONS[token] = {"user": user, "ip": ip, "created": now, "seen": now}
                _FAILS.pop(ip, None)
            log("login ok: %s  <- %s" % (user, ip))
            self._redirect("/", "%s=%s; Path=/; HttpOnly; Secure; SameSite=Strict; Max-Age=%d"
                           % (SESSION_COOKIE, token, SESSION_MAX))
            return

        with _AUTH_LOCK:
            _FAILS.setdefault(ip, []).append(now)
            _ALL_FAILS.append(now)
        log("login failed: %r  <- %s" % (user[:32], ip))
        time.sleep(1)
        self._login_page("帳號或密碼不對。", 401)

    def _logout(self):
        cookie = http.cookies.SimpleCookie()
        try:
            cookie.load(self.headers.get("Cookie") or "")
        except http.cookies.CookieError:
            pass
        if SESSION_COOKIE in cookie:
            with _AUTH_LOCK:
                s = _SESSIONS.pop(cookie[SESSION_COOKIE].value, None)
            if s:
                log("logout: %s  <- %s" % (s["user"], self._who()))
        self._redirect("/login", "%s=; Path=/; HttpOnly; Secure; SameSite=Strict; Max-Age=0"
                       % SESSION_COOKIE)

    def _page(self):
        try:
            with open(PAGE_PATH, encoding="utf-8") as fh:
                html = fh.read()
        except OSError:
            self._send(500, b"web-console.html not found", "text/plain")
            return
        html = html.replace("只接受內網連線。", "遠端入口，已登入。")
        html = html.replace("</body>",
                            '<a href="/logout" style="position:fixed;top:12px;right:14px;'
                            'padding:6px 12px;background:#8a3b2c;color:#fff;text-decoration:none;'
                            'font-weight:700;z-index:9">登出</a></body>')
        self._send(200, html, "text/html; charset=utf-8")

    def do_GET(self):
        if not self._gate():
            return
        path = self.path.split("?")[0]
        if path == "/login":
            self._login_page()
            return
        if path == "/logout":
            self._logout()
            return
        if not self._session():
            if path.startswith("/api/"):
                self._json(401, {"error": "請先登入"})
            else:
                self._redirect("/login")
            return
        if path in ("/", "/index.html"):
            self._page()
            return
        super().do_GET()

    def do_POST(self):
        if not self._gate():
            return
        if self.path.split("?")[0] == "/login":
            self._login()
            return
        if not self._session():
            self._json(401, {"error": "請先登入"})
            return
        super().do_POST()


class Server(ThreadingHTTPServer):
    # On Windows SO_REUSEADDR lets a second process bind a port that is
    # already in use, and the two would quietly split the requests. Without
    # it a second copy fails to start, which is what we want.
    allow_reuse_address = os.name != "nt"


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

    try:
        server = Server((args.host, args.port), Handler)
    except OSError:
        # The desktop shortcut on a machine where the logon task already
        # runs the console: show that one instead of failing.
        print("控制台已經在執行，開啟瀏覽器…", flush=True)
        webbrowser.open("http://127.0.0.1:%d" % args.port)
        time.sleep(3)
        return
    shown = lan_address() if args.host == "0.0.0.0" else args.host

    public_port = settings.get("webConsole", "publicPort", default=None)
    if public_port:
        public = Server(("127.0.0.1", int(public_port)), PublicHandler)
        threading.Thread(target=public.serve_forever, daemon=True).start()

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
    print(" 非私有位址的連線一律拒絕。不要幫這個埠開隧道。")
    if public_port:
        print(" 遠端入口 127.0.0.1:%d（只給 Cloudflare 隧道，要登入帳號密碼）"
              % int(public_port))
        print("          帳號：%s" % (console_auth.configured_user() or "（還沒設定）"))
    print("=" * 62, flush=True)

    log("console started on %s:%d%s" % (
        args.host, args.port,
        ", public entrance on 127.0.0.1:%d" % int(public_port) if public_port else ""))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n收到中斷，關閉中…")
        server.shutdown()


if __name__ == "__main__":
    main()
