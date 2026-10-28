#!/usr/bin/env python3
"""Discord control bot for the Minecraft server.

Lets an allow-listed Discord user start, stop and check the server from a
phone. Uses slash commands only, so it needs no privileged intents and never
reads message content.

Nothing listens for inbound connections: the bot makes an outgoing websocket
to Discord, which is why this works behind the double NAT here.

Run:  python discord-control.py
Config: discord-control.config.json next to this file.
"""

import asyncio
import json
import logging
import logging.handlers
import os
import socket
import struct
import subprocess
import sys
import time

import discord
from discord import app_commands
from discord.ext import tasks

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import settings  # noqa: E402

import importlib.util  # noqa: E402

# The tunnel probes live in check-server.py, shared with both consoles. Its
# name has a hyphen, so it is loaded by path.
_spec = importlib.util.spec_from_file_location(
    "probe", os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "check-server.py"))
probe = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(probe)

# Planned stops and restarts go through the 5-minute in-game countdown the
# server rules promise players.
_spec = importlib.util.spec_from_file_location(
    "sequence", os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "restart-sequence.py"))
sequence = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sequence)

# /inv reads player inventories with the same code as the web console's
# InvSee++ panel - straight from the player files, so it works with the server
# up or down. plugin_panels wants the rcon.py module itself (this file's own
# rcon() is a subprocess wrapper with a different signature).
import rcon as rcon_client  # noqa: E402
import plugin_panels  # noqa: E402
plugin_panels.setup(rcon_client)
# The web console's public entrance account (/console-password).
import console_auth  # noqa: E402

# The bot runs under pythonw.exe, which has no console of its own. Any console
# child it spawns therefore gets a brand new window - and playit_running() runs
# once a minute, so a cmd window was popping up over the game every 60 seconds.
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

HERE = os.path.dirname(os.path.abspath(__file__))
LOG_PATH = os.path.join(HERE, "discord-control.log")
# discord.py's own log goes in its own file, on a rotating handler. It cannot
# share LOG_PATH: the trimming in log() rewrites that file in place, which
# would pull the floor out from under an open handler.
GATEWAY_LOG_PATH = os.path.join(HERE, "discord-gateway.log")

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def log(msg):
    """Print and append to file. Under pythonw.exe (how the scheduled task
    runs this) stdout goes nowhere, so the file is the only record."""
    line = f"{time.strftime('%Y-%m-%d %H:%M:%S')}  {msg}"
    print(line, flush=True)
    try:
        if os.path.exists(LOG_PATH) and os.path.getsize(LOG_PATH) > 1_000_000:
            with open(LOG_PATH, encoding="utf-8", errors="replace") as fh:
                tail = fh.readlines()[-200:]
            with open(LOG_PATH, "w", encoding="utf-8") as fh:
                fh.writelines(tail)
        with open(LOG_PATH, "a", encoding="utf-8") as fh:
            fh.write(line + chr(10))
    except Exception:
        pass


# ------------------------------------------------------------------- config
def load_config():
    """Build the bot's settings from the toolkit-wide config.json.

    Flattened into the shape the rest of this file already expects, so the
    single shared config file is the only thing an install has to edit.
    """
    cfg = {
        "tokenFile": settings.require("discord", "tokenFile"),
        "serverDir": settings.server_dir(),
        "startBat": settings.get(
            "startBat", default=os.path.join(settings.server_dir(), "start.bat")),
        "authorizedUserIds": settings.require("discord", "authorizedUserIds"),
        "rconUserIds": settings.get("discord", "rconUserIds", default=None),
        "javaAddress": settings.require("java", "host"),
        "bedrockAddress": settings.require("bedrock", "host"),
        "bedrockPort": settings.get("bedrock", "tunnelPort", default=19132),
        "mapUrl": settings.get("mapUrl", default=""),
        "logChannelId": settings.get("discord", "logChannelId", default=""),
        "bluemapMaps": settings.get("bluemapMaps", default=None),
    }

    with open(cfg["tokenFile"], encoding="utf-8") as fh:
        cfg["_token"] = fh.read().strip()
    if not cfg["_token"]:
        raise SystemExit(f"token file is empty: {cfg['tokenFile']}")

    cfg["authorizedUserIds"] = [int(u) for u in cfg["authorizedUserIds"]]
    # RCON is full server control, so it gets its own list. Falls back to
    # authorizedUserIds when not set.
    cfg["rconUserIds"] = [int(u) for u in cfg.get("rconUserIds") or cfg["authorizedUserIds"]]
    cfg["bedrockPort"] = int(cfg["bedrockPort"])
    cfg["logChannelId"] = int(cfg.get("logChannelId") or 0)
    cfg["bluemapMaps"] = cfg.get("bluemapMaps") or ["overworld", "world", "world_the_end"]
    return cfg


CFG = load_config()


# ------------------------------------------------- Java Edition status probe
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
            raise IOError("closed")
        b = b[0]
        n |= (b & 0x7F) << shift
        if not b & 0x80:
            return n
        shift += 7


def server_status(timeout=5):
    """Return None if the local server is down, else version/player info."""
    host, port = "127.0.0.1", 25565
    try:
        with socket.create_connection((host, port), timeout=timeout) as sock:
            hs = (b"\x00" + _varint(775) + _varint(len(host)) + host.encode()
                  + struct.pack("!H", port) + b"\x01")
            sock.sendall(_varint(len(hs)) + hs)
            sock.sendall(_varint(1) + b"\x00")
            _read_varint(sock)
            _read_varint(sock)
            n = _read_varint(sock)
            buf = b""
            while len(buf) < n:
                chunk = sock.recv(n - len(buf))
                if not chunk:
                    break
                buf += chunk
        d = json.loads(buf.decode("utf-8"))
        players = d.get("players", {})
        return {
            "version": d.get("version", {}).get("name", "?"),
            "online": players.get("online", 0),
            "max": players.get("max", 0),
            "list": [p.get("name", "?") for p in (players.get("sample") or [])],
        }
    except Exception:
        return None


# ------------------------------------------------------------ tunnel probes
# The checks themselves live in check-server.py, so the bot, both consoles and
# the command-line check all judge each path (playit, Warden, cloudflared) the
# same way.
def playit_running():
    return probe.playit_running()


def tunnel_report():
    """One line describing whether outsiders can actually get in."""
    down = [n for n, r in probe.tunnel_services() if not r]
    if down:
        return False, f"🔴 隧道未啟動（{'、'.join(down)} 沒在執行）"
    ok, detail, _ = probe.tunnel_status()
    if not ok:
        return False, f"🟠 公開位址測試失敗：{detail}"
    outside, odetail, _ = probe.external_view()
    if outside is False:
        return False, f"🟠 這台測得到，但外部檢測失敗：{odetail}"
    return True, "🟢 隧道正常，外部連得進來"


def restart_playit():
    """Try to bring the playit service back up. Returns True if it is running
    afterwards. The service accepts start/stop without elevation here."""
    try:
        subprocess.run(["sc", "start", "playitd"], capture_output=True, timeout=30,
                       creationflags=NO_WINDOW)
    except Exception as exc:
        log(f"playit restart failed: {exc}")
        return False
    time.sleep(20)
    return playit_running()


def rcon(*commands):
    """Run commands through the existing, tested rcon.py helper."""
    try:
        proc = subprocess.run(
            [sys.executable, os.path.join(HERE, "rcon.py"), *commands],
            cwd=CFG["serverDir"], capture_output=True, text=True, timeout=60,
            creationflags=NO_WINDOW,
        )
        return proc.returncode == 0, (proc.stdout or proc.stderr).strip()
    except Exception as exc:
        return False, str(exc)


def launch_server():
    # Detached and windowless - see settings.server_launch_command.
    subprocess.Popen(
        settings.server_launch_command(CFG["startBat"]),
        cwd=CFG["serverDir"],
        creationflags=NO_WINDOW,
    )


def run_map_sync():
    """Push the rendered map to Cloudflare Pages.

    cwd matters: wrangler writes temp files into the working directory, and a
    directory under Documents would be blocked by Controlled Folder Access,
    hanging the process forever.
    """
    try:
        proc = subprocess.run(
            ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
             "-File", os.path.join(HERE, "sync-map.ps1")],
            cwd=CFG["serverDir"], capture_output=True, text=True, timeout=900,
            creationflags=NO_WINDOW,
        )
        return proc.returncode == 0, (proc.stdout or proc.stderr).strip()
    except Exception as exc:
        return False, str(exc)


def bluemap_idle():
    ok, out = rcon("bluemap")
    return ok and "render-threads are idle" in out


def addresses_block():
    if probe.JAVA_VIA == "cloudflared":
        # A Cloudflare Tunnel only carries raw TCP to clients running
        # cloudflared access.
        java = (f"Java：先執行 `cloudflared access tcp --hostname {CFG['javaAddress']}"
                f" --url localhost:25565`，再連 `localhost:25565`")
    else:
        java = f"Java：`{CFG['javaAddress']}`（直接輸入，不用連接埠）"
    if probe.BE_VIA == "warden":
        bedrock = (f"基岩：`{CFG['bedrockAddress']}`（26.40 以上；"
                   f"26.60 之前連接埠填 `443`）")
    else:
        bedrock = f"基岩：`{CFG['bedrockAddress']}` 連接埠 `{CFG['bedrockPort']}`"
    return java + "\n" + bedrock


# --------------------------------------------------------------- monitoring
# Only state *changes* are announced. Polling every minute and posting the
# current state would turn the channel into noise nobody reads.
# A single failed tunnel probe is not evidence of an outage. The Java-side
# check asks mcstatus.io, whose answer is cached for about a minute, so one
# unlucky probe on their side turns into a "tunnel down" alert here. Measured
# on a healthy server: five such alerts in 42 minutes, every one recovering
# within one or two polls, while the playit agent logged no errors at all and
# kept forwarding traffic the whole time.
#
# Retrying straight away would just re-read the same cached answer, so
# confirmation has to wait for the next tick. Recovery is not debounced -
# there is no cost to reporting good news immediately.
TUNNEL_FAIL_THRESHOLD = 2

STATE = {"server": None, "tunnel": None, "sync_size": None, "tunnel_fails": 0,
         "last_beat": 0.0, "last_latency": None, "latency_same": 0}
LOG_CHANNEL = None


def new_sync_errors():
    """Return ERROR lines appended to sync-map.log since the last check."""
    path = os.path.join(HERE, "sync-map.log")
    try:
        size = os.path.getsize(path)
    except OSError:
        return []

    previous = STATE["sync_size"]
    STATE["sync_size"] = size
    if previous is None or size <= previous:
        return []

    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            fh.seek(previous)
            fresh = fh.read()
    except OSError:
        return []

    return [ln for ln in fresh.splitlines() if "[ERROR]" in ln]


async def monitor_tick():
    channel = LOG_CHANNEL or bot.get_channel(CFG["logChannelId"])
    if channel is None:
        return

    st = await asyncio.to_thread(server_status)
    up = st is not None

    if STATE["server"] is not None and up != STATE["server"]:
        if up:
            await channel.send(f"🟢 伺服器已啟動　`{st['version']}`")
        else:
            await channel.send("🔴 伺服器已停止")
        log(f"event: server up={up}")
    STATE["server"] = up

    # A tunnel check only means something while the server is running.
    if up:
        ok, detail = await asyncio.to_thread(tunnel_report)

        # Self-heal: the most common failure by far is the playit service
        # being stopped (a stale cleanup from a previous run does this).
        # Restarting it is safe and fixes the outage without waking anyone.
        if (not ok and "playit" in (probe.JAVA_VIA, probe.BE_VIA)
                and not await asyncio.to_thread(playit_running)):
            log("tunnel down and playit stopped - attempting restart")
            healed = await asyncio.to_thread(restart_playit)
            if healed:
                await channel.send("🔧 偵測到 playit 停止，已自動重啟")
                log("playit restarted automatically")
                ok, detail = await asyncio.to_thread(tunnel_report)

        if ok:
            STATE["tunnel_fails"] = 0
        else:
            STATE["tunnel_fails"] += 1

        if not ok and STATE["tunnel_fails"] < TUNNEL_FAIL_THRESHOLD:
            # Not reported yet, but recorded: a burst of these in the log is
            # how a genuinely flaky tunnel is told apart from a flaky checker.
            log(f"tunnel probe failed "
                f"({STATE['tunnel_fails']}/{TUNNEL_FAIL_THRESHOLD}), "
                f"awaiting confirmation: {detail}")
        else:
            first_look = STATE["tunnel"] is None
            changed = not first_look and ok != STATE["tunnel"]
            # Report a broken tunnel even on the first observation. Treating
            # the first look as a silent baseline meant a tunnel that was
            # already down when the server started never got reported at all.
            if changed or (first_look and not ok):
                if ok:
                    await channel.send("🟢 隧道已恢復，外部連得進來")
                else:
                    await channel.send(detail)
                log(f"event: tunnel ok={ok} detail={detail}")
            STATE["tunnel"] = ok
    else:
        STATE["tunnel"] = None
        STATE["tunnel_fails"] = 0

    # backup-world.ps1 leaves this marker if it could not turn auto-saving
    # back on. That must never sit unnoticed - the world would stop saving.
    # watchdog.ps1 leaves this when the server produced a crash report.
    crash = os.path.join(HERE, "CRASH-WARNING")
    if os.path.exists(crash):
        try:
            name = open(crash, encoding="utf-8", errors="replace").read().strip()
        except OSError:
            name = "(讀取失敗)"
        await channel.send("💥 **伺服器產生了崩潰報告**" + chr(10) + "`" + name[:200] + "`")
        log("event: crash report")
        try:
            os.remove(crash)
        except OSError:
            pass

    marker = os.path.join(HERE, "SAVE-OFF-WARNING")
    if os.path.exists(marker):
        await channel.send(
            "🔴 **自動存檔可能仍是關閉的**" + chr(10)
            + "備份腳本無法恢復存檔，請執行 `/rcon command: save-on` 確認。"
        )
        log("event: save-off warning")
        try:
            os.remove(marker)
        except OSError:
            pass

    # backup-world.ps1 leaves this when the new backup did not verify.
    marker = os.path.join(HERE, "BACKUP-WARNING")
    if os.path.exists(marker):
        try:
            name = open(marker, encoding="utf-8-sig", errors="replace").read().strip()
        except OSError:
            name = "(讀取失敗)"
        await channel.send(
            "🔴 **今天的備份沒有通過檢查**" + chr(10)
            + "`" + name[:200] + "`" + chr(10)
            + "舊的備份都保留著。請看 `windows\\backup-world.log`。"
        )
        log("event: backup verification failed")
        try:
            os.remove(marker)
        except OSError:
            pass

    for line in (await asyncio.to_thread(new_sync_errors))[:3]:
        await channel.send("⚠️ 地圖同步失敗" + chr(10) + "```" + line[:400] + "```")
        log("event: map sync error")


# ------------------------------------------------------------------- the bot
class Control(discord.Client):
    def __init__(self):
        # No privileged intents and no message content. The guilds intent is
        # NOT privileged and is required for a channel cache - without it
        # get_channel() always returns None and monitoring dies silently.
        intents = discord.Intents.none()
        intents.guilds = True
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def on_ready(self):
        log(f"logged in as {self.user} ({self.user.id})")
        # Resolve the log channel now: get_channel() returning None later
        # would make monitoring fail silently, which is the worst outcome
        # for something whose whole job is to tell you when things break.
        if CFG["logChannelId"]:
            ch = self.get_channel(CFG["logChannelId"])
            if ch is None:
                try:
                    ch = await self.fetch_channel(CFG["logChannelId"])
                except Exception as exc:
                    ch = None
                    log(f"log channel {CFG['logChannelId']} unreachable: {exc}")
            if ch is not None:
                globals()["LOG_CHANNEL"] = ch
                log(f"event log channel: #{getattr(ch, 'name', ch.id)}")
        else:
            log("no logChannelId configured - event reporting disabled")

        if not self.monitor_loop.is_running():
            self.monitor_loop.start()
        for guild in self.guilds:
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            log(f"slash commands synced to guild: {guild.name}")


    @tasks.loop(seconds=60)
    async def monitor_loop(self):
        self.check_gateway()
        try:
            await monitor_tick()
        except Exception as exc:
            log(f"monitor error: {exc}")

    def check_gateway(self):
        """Notice a gateway that has died without the process noticing.

        The failure this exists for: the websocket to Discord goes away, the
        TCP socket stays ESTABLISHED, and discord.py never reconnects. From
        in here everything looks fine - and because channel.send() is a plain
        HTTP call, all the monitoring below keeps posting to Discord
        perfectly. From the outside the bot is simply gone: slash commands
        reach it over the gateway, so none of them arrive.

        is_closed() and ws is None both stay false in that state, so they
        cannot be the test. What does give it away is latency, which is the
        gap between the last heartbeat and its ack: while the gateway lives
        that value is rewritten about every 41s, so a tick that sees the
        exact same float as the tick before it saw no ack for a minute.
        Five in a row is five minutes of silence - long past a missed
        heartbeat, and not something a healthy connection produces.
        """
        latency = self.latency
        if self.is_closed() or self.ws is None:
            dead, why = True, "socket closed"
        elif latency == STATE["last_latency"]:
            STATE["latency_same"] += 1
            dead = STATE["latency_same"] >= 5
            why = f"no heartbeat ack for {STATE['latency_same']} tick(s)"
        else:
            STATE["last_latency"] = latency
            STATE["latency_same"] = 0
            dead, why = False, ""

        if dead:
            # Exit rather than reconnect by hand: the scheduled task is
            # already set to restart a failed run (3 attempts, 5 minutes
            # apart), and that path has always been dead code because this
            # process never ends. A non-zero exit finally connects it.
            log(f"gateway looks dead ({why}) - exiting so the scheduled "
                f"task restarts the bot")
            os._exit(1)

        now = time.time()
        if now - STATE["last_beat"] >= 1800:
            STATE["last_beat"] = now
            # Silence in this log used to be ambiguous: a healthy bot with
            # nothing to report reads exactly like a dead one. It cost hours
            # of guessing once. A line every half hour settles it.
            log("alive, gateway latency %.0f ms" % (latency * 1000))

    @monitor_loop.before_loop
    async def before_monitor(self):
        await self.wait_until_ready()


bot = Control()


def authorized(interaction):
    return interaction.user.id in CFG["authorizedUserIds"]


async def deny(interaction):
    log(f"denied {interaction.user} ({interaction.user.id})")
    await interaction.response.send_message(
        "你沒有權限操作這台伺服器。", ephemeral=True
    )


@bot.tree.command(name="status", description="查看伺服器狀態")
async def status_cmd(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    st = await asyncio.to_thread(server_status)
    if not st:
        await interaction.followup.send("🔴 伺服器**沒有在執行**。用 `/start` 開機。")
        return
    _, tunnel = await asyncio.to_thread(tunnel_report)
    who = ("\n線上：" + "、".join(st["list"])) if st["list"] else ""
    await interaction.followup.send(
        f"🟢 伺服器執行中\n版本：`{st['version']}`\n"
        f"人數：**{st['online']}/{st['max']}**{who}\n{tunnel}"
    )


@bot.tree.command(name="start", description="啟動伺服器")
@app_commands.default_permissions(manage_guild=True)
async def start_cmd(interaction: discord.Interaction):
    if not authorized(interaction):
        return await deny(interaction)

    if await asyncio.to_thread(server_status):
        return await interaction.response.send_message("伺服器已經在執行了。", ephemeral=True)

    await interaction.response.defer(ephemeral=True)
    log(f"start requested by {interaction.user}")
    launch_server()

    # Paper plus seven plugins takes roughly half a minute to come up.
    st = None
    for _ in range(40):
        await asyncio.sleep(3)
        st = await asyncio.to_thread(server_status)
        if st:
            break

    if not st:
        await interaction.followup.send(
            "⚠️ 兩分鐘內還沒起來。可能還在啟動，或是啟動失敗 —— 用 `/status` 再看一次。"
        )
        log("start finished, server did not come up")
        return

    # Answering on localhost does not mean anyone can reach it: a late cleanup
    # from a previous run can stop the tunnel seconds after this one starts it.
    ok, tunnel = False, ""
    for _ in range(6):
        ok, tunnel = await asyncio.to_thread(tunnel_report)
        if ok:
            break
        await asyncio.sleep(10)

    head = "✅ 伺服器已啟動" if ok else "⚠️ 伺服器啟動了，但外面可能還連不進來"
    await interaction.followup.send(
        f"{head}\n版本：`{st['version']}`\n{tunnel}\n\n{addresses_block()}"
    )
    log(f"start finished, tunnel_ok={ok}")


async def _countdown(interaction, mode):
    if not authorized(interaction):
        return await deny(interaction)
    st = await asyncio.to_thread(server_status)
    if not st:
        return await interaction.response.send_message("伺服器本來就沒在跑。", ephemeral=True)
    await interaction.response.defer(ephemeral=True)
    log(f"{mode} requested by {interaction.user}")
    ok, msg = await asyncio.to_thread(sequence.launch, mode, None, f"discord {interaction.user}")
    if ok and st["online"]:
        who = "、".join(st["list"]) or f"{st['online']} 人"
        msg += f"\n線上：{who}。可以用 `/cancel` 取消。"
    await interaction.followup.send(("⏳ " if ok else "⚠️ ") + msg, ephemeral=True)


@bot.tree.command(name="stop", description="關閉伺服器（遊戲裡先倒數 5 分鐘）")
@app_commands.default_permissions(manage_guild=True)
async def stop_cmd(interaction: discord.Interaction):
    await _countdown(interaction, "stop")


@bot.tree.command(name="restart", description="重啟伺服器（遊戲裡先倒數 5 分鐘）")
@app_commands.default_permissions(manage_guild=True)
async def restart_cmd(interaction: discord.Interaction):
    await _countdown(interaction, "restart")


@bot.tree.command(name="cancel", description="取消進行中的關閉／重啟倒數")
@app_commands.default_permissions(manage_guild=True)
async def cancel_cmd(interaction: discord.Interaction):
    if not authorized(interaction):
        return await deny(interaction)
    cur = await asyncio.to_thread(sequence.pending)
    if not cur:
        return await interaction.response.send_message("沒有進行中的倒數。", ephemeral=True)
    await asyncio.to_thread(sequence.request_cancel)
    log(f"countdown cancelled by {interaction.user}")
    await interaction.response.send_message("✅ 已取消倒數，遊戲裡會公告。", ephemeral=True)


@bot.tree.command(name="rcon", description="執行伺服器指令（完整權限，請小心）")
@app_commands.default_permissions(manage_guild=True)
@app_commands.describe(command="要執行的指令，不用加斜線。例如：whitelist list")
async def rcon_cmd(interaction: discord.Interaction, command: str):
    if interaction.user.id not in CFG["rconUserIds"]:
        return await deny(interaction)

    if not await asyncio.to_thread(server_status):
        return await interaction.response.send_message(
            "伺服器沒在執行，RCON 連不上。", ephemeral=True
        )

    # Ephemeral: RCON output can contain whitelists, player IPs and other
    # things the rest of the channel has no business seeing.
    await interaction.response.defer(ephemeral=True)
    log(f"rcon by {interaction.user}: {command}")

    ok, out = await asyncio.to_thread(rcon, command)
    body = out.strip() or "(伺服器沒有回傳文字)"
    # Discord caps a message at 2000 characters; leave room for the wrapper.
    if len(body) > 1800:
        body = body[:1800] + chr(10) + "…（輸出過長，已截斷）"

    prefix = "" if ok else "⚠️ 執行失敗" + chr(10)
    await interaction.followup.send(f"{prefix}```{body}```")


@bot.tree.command(name="render", description="重新渲染地圖並立刻上傳網站")
@app_commands.default_permissions(manage_guild=True)
async def render_cmd(interaction: discord.Interaction):
    if not authorized(interaction):
        return await deny(interaction)

    if not await asyncio.to_thread(server_status):
        return await interaction.response.send_message(
            "伺服器沒在執行，BlueMap 也沒跑。", ephemeral=True
        )

    await interaction.response.defer(ephemeral=True)
    log(f"render requested by {interaction.user}")

    await asyncio.to_thread(
        rcon, *[f"bluemap update {m}" for m in CFG["bluemapMaps"]]
    )

    # Wait for the render threads to go quiet before uploading, otherwise we
    # would publish a half-rendered map.
    rendered = False
    for _ in range(40):
        await asyncio.sleep(10)
        if await asyncio.to_thread(bluemap_idle):
            rendered = True
            break

    if not rendered:
        await interaction.followup.send(
            "⚠️ 渲染超過 7 分鐘還沒結束，先不上傳。用 `/rcon command: bluemap` 看進度。"
        )
        return

    # Without a Cloudflare Pages project the map is served live (through the
    # tunnel), so there is nothing to upload.
    if not settings.get("cloudflare", "projectName"):
        await interaction.followup.send("🗺️ 地圖已重新渲染" + chr(10) + CFG["mapUrl"])
        log("render finished (live map, no upload)")
        return

    ok, out = await asyncio.to_thread(run_map_sync)
    if not ok:
        tail = out.strip().splitlines()[-3:] if out.strip() else ["(沒有輸出)"]
        return await interaction.followup.send(
            "⚠️ 渲染完成，但上傳失敗" + chr(10) + "```" + chr(10).join(tail)[:600] + "```"
        )

    changed = ""
    for line in out.splitlines():
        if "Success! Uploaded" in line:
            changed = line.split("wrangler:")[-1].strip()
            break

    await interaction.followup.send(
        "🗺️ 地圖已重新渲染並上傳" + (chr(10) + "`" + changed + "`" if changed else "")
        + chr(10) + CFG["mapUrl"]
    )
    log("render finished")


@bot.tree.command(name="ip", description="顯示連線位址")
async def ip_cmd(interaction: discord.Interaction):
    st = await asyncio.to_thread(server_status)
    version = f"（需要 {st['version'].split()[-1]}）" if st else ""
    await interaction.response.send_message(
        f"**連線位址**{version}\n{addresses_block()}\n\n"
        f"**世界地圖**\n{CFG['mapUrl']}"
        , ephemeral=True
    )


def _item_text(it):
    text = discord.utils.escape_markdown(it["custom"] or it["name"])
    if it["custom"]:
        text += f"（{it['name']}）"
    if it.get("count", 1) > 1:
        text += f" ×{it['count']}"
    if it["enchants"]:
        text += "｜" + "、".join(it["enchants"])
    return text


def _add_lines(embed, title, lines):
    """Lines as one or more fields, each under Discord's 1024-character cap."""
    if not lines:
        embed.add_field(name=title, value="（空的）", inline=False)
        return
    chunk, part = [], 0
    for line in lines:
        if chunk and len(chr(10).join(chunk + [line])) > 1000:
            embed.add_field(name=title if part == 0 else title + "（續）",
                            value=chr(10).join(chunk), inline=False)
            chunk, part = [], part + 1
        chunk.append(line)
    embed.add_field(name=title if part == 0 else title + "（續）",
                    value=chr(10).join(chunk), inline=False)


def inventory_embeds(d):
    """Three embeds - status and equipment with the hotbar, the main
    inventory, the ender chest - each well under Discord's 6000-character cap."""
    colour = 0x4F6238
    slots = {int(k): v for k, v in d["slots"].items()}
    ender = {int(k): v for k, v in d["ender"].items()}

    head = discord.Embed(
        title=f"{discord.utils.escape_markdown(d['player'])} 的背包",
        description=(f"{'🟢 在線上' if d['online'] else '⚫ 離線'}｜存檔於 {d['saved']}\n"
                     f"位置 {d['where']}｜{d['mode']}模式\n"
                     f"生命 {d['health']}｜飢餓 {d['food']}｜等級 {d['level']}"),
        colour=colour)
    _add_lines(head, "裝備", [f"{e['label']}：{_item_text(e['item'])}"
                            for e in d["equipment"] if e["item"]])
    _add_lines(head, "快捷欄", [
        f"{'▶' if k == d['selected'] else '　'}`{k + 1}` {_item_text(slots[k])}"
        for k in range(9) if k in slots])

    main = discord.Embed(colour=colour)
    _add_lines(main, "背包", [f"`{k:>2}` {_item_text(slots[k])}"
                            for k in range(9, 36) if k in slots])

    chest = discord.Embed(colour=colour)
    _add_lines(chest, "終界箱", [f"`{k:>2}` {_item_text(ender[k])}"
                              for k in sorted(ender)])
    return [head, main, chest]


async def _player_choices(interaction: discord.Interaction, current: str):
    names = await asyncio.to_thread(plugin_panels.known_players)
    cur = current.lower()
    return [app_commands.Choice(name=n, value=n) for n in names if cur in n.lower()][:25]


@bot.tree.command(name="inv", description="查看玩家的背包、裝備和終界箱（只能看，不能改）")
@app_commands.default_permissions(manage_guild=True)
@app_commands.describe(player="玩家名稱（基岩版玩家前面有一個點）")
@app_commands.autocomplete(player=_player_choices)
async def inv_cmd(interaction: discord.Interaction, player: str):
    if not authorized(interaction):
        return await deny(interaction)
    # Ephemeral: someone's inventory and position are nobody else's business.
    await interaction.response.defer(ephemeral=True)
    log(f"inventory of {player} requested by {interaction.user}")
    try:
        data = await asyncio.to_thread(plugin_panels.inventory, player)
    except plugin_panels.BadInput as exc:
        return await interaction.followup.send(f"⚠️ {exc}", ephemeral=True)
    except Exception as exc:
        log(f"inventory of {player} failed: {exc}")
        return await interaction.followup.send(f"⚠️ 讀不到背包：{exc}", ephemeral=True)
    for embed in inventory_embeds(data):
        await interaction.followup.send(embed=embed, ephemeral=True)


class ConsolePasswordModal(discord.ui.Modal, title="網頁控制台遠端入口的帳號密碼"):
    """A Discord form rather than command options: options are echoed in the
    channel's command log, a modal's fields are not."""

    def __init__(self, current_user):
        super().__init__()
        self.username = discord.ui.TextInput(
            label="帳號（英文字母、數字、_ . -）", max_length=32,
            default=current_user or None)
        self.password = discord.ui.TextInput(
            label="密碼（至少 %d 個字）" % console_auth.MIN_PASSWORD,
            min_length=console_auth.MIN_PASSWORD, max_length=128)
        self.again = discord.ui.TextInput(
            label="再輸入一次密碼",
            min_length=console_auth.MIN_PASSWORD, max_length=128)
        for item in (self.username, self.password, self.again):
            self.add_item(item)

    async def on_submit(self, interaction: discord.Interaction):
        if self.password.value != self.again.value:
            return await interaction.response.send_message(
                "⚠️ 兩次密碼不一樣，沒有變更。", ephemeral=True)
        name = self.username.value.strip()
        try:
            await asyncio.to_thread(console_auth.set_login, name, self.password.value)
        except ValueError as exc:
            return await interaction.response.send_message(f"⚠️ {exc}，沒有變更。", ephemeral=True)
        log(f"web console login set to user {name!r} by {interaction.user}")
        url = settings.get("webConsole", "publicUrl", default="")
        # The control token only lives on this machine; a phone logging in
        # from outside for the first time has no other way to get it.
        token = (await asyncio.to_thread(console_auth._read)).get("token", "")
        await interaction.response.send_message(
            f"✅ 已設定帳號 **{discord.utils.escape_markdown(name)}**，立即生效。\n{url}\n"
            f"登入後，按鈕和指令還需要控制權杖：||{token}||（點一下顯示，只有你看得到）",
            ephemeral=True)


@bot.tree.command(name="console-password",
                  description="設定網頁控制台遠端入口的帳號密碼")
@app_commands.default_permissions(manage_guild=True)
async def console_password_cmd(interaction: discord.Interaction):
    # Same trust as /rcon: the console can run any command too.
    if interaction.user.id not in CFG["rconUserIds"]:
        return await deny(interaction)
    current = await asyncio.to_thread(console_auth.configured_user)
    await interaction.response.send_modal(ConsolePasswordModal(current))


if __name__ == "__main__":
    log("starting Discord control bot")
    # log_handler=None used to disable discord.py's logging completely. Under
    # pythonw.exe there is no stderr either, so everything the library had to
    # say about the connection - reconnects, resumes, heartbeats it never got
    # an ack for - went nowhere at all. A gateway could die and leave not one
    # line anywhere. Give it a real file instead.
    handler = logging.handlers.RotatingFileHandler(
        GATEWAY_LOG_PATH, maxBytes=1_000_000, backupCount=2,
        encoding="utf-8", errors="replace")
    handler.setFormatter(logging.Formatter(
        "%(asctime)s  %(levelname)-8s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"))
    bot.run(CFG["_token"], log_handler=handler, log_level=logging.INFO)
