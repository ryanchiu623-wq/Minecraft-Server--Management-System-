# Full install guide

[繁體中文](INSTALL.md) · **English**

From a Windows machine with nothing on it, to a server your friends can reach, that backs itself up and gets itself back up after a crash.

**This guide exposes the server through a playit tunnel**, which needs no public IP and no router changes. If you have a public IP and want a direct connection with lower latency, read [INSTALL-port-forwarding.en.md](INSTALL-port-forwarding.en.md) instead. You only need one of the two.

Parts 1, 2 and 7 are required; skip the rest as you like. Every part ends with a verification step — **check as you go, rather than installing everything and then hunting for which piece broke**.

| Part | Contents | Required |
|---|---|---|
| [0](#0-requirements) | Requirements | yes |
| [1](#1-get-the-server-running) | Paper server + RCON | yes |
| [2](#2-install-the-toolkit) | Install the toolkit | yes |
| [3](#3-exposing-the-server) | Exposing the server (playit + domain) | optional |
| [4](#4-bedrock-crossplay) | Bedrock crossplay (Geyser) | optional |
| [5](#5-web-map) | Web map (BlueMap) | optional |
| [6](#6-discord-control) | Discord control | optional |
| [7](#7-lan-console) | LAN console | yes |
| [8](#8-automation) | Automation | recommended |
| [9](#9-final-check) | Final check | yes |

---

## 0. Requirements

| | Version | Notes |
|---|---|---|
| Windows | 10 / 11 | |
| Java | 21 or newer | Paper 1.21+ requires it. Developed against 26.0.1 |
| Python | 3.10 or newer | Developed against 3.14 |
| Memory | 8 GB or more suggested | 4 GB for the server itself is plenty |

Tick **"Add to PATH"** when installing Java and Python. Open a new terminal afterwards and confirm:

```bash
java -version
python --version
```

### Deal with Controlled Folder Access first

Windows Defender's Controlled Folder Access protects `Documents`, `Pictures` and `Desktop` by default, and **blocked writes fail silently** — the server dies for no visible reason, tools hang forever, and nothing tells you why.

```powershell
(Get-MpPreference).EnableControlledFolderAccess
```

`1` means it is on. **Do not turn it off.** Install outside those folders instead:

```
C:\mc-paper      the server
C:\mc-backup     backups
C:\mc-toolkit    this toolkit
```

The rest of this guide uses those paths.

---

## 1. Get the server running

### 1.1 Download Paper

Grab the latest build from <https://papermc.io/downloads/paper> and save it as `C:\mc-paper\paper.jar`.

### 1.2 First start

```bash
cd C:\mc-paper
java -jar paper.jar nogui
```

It writes `eula.txt` and exits. Edit it:

```properties
eula=true
```

Run it again, wait for the world to generate, then type `stop` in the console.

### 1.3 Turn RCON on

RCON is the only channel the toolkit has to the server. **Nothing below works without it.** Edit `C:\mc-paper\server.properties`:

```properties
enable-rcon=true
rcon.port=25575
rcon.password=pick a long password of your own
```

Any long string will do — you do not need to remember it, the toolkit reads it from this file.

Restart the server.

### Verify

In another terminal:

```bash
cd C:\mc-toolkit
python scripts\rcon.py "list"
```

`There are 0 of a max of 20 players online:` means it works.

If it fails, check in this order: is the server running, is `enable-rcon` actually `true`, does the password have stray whitespace.

---

## 2. Install the toolkit

```bash
git clone https://github.com/ryanchiu623-wq/Minecraft-Server--Management-System-.git C:\mc-toolkit
cd C:\mc-toolkit
copy config.example.json config.json
```

Edit `config.json`. **Four fields are enough for now**; leave the rest until later:

```json
{
  "serverDir": "C:\\mc-paper",
  "backupDir": "C:\\mc-backup",
  "startBat": "C:\\mc-paper\\start.bat",
  "keepBackups": 7
}
```

Paths need doubled backslashes — that is JSON, not Windows.

Copy the launcher into the server directory:

```bash
copy windows\start.bat C:\mc-paper\
```

### Verify

```bash
python scripts\rcon.py "list"
```

Same result as 1.3. This time it found the server through `config.json`.

---

## 3. Exposing the server

A home connection is usually behind NAT — often the ISP's, not just your own — with no static IP and no way to forward a port. [playit.gg](https://playit.gg) tunnels through it. Free, and it touches nothing on your router.

### 3.1 Install playit

Sign up at <https://playit.gg> and install the Windows build. It registers a service called `playitd` that starts with the machine. The first run gives you a URL to claim the agent.

### 3.2 Create the tunnels

In the playit dashboard:

| Type | Protocol | Points at |
|---|---|---|
| Minecraft Java | TCP | `127.0.0.1:25565` |
| Minecraft Bedrock | UDP | `127.0.0.1:19132` |

You get a public address like `something.tun.ply.gg:12345`.

> **A dashboard reading "online" does not mean traffic arrives.** It only reflects whether the agent reached playit's service; it says nothing about whether packets get to your machine. Trust the agent log (`C:\ProgramData\playit_gg\logs\playitd.log`) and the outside check in part 9 instead.
>
> When the dashboard looks fine and nobody can connect, **deleting the agent and the tunnel and creating them again** is often the only thing that works.

### 3.3 Point your own domain at it (optional)

With Cloudflare:

| Type | Name | Content | Proxy |
|---|---|---|---|
| A | `mc` | The IP playit gave you | **DNS only (grey cloud)** |
| SRV | `_minecraft._tcp.mc` | Priority 0, weight 0, port `<playit's port>`, target `mc.yourdomain` | — |
| A | `bedrock` | The IP playit gave you | **DNS only (grey cloud)** |

With the SRV record, Java players type `mc.yourdomain` with no port.

**Three traps:**

- **The proxy must be off (grey cloud).** The orange cloud is an HTTP proxy; Minecraft's protocol does not survive it.
- **Do not create an AAAA record.** playit advertises an IPv6 address but does not route IPv6 to the agent, and players get `Connection timed out: getsockopt`. Keep the whole chain on IPv4.
- **Do not paste into Cloudflare's SRV target field.** Copying from elsewhere brings invisible characters with it and you get `Data field "target" contains non-printable characters`. Type it.

### Verify

```bash
python scripts\check-server.py
```

The DNS layer should show your domain resolving to playit's IP.

---

## 4. Bedrock crossplay

Lets friends on phones, tablets and consoles join your Java server. **They do not need a Java account.**

> Using the installer? Skip this — it downloads Geyser and Floodgate and sets `auth-type` to `floodgate` when Geyser's config already exists.

### 4.1 Install the plugins

Both jars go in `C:\mc-paper\plugins\`:

- **Geyser** (Spigot build) — <https://geysermc.org/download>
- **Floodgate** (Spigot build) — same page

Geyser translates the protocol; **Floodgate is the part that lets people in without a Java account**. With Geyser alone, Bedrock players still need one.

Restart the server so it generates the config files.

### 4.2 Configure

`plugins\Geyser-Spigot\config.yml`:

```yaml
bedrock:
  port: 19132
remote:
  auth-type: floodgate
```

`auth-type` must be `floodgate`.

Restart again.

### 4.3 Update config.json

```json
"bedrock": {
  "host": "bedrock.yourdomain",
  "tunnelPort": your playit UDP port,
  "localPort": 19132
}
```

`tunnelPort` is the public port playit assigned, and it is **usually not 19132**. That is the number Bedrock players type in the game.

### Verify

```bash
python scripts\check-server.py
```

Both Bedrock layers should pass. Or just ask a friend to try.

---

## 5. Web map

BlueMap renders a 3D web map; pushing it to Cloudflare Pages as static files means **no third tunnel**, and nobody reaches your home IP by opening the map.

### 5.1 Install BlueMap

Drop `bluemap-x.y-paper.jar` into `plugins\` and restart. It starts rendering, which takes a while on a large world.

### 5.2 Set up Cloudflare Pages

```bash
npm install -g wrangler
wrangler login
wrangler pages project create your-project-name
```

Save the Cloudflare API token to a plain text file **outside the repository**, for example `C:\Users\you\.secrets\cloudflare-token.txt`.

### 5.3 Update config.json

```json
"mapUrl": "https://your-project-name.pages.dev",
"cloudflare": {
  "projectName": "your-project-name",
  "accountId": "your account ID",
  "tokenFile": "C:\\Users\\you\\.secrets\\cloudflare-token.txt",
  "webDir": "C:\\mc-paper\\bluemap\\web"
}
```

### Verify

```bash
powershell -ExecutionPolicy Bypass -File windows\sync-map.ps1
```

Open `mapUrl` afterwards and the map should be there.

> **Leave compression off on Cloudflare Pages.** BlueMap's tiles are already compressed; compressing them again leaves the browser unable to decode them and the map comes up blank.

---

## 6. Discord control

Start and stop the server, check status and run commands from your phone.

### 6.1 Create the bot

1. Create an Application at <https://discord.com/developers/applications>
2. **Bot** in the sidebar → Add Bot → Reset Token → **save the token to a plain text file outside the repository**
3. On the same page, enable **Message Content Intent**
4. **OAuth2 → URL Generator** → tick `bot` and `applications.commands` → use the generated URL to invite it

> **Never paste the token into a chat, a screenshot or a command line.** Anyone who has it can drive your bot. If it does leak, hit Reset Token on the developer page.

### 6.2 Get the IDs

Discord settings → Advanced → enable **Developer Mode**. After that, right-clicking any user or channel offers "Copy ID".

### 6.3 Update config.json

```json
"discord": {
  "tokenFile": "C:\\Users\\you\\.secrets\\discord-bot-token.txt",
  "authorizedUserIds": ["your user ID"],
  "rconUserIds": ["your user ID"],
  "logChannelId": "channel ID for event notifications"
}
```

`rconUserIds` is a separate list because RCON is full control of the server. Left empty, it falls back to `authorizedUserIds`.

### 6.4 Install and start

```bash
pip install discord.py
python scripts\discord-control.py
```

### Verify

Type `/status` in Discord. It should reply with the server's state.

If the commands do not appear, give Discord a minute to sync, or invite the bot again.

---

## 7. LAN console

A browser admin page, reachable from your phone, a tablet, or another PC.

```bash
python scripts\web-console.py
```

It prints its address and a control token on startup. The token lives in `web-console.config.json`; delete that field and restart to get a new one.

### 7.1 Firewall rule

Other devices on the LAN need one rule. **Open PowerShell as administrator:**

```powershell
New-NetFirewallRule -DisplayName 'MC Web Console (LAN)' -Direction Inbound `
  -Protocol TCP -LocalPort 8099 -RemoteAddress LocalSubnet -Action Allow `
  -Profile Private,Domain
```

The rule covers the Private and Domain profiles, so **your network must be set to "private"**:

```powershell
Get-NetConnectionProfile
```

If it says `Public` the rule does not apply — change that network to private in Windows settings.

### 7.2 Security

This page can stop the server and run any console command. Three layers protect it: the LAN address check, the control token, and the firewall rule. Every state-changing action is written to `web-console.log` with the source address.

> **Never point playit — or any other tunnel — at port 8099.** The agent connects from `127.0.0.1`, which passes the address check, so the tunnel would put the admin page on the public internet with only the token in the way.

### Verify

From a phone on the same Wi-Fi, open `http://<your LAN IP>:8099`.

If it does not load: check the firewall rule exists, that the network is private, and that your router does not have AP isolation switched on.

---

## 8. Automation

Hand the backups, the watchdog, the restarts and the bot to Task Scheduler.

| Task | Trigger | Command |
|---|---|---|
| World backup | Daily at 04:00 | `powershell -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File C:\mc-toolkit\windows\backup-world.ps1` |
| Watchdog | Every 5 minutes | `powershell -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File C:\mc-toolkit\windows\watchdog.ps1` |
| Scheduled restart | Daily, **5 minutes before** the restart time | `pythonw C:\mc-toolkit\scripts\restart-sequence.py` |
| Discord bot | At logon | `pythonw C:\mc-toolkit\scripts\discord-control.py` |
| LAN console | At logon | `pythonw C:\mc-toolkit\scripts\web-console.py` |

**Set every task's "Start in" to `C:\mc-toolkit`**, or the scripts will not find `config.json`.

### Why pythonw and -WindowStyle Hidden matter

Without them, **every trigger throws a console window onto the screen**. The watchdog fires every five minutes, and being interrupted mid-game gets old fast.

For the same reason, set the execution time limit on long-running tasks (the bot, the console) to unlimited — the default kills them after three days.

### Verify

Hit "Run" on each task in Task Scheduler, then:

- Backup → a zip appears in `C:\mc-backup`
- Watchdog → a new line in `watchdog.log`
- Bot / console → the service comes up

---

## 9. Final check

```bash
python scripts\check-server.py
```

Six layers, ordered so that **a failure below is usually caused by one above — start at the topmost failure**:

```
local        is the server process alive
DNS          does the domain point where it should
tunnel       can this machine reach the public address
outside      can a third party see it
web map      does the map site respond
```

All green means you are done.

Then have a friend actually connect — **passing an external check is not the same as a player getting in**.

---

## Troubleshooting

Each of these was debugged the hard way, not read somewhere.

**Something dies or hangs with no error at all**
Check Controlled Folder Access first (part 0). It blocks writes silently, and the symptoms point somewhere else entirely.

**A `.bat` spits out garbage commands halfway through**
Batch files must be **pure ASCII with CRLF endings**. cmd.exe reads them in the OEM codepage; UTF-8 comments get shredded and the fragments run as commands. LF-only endings break multi-line `if (...)` blocks.

**A `.ps1` reports `MissingEndCurlyBrace` on a line that is fine**
A PowerShell script containing non-ASCII text must be saved as **UTF-8 with BOM**. Without one, PowerShell 5.1 reads it in the system ANSI codepage and the second byte of certain characters swallows the following brace. Check it with this rather than by eye:

```powershell
$e=$null; [void][System.Management.Automation.Language.Parser]::ParseFile('path',[ref]$null,[ref]$e); $e
```

**A scheduled task flashes a window every time it runs**
Use `pythonw` instead of `python`, and `-WindowStyle Hidden` for PowerShell. In your own scripts, **a background process with no console opens a fresh window for every console child** — pass `creationflags=CREATE_NO_WINDOW` on every `subprocess` call.

**PowerShell launches a .bat and nothing happens**
`Start-Process -ArgumentList` does not quote list items containing spaces. `'/c','start','MC Server','/min',$bat` reaches cmd as `start MC Server /min ...` — `start` takes `MC` as the window title and tries to run `Server`. The batch file is never launched, and nothing is reported. Write it as `'"MC Server"'`.

**Bedrock players cannot connect but Java players can**
Bedrock is UDP and needs its own tunnel. The public port is usually not 19132 — players have to type the one playit assigned.

**Players get `Connection timed out: getsockopt`**
Usually IPv6. playit advertises AAAA but does not route IPv6 to the agent. Delete every AAAA record.

**RCON commands time out when nobody is online**
Paper pauses an idle server (`Server empty for 60 seconds, pausing` in the log). Large batches of RCON commands tend to drop the connection in that state; send them in smaller pieces.

**The map page is blank**
Turn compression off on Cloudflare Pages. BlueMap's tiles are already compressed and the browser cannot decode them twice.
