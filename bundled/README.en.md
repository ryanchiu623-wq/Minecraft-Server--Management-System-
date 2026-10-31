# bundled

[繁體中文](README.md) · **English**

What goes onto the server: two Paper plugins written for this toolkit, one Geyser extension and the DeluxeMenus menus. The installer lays down PanelKey and the menus; RyanDrawers and EmoteOffhand you build yourself.

| Path | Contents |
|---|---|
| `PanelKey-1.7.0.jar` | PanelKey, built; this is what the installer uses |
| `panelkey-src/` | PanelKey source |
| `drawers-src/` | RyanDrawers source, and its self-test plugin in `selftest/` |
| `emoteoffhand-src/` | EmoteOffhand (Geyser extension) source |
| `deluxemenus/` | Menu YAML: `admin_panel`, `admin_stop_confirm`, `toolbox`, `stations`, `player_menu`, `drawers` |

---

## PanelKey

The in-game way into server management.

| Command / action | What it does |
|---|---|
| Sneak + swap hands (Shift+F) | Opens the admin panel for `serverpanel.admin`, the player menu for everyone else. Bedrock has no swap-hands key; with EmoteOffhand it is sneak + emote |
| `/menu` | Opens the admin panel (DeluxeMenus) |
| `/spawn` | Back to spawn; open to every player |
| `/mobile <station>` (`/mb`) | Portable workstations: crafting table, ender chest, anvil, enchanting table, grindstone, stonecutter, smithing table, loom, cartography table |
| `/givetarget` (`/gt`) | Picks a player as the "give target"; the toolbox hands its items to them |
| `/tpamenu` (`/tpam`) | Lists who is online; clicking a head sends them an EssentialsX `/tpa` |
| `/serverctl <stop\|restart\|cancel>` | A 5-minute countdown stop or restart through the toolkit's `restart-sequence.py`, or calls one off |
| `/stop`, `/restart` typed in game | With `guard-stop: true`, the same 5-minute countdown as `/serverctl`. The console and RCON still stop at once |

It also registers the PlaceholderAPI placeholder `%panelkey_target%`, so menu YAML can hand items to a chosen player.

It can also offer QualityArmory's gun resource pack to `serverpanel.gunpack` holders only (OPs by default) and refuse `/qa getResourcepack` and `/qa sendResourcepack` to everyone else. Turn `sendOnJoin` off in QualityArmory's own config for this.

**Settings** (`plugins/PanelKey/config.yml`):

| Key | Meaning |
|---|---|
| `sequence-command` | How to run `restart-sequence.py`, e.g. `["C:/.../pythonw.exe", "C:/mc-toolkit/scripts/restart-sequence.py"]`. Empty turns off `/serverctl` and `guard-stop` |
| `guard-stop` | Turn `/stop` and `/restart` typed in game into the countdown |
| `gun-pack-url` | The gun resource pack's URL; empty turns it off |
| `require-sneak` | `false` opens the menu on F alone, at the cost of normal hand swapping |

**Depends on**: DeluxeMenus (it provides the menus); PlaceholderAPI (optional, only for `%panelkey_target%`). `/tpamenu` needs EssentialsX.

---

## RyanDrawers

Drawers in the style of the Storage Drawers mod. The block is a barrel, and floating item and text displays on its front show what it holds, so players need no mod and no resource pack. How the displays look to Bedrock players has not been checked yet.

| Action | What it does |
|---|---|
| Right-click the front | Puts what you hold into the slot you clicked |
| Quick double right-click | Puts everything in your inventory that the drawer already holds into it |
| Left-click the front | Takes a stack; sneak + left-click takes one |
| Right-click holding an upgrade | Installs it |
| Sneak + right-click empty-handed | Settings menu: lock slots, add or remove upgrades |
| Break it | Drops one drawer carrying its contents, upgrades and locks; placing it restores everything |

- Three drawers: single, two slots stacked, and 2×2. Crafted from planks around chests (any wood, mixed is fine).
- Five upgrades: obsidian, iron, gold, diamond, emerald — ×2 / ×4 / ×8 / ×16 / ×32, and they add up.
- Hoppers feed and drain them. Explosions and fire leave them alone. A front hit that would break one instantly is cancelled, so a click meant to take items never mines the drawer.
- Players can trade 3 iron ingots for a single drawer from the player menu (`/drawers buy`, permission `drawers.buy`, open to everyone by default). The price is `buy:` in the config; renamed ingots never count.
- Admins take drawers and upgrades for free from the "中藥櫃" page of the toolbox (`deluxemenus/drawers.yml`).
- Admin commands: `/drawers give <player> <single|double|quad|upgrade1..5> [amount]`, `/drawers place <world> <x> <y> <z> <1|2|4> <facing>`, `/drawers info <world> <x> <y> <z>`.

**Settings** (`plugins/RyanDrawers/config.yml`): base stacks per drawer type, upgrade multipliers, upgrades per drawer, whether recipes are on, how far the displays are drawn.

### Self-test

`drawers-src/selftest/` is a plugin for a test server only. A fake player hands RyanDrawers real events — right and left clicks, breaking, placing, menu clicks, explosions, fire, chunk loads — and the test checks the drawer's stored counts, its front displays and the fake player's inventory. An OP runs `/drawerstest` on the test server; each check is a `PASS` or `FAIL` line in the server log.

It cannot see the screen, so how the displays look in game and on Bedrock still needs a person. **Do not install it on a live server**: it places blocks in the world to test with.

---

## EmoteOffhand

Makes a Bedrock emote act as the Java swap-hands key (F). Bedrock has no such key, so Bedrock players could neither open the PanelKey menu (sneak + F) nor reload a QualityArmory gun with F.

Geyser used to do this through its `emote-offhand-workaround` option; newer builds dropped it and leave it to extensions listening for `ClientEmoteEvent`. On each emote this one sends a swap-hands for the player, which the server sees exactly as a Java player's F. The emote still plays.

To install, put the built jar in `plugins/Geyser-Spigot/extensions/` and restart the server (not `geyser reload`).

---

## Building

No Maven or Gradle: `javac` against Paper's own libraries is enough. PanelKey, in Git Bash:

```bash
cd panelkey-src
CP=$( { find /c/mc-paper/libraries -name "*.jar"; \
        ls /c/mc-paper/plugins/PlaceholderAPI-*.jar; } \
      | tr '\n' '\0' | xargs -0 cygpath -w | tr '\n' ';')

javac --release 21 -cp "$CP" -d build/classes $(find src/main/java -name "*.java")
cp src/main/resources/*.yml build/classes/
jar cf ../PanelKey-1.7.0.jar -C build/classes .
```

RyanDrawers is the same without PlaceholderAPI; for `selftest/`, add the RyanDrawers jar to the classpath. EmoteOffhand needs only `plugins/Geyser-Spigot.jar` on the classpath; copy its `extension.yml` into `build/classes/` the same way.

Replace `/c/mc-paper` with your own server's path. `--release 21` sets the class version, which any server on Java 21 or newer loads.

Windows locks a plugin jar while the server runs; to replace one, use `scripts/swap-plugin.py`, which counts the server down first.
