# Minecraft Server Management System

[繁體中文](README.md) · **English**

Run a Paper server on your own Windows PC and let it look after itself: it comes back after a crash, backs itself up every day and checks the backup, and never stops or restarts without giving players a 5-minute warning in game. Day to day you manage it from a browser, from Discord or from an in-game menu, without going back to the machine.

> The tools' user interface is in Traditional Chinese. This document, the code and the commit history are in English.

[![Download](https://img.shields.io/badge/Download-MinecraftToolkitSetup.exe-2ea44f?style=for-the-badge)](../../releases/latest)

---

## Documentation

| Document | Contents |
|---|---|
| [Install guide (playit tunnel)](docs/INSTALL.en.md) | **Start here.** Full setup from nothing, no public IP required |
| [Install guide (router port forwarding)](docs/INSTALL-port-forwarding.en.md) | For a public IP and a direct connection |
| [Bundled plugins](bundled/README.en.md) | PanelKey and RyanDrawers: commands, settings, build steps |

Further down this page: [playit setup](#exposing-the-server-playit), [remote console](#managing-from-outside-cloudflare-tunnel), [security](#security), [scheduled tasks](#scheduled-tasks), [things that cost me time](#things-that-cost-me-time).

---

## What it is for

| What you want | How it happens |
|---|---|
| Friends can connect from outside | A playit tunnel, no router changes |
| Bedrock players can join too | Geyser and Floodgate; they need no Java account |
| Check on the server from the sofa | The LAN web console, on any phone |
| Manage it while you are out | The Discord bot, or the web console's login entrance behind a Cloudflare tunnel |
| Manage it from inside the game | PanelKey's `/menu` admin panel |
| Stop or restart without surprising anyone | Every console goes through one countdown script: 5 minutes of warnings, and it can be called off |
| Recover from a crash | A watchdog checks every five minutes and restarts it |
| Recover from a broken world | Daily backups of the world and the configuration, every chunk read back, a copy on a second disk |
| Find out what happened | SimplyFlashback records every online player; replays are kept 36 hours |
| See what the world looks like | A BlueMap 3D web map, published to Cloudflare Pages |

---

## Quick start

Download `MinecraftToolkitSetup.exe` from [Releases](../../releases/latest) and run it.

It will, and each step can be unchecked:

1. Check your Java version, Controlled Folder Access, and whether it has administrator rights
2. Download the Paper build you pick
3. Download plugins (Geyser, Floodgate, BlueMap, DeluxeMenus, PlaceholderAPI, LuckPerms, WorldEdit, WorldGuard, DiscordSRV)
4. Install the bundled PanelKey plugin and the admin menus
5. Turn RCON on and generate a password
6. Write `config.json`
7. Register the scheduled tasks (backup, watchdog, console)
8. Add the firewall rule and desktop shortcuts

It needs administrator rights, for the firewall rule. Start the server afterwards, then open `http://localhost:8099`.

If you would rather do it by hand, there are two guides that start from nothing, each with a verification step at the end of every section. They differ only in how the outside world reaches you — **read one of them**:

| | For |
|---|---|
| [INSTALL.en.md](docs/INSTALL.en.md) | **Most people.** A playit tunnel: no public IP, no router changes, works behind carrier-grade NAT |
| [INSTALL-port-forwarding.en.md](docs/INSTALL-port-forwarding.en.md) | You have a public IP and want a direct connection. You configure the router yourself, and your home IP is exposed |

---

## What is in it

### Managing the server

| Component | Location | What it does |
|---|---|---|
| **Web console** | `scripts/web-console.py` | Status tiles, start / countdown stop / restart / cancel, backups, RCON, log, game rules, heap size, and a panel per plugin (`plugin_panels.py`). LAN directly; from outside through a separate login entrance |
| **Desktop console** | `scripts/console-gui.py` | A tkinter window; same job as the web console |
| **Discord bot** | `scripts/discord-control.py` | `/status` `/start` `/stop` `/restart` `/cancel` `/rcon` `/render` `/ip` `/inv` (read-only look at a player's inventory) `/console-password`. Posts when the server or a tunnel changes state |
| **PanelKey plugin** | `bundled/panelkey-src/` | In-game admin panel, player menu, `/tpamenu`, portable workstations; turns `/stop` and `/restart` typed in game into the 5-minute countdown. See [bundled/README.en.md](bundled/README.en.md) |
| **Menus** | `bundled/deluxemenus/` | DeluxeMenus menus: admin panel, stop confirmation, toolbox, workstations, player menu |

### Stopping and starting

| Component | Location | What it does |
|---|---|---|
| **Countdown stop / restart** | `scripts/restart-sequence.py` | Shared by every console: announces at 5, 3 and 1 minutes, counts down the last 30 seconds, can be cancelled |
| **Start the server** | `scripts/start-server.py` | Desktop shortcut. No console window, so nobody kills the server by closing it |
| **Safe restart / safe shutdown** | `scripts/safe-power.py` | Desktop shortcuts. Count the server down, wait for java to finish saving, then restart or shut down Windows |
| **Swap a plugin** | `scripts/swap-plugin.py` | For a jar the running server keeps locked: countdown stop → swap → start. `--wait-empty` waits until nobody is online |
| **Watchdog** | `windows/watchdog.ps1` | Checks the server and tunnels every five minutes and restarts what died |
| **Lock after auto sign-in** | `windows/lock-after-autologon.ps1` | With Windows signing in by itself, locks the screen straight away; the server keeps running behind it |

### Backups and records

| Component | Location | What it does |
|---|---|---|
| **World backup** | `windows/backup-world.ps1` | Pause auto-save → flush → copy → compress → rotate |
| **Configuration backup** | `scripts/backup-config.py` | Whitelist, ops, plugin data, plugin jars, the toolkit itself, tunnel credentials. LuckPerms and SQLite are exported live, never copied half-written. **The zip holds secrets; keep it private** |
| **Backup check** | `scripts/verify-backup.py` | Reads every chunk's NBT straight from the zip and compares region counts per dimension |
| **Off-disk copy** | `windows/mirror-backup.ps1` | Copies backups that passed the check to another physical disk |
| **Recording** | `scripts/flashback-record.py` | Every minute, starts a SimplyFlashback recording for anyone online without one, and copies finished replays where the Flashback mod can open them |
| **Recording cleanup** | `windows/flashback-cleanup.ps1` | Removes replays older than the retention window |

### Everything else

| Component | Location | What it does |
|---|---|---|
| **Installer** | `installer/` | The eight steps under Quick start, with a GUI |
| **Health check** | `scripts/check-server.py` | Local service → DNS → tunnels → outside view → web map, each path checked the way players actually connect |
| **Map publishing** | `windows/sync-map.ps1` | Pushes BlueMap's static output to Cloudflare Pages |
| **RyanDrawers plugin** | `bundled/drawers-src/` | Storage Drawers-style drawers built on barrels, no client mod needed. Comes with a self-test plugin. Not installed by the installer; build it yourself |
| **Schematic converter** | `scripts/litematic2structure.py` | `.litematic` → structure-block `.nbt`, container contents preserved |

Everything except the Discord bot uses only the Python standard library.

---

## Requirements

| | |
|---|---|
| OS | Windows 10 or 11 |
| Java | 25 or newer |
| Paper | 26.x (the plugins are built against `api-version: 1.21`) |
| Python | 3.10 or newer — only for a manual install; the installer bundles its own |

---

## Configuration

One `config.json` configures every tool:

```bash
copy config.example.json config.json
```

The installer does this for you; afterwards you only fill in the domain, Discord and Cloudflare fields. Every section of `config.example.json` is commented; leave out what you do not use (off-disk copies, recording, the remote console).

Secrets are **not written into the config**. It points at files kept outside the repository:

```json
"discord": { "tokenFile": "C:\\Users\\you\\.secrets\\discord-bot-token.txt" }
```

`config.json` itself is in `.gitignore` too, since it carries your addresses and IDs.

---

## Exposing the server (playit)

**The installer does not do this step**, because it needs an account of your own. It is also the step that decides whether anyone can connect, so it is here rather than buried in the guide.

A home connection usually has no static IP and cannot open ports — consumer broadband is often behind carrier-grade NAT. playit gets around that with a tunnel opened from the inside out. It is free and touches nothing on your router.

### 1. Install

Sign up at <https://playit.gg> and install the Windows agent. It runs as a service called `playitd` and starts with the machine. The first run gives you a URL to claim it against your account.

### 2. Create the tunnels

Two of them, and **the protocol matters**:

| Type | Protocol | Points at |
|---|---|---|
| Minecraft Java | **TCP** | `127.0.0.1:25565` |
| Minecraft Bedrock | **UDP** | `127.0.0.1:19132` |

You get a public address like `something.tun.ply.gg:12345`. Skip the second one if nobody plays on Bedrock.

### 3. Put it in config.json

```json
"java":    { "host": "something.tun.ply.gg", "port": 25565 },
"bedrock": { "host": "something.tun.ply.gg", "tunnelPort": 12345 },
"tunnel":  { "java": "playit", "bedrock": "playit", "web": "pages" }
```

`tunnelPort` is the **public UDP port playit assigned**, which is usually not 19132 — that is the number Bedrock players type in. `tunnel` tells the watchdog and the health check which kind of tunnel each path uses (Java can also go through `cloudflared`, Bedrock through Geyser's `warden`).

### 4. Point your own domain at it (optional)

With Cloudflare:

| Type | Name | Content | Proxy |
|---|---|---|---|
| A | `mc` | The IP playit gave you | **DNS only (grey cloud)** |
| SRV | `_minecraft._tcp.mc` | Priority 0, weight 0, port `<playit's port>`, target `mc.yourdomain` | — |
| A | `bedrock` | The IP playit gave you | **DNS only (grey cloud)** |

With the SRV record, Java players type `mc.yourdomain` and no port.

### Three things that will stop you

**The proxy must be off (grey cloud).** The orange cloud is an HTTP proxy and Minecraft's protocol does not survive it.

**Do not create an AAAA record.** playit advertises an IPv6 address but does not route IPv6 to the agent, and players get `Connection timed out: getsockopt`. Keep the whole DNS chain on IPv4.

**A dashboard reading "online" does not mean traffic arrives.** It only reflects whether the agent reached playit's service. What to trust instead: the agent log at `C:\ProgramData\playit_gg\logs\playitd.log`, and the outside-view layer of `python scripts/check-server.py`. When the dashboard looks fine and nobody can connect, **deleting the agent and the tunnel and creating them again** is often the only thing that works.

### Verify

```bash
python scripts/check-server.py
```

The outside-view layer passing means it is genuinely reachable. Then have a friend actually try — passing an external check is not the same as a player getting in.

The full version, with troubleshooting, is in [docs/INSTALL.en.md, section 3](docs/INSTALL.en.md#3-exposing-the-server).

---

## Managing from outside (Cloudflare tunnel)

The LAN console (8099) only takes LAN connections. For use from outside, the console opens a second, **login-only entrance bound to `127.0.0.1`** (`webConsole.publicPort`, 8098 by default), and a Cloudflare Tunnel points at that:

1. Set a username and password at the machine (only a salted PBKDF2 hash is stored):
   ```bash
   python scripts/console_auth.py
   ```
   Away from the machine, Discord's `/console-password` sets them too.
2. Point a Cloudflare Tunnel public hostname at `http://127.0.0.1:8098`.
3. Put that address in `webConsole.publicUrl` in `config.json`.

After logging in, buttons that change anything still need the control token. Failed logins are throttled per address and in total.

---

## Security

The console can stop the server and run any console command, so the LAN entrance has three layers:

1. **A LAN address check** — `127/8`, `10/8`, `172.16/12`, `192.168/16`, `169.254/16`, `::1`, `fc00::/7`, `fe80::/10`, spelled out. Deliberately not `ipaddress.is_private`, which also counts documentation ranges such as `203.0.113.0/24` as private.
2. **A control token** for anything that changes state. Reading the dashboard needs nothing, so a phone can glance at it.
3. **A firewall rule** scoped to the local subnet.

The outside entrance adds a login on top. Every value a plugin panel puts into a command is checked against a fixed pattern first, since RCON runs everything with console rights. Every state-changing action is written to `web-console.log` with the source address.

> **Never point a tunnel at the LAN console's port (8099).** A tunnel agent connects from `127.0.0.1`, which passes the address check, so the tunnel would hand the admin page to the whole internet with only the token in the way. From outside, use the login entrance above and nothing else.

---

## Scheduled tasks

The scripts under `windows/` and `scripts/` are meant to be driven by Task Scheduler. The installer registers the backup, the watchdog and the console; add the rest if you want them:

| Task | Trigger | Command |
|---|---|---|
| World and configuration backup | Daily at 04:00 | `powershell -WindowStyle Hidden -File backup-world.ps1` (runs the configuration backup, the check and the off-disk copy after it) |
| Watchdog | Every 5 minutes | `powershell -WindowStyle Hidden -File watchdog.ps1` |
| Scheduled restart | 5 minutes before the restart time | `pythonw restart-sequence.py` |
| Discord bot | At logon | `pythonw discord-control.py` |
| LAN console | At logon | `pythonw web-console.py` |
| Recording | Every minute | `pythonw flashback-record.py` |
| Recording cleanup | Every hour | `powershell -WindowStyle Hidden -File flashback-cleanup.ps1` |
| Lock after auto sign-in | At logon | `powershell -WindowStyle Hidden -File lock-after-autologon.ps1` |

`pythonw` and `-WindowStyle Hidden` are not cosmetic: without them every trigger throws a console window on screen, and the watchdog fires every five minutes. For long-running tasks, set the execution time limit to unlimited — the default kills them after three days.

---

## Things that cost me time

Every one of these was debugged the hard way.

**Controlled Folder Access blocks writes silently.** Windows Defender protects `Documents`, `Pictures` and `Desktop` by default. Put a server or a tool's working directory under one of them and the symptom is "it dies or hangs with no error at all", pointing you in entirely the wrong direction. Keep things outside those folders; you do not have to turn the protection off.

**Restarting or shutting down Windows kills the server without saving.** Hence the "safe restart" and "safe shutdown" shortcuts: count the server down, wait for java to exit, then hand over to Windows.

**A server running in a console window dies with the window.** Close it and java is killed on the spot. The server now starts in the background (`start-server.py`) and only ever stops through the countdown script.

**Vanilla `/stop` and Spigot's `/restart` stop at once.** One admin typing them out of habit breaks the 5-minute warning players were promised. PanelKey turns both, when typed in game, into the countdown; the console and RCON keep the immediate stop for emergencies.

**Paper's RCON only returns what a command printed while it ran.** LuckPerms, WorldGuard, spark and Floodgate all reply asynchronously, so their answers never come back over RCON. The console's plugin panels send the command and then read the files those plugins write: a LuckPerms export, `regions.yml`, spark's `activity.json`, `whitelist.json`.

**A background process with no console opens a window for every console child.** `pythonw.exe` has no console of its own, so every console program it spawns gets a fresh window. Pass `creationflags=CREATE_NO_WINDOW` on every `subprocess` call.

**`Start-Process -ArgumentList` does not quote list items containing spaces.** `'/c','start','MC Server','/min',$bat` reaches cmd as `start MC Server /min ...` — `start` takes `MC` as the window title and tries to run `Server`, the batch file is never launched, and nothing is reported. Write it as `'"MC Server"'`.

**A `.ps1` containing Chinese must be saved as UTF-8 with BOM.** Windows PowerShell 5.1 reads a BOM-less file in the system ANSI codepage, where the second byte of certain characters swallows the following brace. It then reports `MissingEndCurlyBrace` against a line that is perfectly correct.

**A `.bat` must be pure ASCII with CRLF endings.** cmd.exe reads batch files in the OEM codepage; UTF-8 comments get shredded and the fragments are executed as commands. LF-only endings break multi-line `if (...)` blocks.

**Asking for DPI awareness without scaling is worse than not asking.** Windows stops magnifying the window, so unless the program handles fonts and sizes itself everything comes out about a third of its intended size — and resizing the window does not help, because the fonts are the problem. `SetProcessDpiAwareness` must also be called *before* the window exists; after that it does nothing.

**The Flashback mod only lists `.zip` files.** SimplyFlashback's `.flashback` is the same zip under another name; renaming the copy is enough.

**The server caches structure templates in memory.** Change the `.nbt` on disk and the same ID keeps serving the old one until you rename it or restart.

---

## Schematic converter

```bash
python scripts/litematic2structure.py schematic.litematic output-dir --prefix name
```

Litematica places blocks one at a time in no dependency order, so a rail goes down before the block beneath it and drops. Worse, placement driven through WorldEdit `//set` **does not write container contents** — the filter hoppers of an item sorter come out empty, the machine does nothing, and nothing is reported.

A structure block writes its whole volume at once without neighbour updates, and it carries container contents. The converter:

- Preserves the original NBT tag types (an item stack's `Slot` is a byte; written back as an int the container reads as empty)
- Preserves entities and block entities
- Writes air as well — a structure only places the blocks it lists, so dropping air leaves the machine entombed in the terrain it was placed into
- Splits anything over 48×48×48 and prints the offset each tile goes at

Output belongs in `<world>/generated/minecraft/structure/` — **singular** `structure`.

---

## Building the installer yourself

```bash
pip install pyinstaller
python installer/build_exe.py
```

Produces `dist/MinecraftToolkitSetup.exe`, a single self-contained file stamped with the commit it was built from.

---

## Inspiration

The installer's shape came from [tntapple219/MinecraftServerManager](https://github.com/tntapple219/MinecraftServerManager) (MIT) — one PyInstaller-built graphical program that runs the whole setup.

---

## Licence

MIT
