# Minecraft Server Management System

[繁體中文](README.md) · **English**

Run a Minecraft server on your own Windows PC, and let it look after itself.

One installer sets up the server, its plugins and the automation around it. After that you manage it from a browser or from Discord, without going back to the machine.

> The tools' user interface is in Traditional Chinese. This document, the code and the commit history are in English.

[![Download](https://img.shields.io/badge/Download-MinecraftToolkitSetup.exe-2ea44f?style=for-the-badge)](../../releases/latest)

---

## Documentation

| Document | Contents |
|---|---|
| [Install guide (playit tunnel)](docs/INSTALL.en.md) | **Start here.** Full setup from nothing, no public IP required |
| [Install guide (router port forwarding)](docs/INSTALL-port-forwarding.en.md) | For a public IP and a direct connection |
| [PanelKey plugin](bundled/README.en.md) | The bundled in-game admin panel, with source and build steps |

Further down this page: [playit setup](#exposing-the-server-playit), [security](#security), [scheduled tasks](#scheduled-tasks), [things that cost me time](#things-that-cost-me-time).

---

## What it is for

A home connection has no static IP and no way to open a port, so nobody can reach you. A server that dies at 3am stays dead until someone notices. Shutting it down means walking back to the machine. And friends on Bedrock — phones, tablets, consoles — cannot join a Java server at all.

| What you want | How it happens |
|---|---|
| Friends can connect from outside | A playit tunnel, no router changes |
| Bedrock players can join too | Geyser and Floodgate; they need no Java account |
| Check on the server from the sofa | The LAN web console |
| Start or stop it while you are out | The Discord bot |
| Recover from a crash | A watchdog checks every five minutes and restarts it |
| Recover from a broken world | Daily backups, seven kept |
| See what the world looks like | A BlueMap 3D web map |

---

## Quick start

Download `MinecraftToolkitSetup.exe` from [Releases](../../releases/latest) and run it.

It will, and each step can be unchecked:

1. Check your Java version, Controlled Folder Access, and whether it has administrator rights
2. Download the Paper build you pick
3. Download plugins (Geyser, Floodgate, BlueMap, DeluxeMenus, PlaceholderAPI, LuckPerms, WorldEdit, WorldGuard, DiscordSRV)
4. Install the bundled PanelKey plugin and the four admin menus
5. Turn RCON on and generate a password
6. Write `config.json`
7. Register the scheduled tasks (backup, watchdog, console)
8. Add the firewall rule and desktop shortcuts

It needs administrator rights, for the firewall rule. Start the server afterwards, then open `http://localhost:8099`.

If you would rather do it by hand, there are two guides that start from nothing, each with a verification step at the end of every section.

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
"bedrock": { "host": "something.tun.ply.gg", "tunnelPort": 12345 }
```

`tunnelPort` is the **public UDP port playit assigned**, which is usually not 19132 — that is the number Bedrock players type in.

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

## What is in it

| Component | Location | What it does |
|---|---|---|
| **Installer** | `installer/` | The eight steps above, with a GUI |
| **LAN console** | `scripts/web-console.py` | Browser admin page: status tiles, start/stop, backups, RCON, log, game rules, heap size. LAN connections only |
| **Health check** | `scripts/check-server.py` | Six layers: local service → DNS → tunnel → outside view → web map |
| **Discord bot** | `scripts/discord-control.py` | `/status` `/start` `/stop` `/rcon` `/ip` `/render` |
| **Desktop console** | `scripts/console-gui.py` | A tkinter window; same job as the web console |
| **Scheduled restart** | `scripts/restart-sequence.py` | Announces at 5, 3 and 1 minutes, counts down the last 30 seconds |
| **Watchdog** | `windows/watchdog.ps1` | Checks every five minutes and restarts a server that died |
| **Backup** | `windows/backup-world.ps1` | Pause auto-save → flush → copy → compress → rotate |
| **Map publishing** | `windows/sync-map.ps1` | Pushes BlueMap's static output to Cloudflare Pages |
| **PanelKey plugin** | `bundled/` | In-game admin panel: `/menu`, `/spawn`, portable workstations, give-to-target. Source included |
| **Admin menus** | `bundled/deluxemenus/` | Four DeluxeMenus menus, registered during install |
| **Schematic converter** | `scripts/litematic2structure.py` | `.litematic` → structure-block `.nbt`, container contents preserved |

Everything except the Discord bot uses only the Python standard library.

---

## Requirements

| | |
|---|---|
| OS | Windows 10 or 11 |
| Java | 21 or newer |
| Python | 3.10 or newer — only for a manual install; the installer bundles its own |

---

## Configuration

One `config.json` configures every tool:

```bash
copy config.example.json config.json
```

The installer does this for you; afterwards you only fill in the domain, Discord and Cloudflare fields.

Secrets are **not written into the config**. It points at files kept outside the repository:

```json
"discord": { "tokenFile": "C:\\Users\\you\\.secrets\\discord-bot-token.txt" }
```

`config.json` itself is in `.gitignore` too, since it carries your addresses and IDs.

---

## Security

The console can stop the server and run any console command, so there are three layers:

1. **A LAN address check** — `127/8`, `10/8`, `172.16/12`, `192.168/16`, `169.254/16`, `::1`, `fc00::/7`, `fe80::/10`, spelled out. Deliberately not `ipaddress.is_private`, which also counts documentation ranges such as `203.0.113.0/24` as private.
2. **A control token** for anything that changes state. Reading the dashboard needs nothing, so a phone can glance at it.
3. **A firewall rule** scoped to the local subnet.

Every state-changing action is written to `web-console.log` with the source address.

> **Never point playit — or any other tunnel — at the console's port.** The agent connects from `127.0.0.1`, which passes the address check, so the tunnel would hand the admin page to the whole internet with only the token in the way.

---

## Scheduled tasks

The scripts under `windows/` are meant to be driven by Task Scheduler. The installer registers the backup, the watchdog and the console; add the rest if you want them:

| Task | Trigger | Command |
|---|---|---|
| World backup | Daily at 04:00 | `powershell -WindowStyle Hidden -File backup-world.ps1` |
| Watchdog | Every 5 minutes | `powershell -WindowStyle Hidden -File watchdog.ps1` |
| Scheduled restart | 5 minutes before the restart time | `pythonw restart-sequence.py` |
| Discord bot | At logon | `pythonw discord-control.py` |
| LAN console | At logon | `pythonw web-console.py` |

`pythonw` and `-WindowStyle Hidden` are not cosmetic: without them every trigger throws a console window on screen, and the watchdog fires every five minutes. For long-running tasks, set the execution time limit to unlimited — the default kills them after three days.

---

## Things that cost me time

Every one of these was debugged the hard way.

**Controlled Folder Access blocks writes silently.** Windows Defender protects `Documents`, `Pictures` and `Desktop` by default. Put a server or a tool's working directory under one of them and the symptom is "it dies or hangs with no error at all", pointing you in entirely the wrong direction. Keep things outside those folders; you do not have to turn the protection off.

**A background process with no console opens a window for every console child.** `pythonw.exe` has no console of its own, so every console program it spawns gets a fresh window. Pass `creationflags=CREATE_NO_WINDOW` on every `subprocess` call.

**`Start-Process -ArgumentList` does not quote list items containing spaces.** `'/c','start','MC Server','/min',$bat` reaches cmd as `start MC Server /min ...` — `start` takes `MC` as the window title and tries to run `Server`, the batch file is never launched, and nothing is reported. Write it as `'"MC Server"'`.

**A `.ps1` containing Chinese must be saved as UTF-8 with BOM.** Windows PowerShell 5.1 reads a BOM-less file in the system ANSI codepage, where the second byte of certain characters swallows the following brace. It then reports `MissingEndCurlyBrace` against a line that is perfectly correct.

**A `.bat` must be pure ASCII with CRLF endings.** cmd.exe reads batch files in the OEM codepage; UTF-8 comments get shredded and the fragments are executed as commands. LF-only endings break multi-line `if (...)` blocks.

**Asking for DPI awareness without scaling is worse than not asking.** Windows stops magnifying the window, so unless the program handles fonts and sizes itself everything comes out about a third of its intended size — and resizing the window does not help, because the fonts are the problem. `SetProcessDpiAwareness` must also be called *before* the window exists; after that it does nothing.

**A playit dashboard reading "online" does not mean traffic arrives.** See the playit section above.

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
