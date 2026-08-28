# bundled

[繁體中文](README.md) · **English**

Files the installer lays down on the server, shipped inside the .exe.

## PanelKey

A small Paper plugin written for this toolkit. It provides the in-game half of the admin panel:

| Command | What it does |
|---|---|
| `/menu` | Opens the admin panel (DeluxeMenus) |
| `/spawn` | Back to spawn — ordinary players can use it too |
| `/mobile <station>` | Portable workstations: crafting table, ender chest, anvil, enchanting table, grindstone, stonecutter, smithing table, loom, cartography table |
| `/givetarget` | Pick a player as the give-target; the toolbox then hands items to them |
| Shift + swap-hands | Opens the panel without typing a command |

It also registers the `%panelkey_target%` PlaceholderAPI placeholder, which is what lets the menu YAML give items to the chosen player rather than only to whoever opened it.

**Dependencies**: PlaceholderAPI (optional, only for `%panelkey_target%`), DeluxeMenus (it supplies the menus `/menu` opens).

### Building it yourself

`panelkey-src/` holds the complete source. There is no Maven or Gradle — `javac` against Paper's own libraries is enough:

```bash
cd panelkey-src
CP=$( { find /c/mc-paper/libraries -name "*.jar"; \
        ls /c/mc-paper/plugins/PlaceholderAPI-*.jar; } \
      | tr '\n' '\0' | xargs -0 cygpath -w | tr '\n' ';')

javac --release 21 -cp "$CP" -d build/classes $(find src/main/java -name "*.java")
cp src/main/resources/*.yml build/classes/
jar cf ../PanelKey-1.3.0.jar -C build/classes .
```

Replace `/c/mc-paper` with your own server path. `--release 21` has to match the server's Java version.
