# Full install guide (router port forwarding)

[繁體中文](INSTALL-port-forwarding.md) · **English**

The same setup as [INSTALL.en.md](INSTALL.en.md), differing only in **how the outside world reaches you**: your own router forwards the ports, with no third party in between.

**You only need one of the two guides.** Pick with this:

| | Port forwarding (this guide) | playit tunnel ([INSTALL.en.md](INSTALL.en.md)) |
|---|---|---|
| Public IP required | **yes** | no |
| Router changes required | yes | no |
| Latency | direct, lowest | one hop more |
| Your home IP exposed | **yes** | no |
| DDoS protection | none | absorbed by the tunnel provider |
| Address players use | your domain or IP | the provider's address |
| Cost | free | free (paid tiers get a fixed address) |

**Consumer broadband is often behind carrier-grade NAT, where port forwarding cannot work** — in that case the playit guide is your only option. Section 3.0 shows how to tell. **Do that step before anything else.**

Parts 1, 2 and 7 are required; skip the rest as you like. Every part ends with a verification step — check as you go rather than installing everything and then hunting for what broke.

---

## 0. Requirements

| | Version | Notes |
|---|---|---|
| Windows | 10 / 11 | |
| Java | 21 or newer | Paper 1.21+ requires it |
| Python | 3.10 or newer | Not needed if you use the installer |
| Network | **a public IP** | See section 3.0 |
| Router | one you can log into | An ISP-supplied box usually counts; the password is often on a sticker |

Tick **"Add to PATH"** when installing Java and Python.

### Deal with Controlled Folder Access first

Windows Defender's Controlled Folder Access protects `Documents`, `Pictures` and `Desktop` by default, and **blocked writes fail silently** — the server dies for no visible reason and nothing tells you why.

```powershell
(Get-MpPreference).EnableControlledFolderAccess
```

`1` means it is on. **Do not turn it off.** Install outside those folders:

```
C:\mc-paper      the server
C:\mc-backup     backups
C:\mc-toolkit    this toolkit
```

---

## 1. Get the server running

Identical to the playit guide.

### 1.1 Download Paper

Save the latest build from <https://papermc.io/downloads/paper> as `C:\mc-paper\paper.jar`.

### 1.2 First start

```bash
cd C:\mc-paper
java -jar paper.jar nogui
```

It writes `eula.txt` and exits. Change `eula=false` to `eula=true`, run it again, wait for the world to generate, then type `stop`.

### 1.3 Turn RCON on

RCON is the only channel the toolkit has to the server. **Nothing below works without it.** Edit `C:\mc-paper\server.properties`:

```properties
enable-rcon=true
rcon.port=25575
rcon.password=pick a long password of your own
server-port=25565
```

> **Never forward the RCON port (25575).** That is full console access behind a single password. Forward only 25565, the game port.

### Verify

```bash
cd C:\mc-toolkit
python scripts\rcon.py "list"
```

`There are 0 of a max of 20 players online:` means it works.

---

## 2. Install the toolkit

```bash
git clone https://github.com/ryanchiu623-wq/Minecraft-Server--Management-System-.git C:\mc-toolkit
cd C:\mc-toolkit
copy config.example.json config.json
```

Fill in four fields for now:

```json
{
  "serverDir": "C:\\mc-paper",
  "backupDir": "C:\\mc-backup",
  "startBat": "C:\\mc-paper\\start.bat",
  "keepBackups": 7
}
```

Paths need doubled backslashes — that is JSON, not Windows.

```bash
copy windows\start.bat C:\mc-paper\
```

> `start.bat` contains a section that starts playit. Without it installed those lines fail quietly and nothing else is affected; delete the `sc start playitd` line if it bothers you.

---

## 3. Exposing the server (port forwarding)

### 3.0 First, confirm you have a public IP

**This is the most important step in the guide.** Behind a carrier-grade NAT, forwarding a port **cannot** work — not because you configured it wrong, but because that public address is shared between hundreds of subscribers and your router has no say over which of them a port belongs to.

How to tell: **compare two addresses.**

**A. The WAN address on your router** — log into its admin page, find "WAN status", "Internet" or "Connection info", and note the address it reports.

**B. The address the world sees** — open <https://api.ipify.org>, or:

```powershell
(Invoke-WebRequest -Uri https://api.ipify.org -UseBasicParsing).Content
```

**Same** → you have a public IP; carry on.

**Different** → you are behind carrier-grade NAT and **forwarding will not help**. Use [INSTALL.en.md](INSTALL.en.md) and playit instead.

You can also settle it outright if the router's WAN address falls in one of these:

| Range | |
|---|---|
| `100.64.0.0/10` | CGNAT (RFC 6598), the common one |
| `10.0.0.0/8` | private |
| `172.16.0.0/12` | private |
| `192.168.0.0/16` | private |

> **Checking "what is my IP" on its own proves nothing.** Behind carrier-grade NAT those sites still answer with a public address — the carrier's, not yours. Only the comparison against the router's WAN address means anything.

> **Double NAT**: some setups have an ISP modem *and* your own router. Then both need forwarding, or the modem needs to be put in bridge mode. Make sure you are configuring the outermost device.

### 3.1 Give the server machine a fixed LAN address

Forwarding points at a **LAN address**. If that machine's address changes — and DHCP will change it — the forward starts pointing at somebody else after a reboot.

Find the current one:

```powershell
Get-NetIPConfiguration | Where-Object { $_.NetProfile.IPv4Connectivity -eq 'Internet' } |
  Select-Object InterfaceAlias, IPv4Address, IPv4DefaultGateway
```

Two ways to pin it; **the first is better**:

**A. A DHCP reservation on the router (recommended)** — look for "DHCP reservation", "static DHCP" or "address reservation" and bind this machine's MAC to a fixed address. Nothing changes on the machine, and it keeps working on other networks.

**B. A static address on the machine** — Windows Settings → Network → Edit IP assignment → Manual. You have to supply the address, mask, gateway and DNS yourself, and getting one wrong takes the machine off the network entirely.

### 3.2 Forward the ports

In the router's admin page, look for "port forwarding", "virtual server" or "NAT". The name varies; it is usually under Advanced.

Add two rules:

| Purpose | Protocol | External port | Internal address | Internal port |
|---|---|---|---|---|
| Minecraft Java | **TCP** | 25565 | your server's LAN address | 25565 |
| Minecraft Bedrock | **UDP** | 19132 | same | 19132 |

**The protocol must be right**: Java is TCP, Bedrock is UDP. If your router offers "both", that works too.

Skip the second rule if nobody plays on Bedrock.

> **Forward only those two ports.** Do not use DMZ to save time — that exposes every service on the machine. And do not forward RCON's 25575.

### 3.3 Windows Firewall

Forwarding only makes the router willing to send traffic; Windows still has to accept it. **Open PowerShell as administrator:**

```powershell
New-NetFirewallRule -DisplayName 'Minecraft Java' -Direction Inbound `
  -Protocol TCP -LocalPort 25565 -Action Allow -Profile Private,Domain

New-NetFirewallRule -DisplayName 'Minecraft Bedrock' -Direction Inbound `
  -Protocol UDP -LocalPort 19132 -Action Allow -Profile Private,Domain
```

These cover the Private and Domain profiles, so your network must be set to private:

```powershell
Get-NetConnectionProfile
```

If it says `Public`, the rules do not apply — change that network to private in Windows settings.

> You will find advice to add `-Profile Any`, or to include Public. **Do not** — that leaves these ports open on café Wi-Fi too.

### 3.4 Point your own domain at it

Without a domain, friends can connect to your public IP directly and you can skip this. But a home connection's IP usually changes — on reconnect, or when the ISP reassigns it — **so a domain is strongly recommended**: when the address changes you edit one record.

With Cloudflare:

| Type | Name | Content | Proxy |
|---|---|---|---|
| A | `mc` | your public IP | **DNS only (grey cloud)** |
| A | `bedrock` | your public IP | **DNS only (grey cloud)** |

**The proxy must be off (grey cloud).** The orange cloud is an HTTP proxy and Minecraft's protocol does not survive it.

Because the external port is the standard 25565, **no SRV record is needed** — players just type `mc.yourdomain`. (This is simpler than the playit setup, where the assigned port is not 25565 and SRV exists to hide it.)

**When the IP changes** — use dynamic DNS. Cloudflare has an API you can drive from a small script, or use a free service like No-IP or DuckDNS, which ship a Windows client that updates the record for you. To find out whether your address moves at all, check <https://api.ipify.org> again in a few days.

### Verify

**Test from outside first**, not from your own network — many routers do not support reaching your own public IP from inside (NAT hairpinning), and you will read that as a failure.

Use a phone on mobile data with Wi-Fi off, or a web tool:

- <https://mcsrvstat.us> with your domain or IP
- or any port checker, against TCP 25565

Then:

```bash
python scripts\check-server.py
```

The DNS layer should show your domain resolving to your public IP, and the outside-view layer should pass.

---

## 3.5 What port forwarding costs you that a tunnel does not

This section does not exist in the playit guide, because the tunnel provider absorbs these for you.

**Your home IP becomes public.** Anyone who connects, or who looks up your domain, can see it, along with a rough location and your ISP. If that bothers you, use the playit guide.

**You will be scanned, continuously.** This is measured, not theoretical: on the tunnel side of this setup, a single scanning bot accounted for **906 of 912 connections over 18 hours** — 99.3%. An exposed Minecraft port will be found. With forwarding, that traffic arrives on your own line.

**There is no DDoS protection.** A home connection has no buffer; being hit takes the whole line down, and everyone else in the house with it.

What to actually do:

- **Turn the whitelist on.** This is the effective one. Only listed players get in, and the scanners stop mattering.
  ```bash
  python scripts\rcon.py "whitelist on" "whitelist add friendname"
  ```
- **Keep Paper updated.** Server software vulnerabilities are real.
- **Leave `online-mode=true`** (the default). Set it false and anyone can impersonate any account.
- **Do not forward RCON**, as above.
- If you are being targeted specifically, routers usually offer IP blocking.

---

## 4. Bedrock crossplay

Lets friends on phones, tablets and consoles join. **They do not need a Java account.**

> Using the installer? Skip this section.

### 4.1 Install the plugins

Both jars go in `C:\mc-paper\plugins\`:

- **Geyser** (Spigot build) — <https://geysermc.org/download>
- **Floodgate** (Spigot build) — same page

Geyser translates the protocol; **Floodgate is the part that lets people in without a Java account**. With Geyser alone, Bedrock players still need one.

Restart the server to generate the config files.

### 4.2 Configure

`plugins\Geyser-Spigot\config.yml`:

```yaml
bedrock:
  port: 19132
remote:
  auth-type: floodgate
```

Restart again.

### 4.3 Update config.json

```json
"bedrock": {
  "host": "bedrock.yourdomain",
  "tunnelPort": 19132,
  "localPort": 19132
}
```

**This differs from the playit guide**: playit hands out an odd public port, but with forwarding the external port is just 19132, so both fields hold the same value. Bedrock players type 19132 as well.

### Verify

```bash
python scripts\check-server.py
```

Both Bedrock layers should pass.

---

## 5. Web map

Identical to the playit guide — follow [INSTALL.en.md section 5](INSTALL.en.md#5-web-map).

The point: BlueMap produces static files that go to Cloudflare Pages. **Do not forward another port for the map.** That is one more thing exposed, and the map page would hand your home IP to everyone who opens it. Static hosting has neither problem.

> Leave compression off on Cloudflare Pages. BlueMap's tiles are already compressed, and the browser cannot decode them twice — the map comes up blank.

---

## 6. Discord control

Identical to the playit guide — follow [INSTALL.en.md section 6](INSTALL.en.md#6-discord-control).

> **Never paste the bot token into a chat, a screenshot or a command line.** Anyone who has it can drive your bot. If it leaks, hit Reset Token on the developer page.

---

## 7. LAN console

```bash
python scripts\web-console.py
```

It prints its address and a control token on startup. The token lives in `web-console.config.json`.

Firewall rule (**needs administrator rights**):

```powershell
New-NetFirewallRule -DisplayName 'MC Web Console (LAN)' -Direction Inbound `
  -Protocol TCP -LocalPort 8099 -RemoteAddress LocalSubnet -Action Allow `
  -Profile Private,Domain
```

Note the `-RemoteAddress LocalSubnet` — unlike the game ports in 3.3, this one **only accepts the local network**.

> **Never forward port 8099.** This page can stop the server and run any console command. Its LAN address check rejects outside sources, but forwarding it is deliberately putting the admin interface on the public internet with only the token in the way. To manage the server while you are out, use the Discord bot.

---

## 8. Automation

Identical to the playit guide — follow [INSTALL.en.md section 8](INSTALL.en.md#8-automation).

Use `pythonw` and `-WindowStyle Hidden`, or every trigger throws a console window on screen; the watchdog fires every five minutes. Set the execution time limit on long-running tasks to unlimited.

---

## 9. Final check

```bash
python scripts\check-server.py
```

Ordered so that **a failure below is usually caused by one above — start at the topmost failure**:

```
local        is the server process alive
DNS          does the domain point at your public IP
tunnel       means something different here, see below
outside      can a third party see it
web map      does the map site respond
```

> **Ignore the tunnel layer in this setup.** It exists to check playit; with forwarding, the outside-view layer is the one that matters.

Then have a friend actually connect — **passing an external check is not the same as a player getting in**.

---

## Troubleshooting

### Specific to port forwarding

**External checks say unreachable, but the server is clearly running**

Rule things out in this order:

1. **You are behind carrier-grade NAT** (section 3.0). The most common cause, and no amount of configuration fixes it.
2. **The LAN address changed** and the forward now points at another machine. Compare the current address against what the router has, then make a DHCP reservation.
3. **The Windows firewall rule is missing**, or the network is set to Public so the rule does not apply.
4. **Double NAT**, with the outer device unconfigured.
5. **The ISP blocks the port.** A few do. Try a different external port — external 25566 → internal 25565, with players typing `:25566`.

**You cannot reach `yourdomain:25565` yourself, but friends can**

Normal. Many routers do not support NAT hairpinning — reaching your own public address from inside. Use the LAN address at home, for example `192.168.1.50`.

**It worked yesterday and today nobody can connect**

Your public IP changed. Compare <https://api.ipify.org> against the DNS record. This is why section 3.4 recommends a domain and dynamic DNS.

**Bedrock players cannot connect but Java players can**

Bedrock is UDP. If the forwarding rule's protocol is set to TCP, this is exactly what happens. Check that the 19132 rule says UDP.

### General

**Something dies or hangs with no error at all**
Check Controlled Folder Access first (part 0). It blocks writes silently and the symptoms point somewhere else entirely.

**A `.bat` spits out garbage commands halfway through**
Batch files must be **pure ASCII with CRLF endings**. cmd.exe reads them in the OEM codepage; UTF-8 comments get shredded and the fragments run as commands.

**A `.ps1` reports `MissingEndCurlyBrace` on a line that is fine**
A PowerShell script containing non-ASCII text must be saved as **UTF-8 with BOM**. Check it with this rather than by eye:

```powershell
$e=$null; [void][System.Management.Automation.Language.Parser]::ParseFile('path',[ref]$null,[ref]$e); $e
```

**A scheduled task flashes a window every time it runs**
Use `pythonw` instead of `python`, and `-WindowStyle Hidden` for PowerShell. In your own scripts, pass `creationflags=CREATE_NO_WINDOW` on every `subprocess` call.

**RCON commands time out when nobody is online**
Paper pauses an idle server (`Server empty for 60 seconds, pausing` in the log). Send large batches of RCON commands in smaller pieces.

**The map page is blank**
Turn compression off on Cloudflare Pages.
