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
import urllib.request

import discord
from discord import app_commands
from discord.ext import tasks

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import settings  # noqa: E402

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
RAKNET_MAGIC = bytes.fromhex("00ffff00fefefefefdfdfdfd12345678")


def bedrock_tunnel_ok(timeout=6):
    """RakNet unconnected ping through the public Bedrock tunnel.

    Unlike the Java tunnel, playit does not block connections coming from the
    agent's own address over UDP, so this one can be checked from here.
    """
    pkt = (b"\x01" + struct.pack(">Q", int(time.time() * 1000)) + RAKNET_MAGIC
           + struct.pack(">Q", 0x1234567890ABCDEF))
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(timeout)
    try:
        s.sendto(pkt, (CFG["bedrockAddress"], CFG["bedrockPort"]))
        data, _ = s.recvfrom(4096)
        return bool(data) and data[0] == 0x1C
    except Exception:
        return False
    finally:
        s.close()


def playit_running():
    try:
        out = subprocess.run(["sc", "query", "playitd"], capture_output=True,
                             text=True, timeout=15,
                             creationflags=NO_WINDOW).stdout
        return "RUNNING" in out
    except Exception:
        return False


def outside_view(timeout=20):
    """Ask a third party whether the Java tunnel is reachable.

    playit refuses connections to a tunnel from the agent's own public IP, so
    an outside vantage point is the only way to check the Java side.
    Returns True, False, or None when the checker itself did not answer.
    """
    url = f"https://api.mcstatus.io/v2/status/java/{CFG['javaAddress']}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "mc-control-bot"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return bool(json.loads(resp.read().decode("utf-8")).get("online"))
    except Exception:
        return None


def tunnel_report():
    """One line describing whether outsiders can actually get in."""
    if not playit_running():
        return False, "🔴 隧道未啟動（playit 服務停止中）"
    if not bedrock_tunnel_ok():
        return False, "🟠 playit 執行中，但公開位址沒有回應"
    outside = outside_view()
    if outside is False:
        return False, "🟠 基岩隧道正常，但外部看不到 Java 版"
    if outside is None:
        return True, "🟢 隧道正常（外部檢測服務無回應，未能複查）"
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
    # cmd /c start detaches the batch file into its own window, so the bot is
    # not the server's parent and can be restarted without killing it.
    subprocess.Popen(
        ["cmd", "/c", "start", "MC Server", "/min", CFG["startBat"], "/nopause"],
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
    return (f"Java：`{CFG['javaAddress']}`\n"
            f"基岩：`{CFG['bedrockAddress']}` 連接埠 `{CFG['bedrockPort']}`")


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
        if not ok and not await asyncio.to_thread(playit_running):
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


@bot.tree.command(name="stop", description="關閉伺服器（會先存檔）")
@app_commands.default_permissions(manage_guild=True)
async def stop_cmd(interaction: discord.Interaction):
    if not authorized(interaction):
        return await deny(interaction)

    st = await asyncio.to_thread(server_status)
    if not st:
        return await interaction.response.send_message("伺服器本來就沒在跑。", ephemeral=True)

    if st["online"]:
        who = "、".join(st["list"]) or f"{st['online']} 人"
        await interaction.response.send_message(f"⚠️ 還有人在線上（{who}），仍會關閉並存檔…", ephemeral=True)
    else:
        await interaction.response.defer(ephemeral=True)

    log(f"stop requested by {interaction.user}")
    ok, out = await asyncio.to_thread(rcon, "save-all", "stop")
    msg = ("🛑 已送出關機指令，世界已存檔。\n"
           "存檔需要約一分鐘，這期間先不要 `/start`。"
           if ok else f"關機指令失敗：\n```{out[:500]}```")
    if interaction.response.is_done():
        await interaction.followup.send(msg, ephemeral=True)
    else:
        await interaction.response.send_message(msg, ephemeral=True)


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
    await interaction.response.send_message(
        f"**Java 版**（需要 26.2）\n`{CFG['javaAddress']}`\n\n"
        f"**基岩版**\n`{CFG['bedrockAddress']}`　連接埠 `{CFG['bedrockPort']}`\n\n"
        f"**世界地圖**\n{CFG['mapUrl']}"
        , ephemeral=True
    )


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
