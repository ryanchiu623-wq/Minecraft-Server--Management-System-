# bundled

**繁體中文** · [English](README.en.md)

Files the installer lays down on the server, shipped inside the .exe.

## PanelKey

A small Paper plugin written for this toolkit. It provides the in-game side of
the admin panel:

| 指令 | 做什麼 |
|---|---|
| `/menu` | 開啟管理面板（DeluxeMenus） |
| `/spawn` | 回到出生點，一般玩家也能用 |
| `/mobile <站別>` | 行動工作台：工作台、終界箱、鐵砧、附魔台、砂輪、切石機、鍛造台、織布機、製圖台 |
| `/givetarget` | 選一個玩家當「給予對象」，之後工具箱發的東西都給他 |
| Shift + 換手鍵 | 直接開面板，不用打指令 |

它也註冊 `%panelkey_target%` 這個 PlaceholderAPI 變數，讓選單 YAML 能把物品發給指定的人而不是只能發給自己。

**依賴**：PlaceholderAPI（選填，只有 `%panelkey_target%` 需要）、DeluxeMenus（`/menu` 要開的選單由它提供）。

### 自行建置

`panelkey-src/` 是完整原始碼。沒有用 Maven 或 Gradle，直接 `javac` 對著 Paper 自己的 libraries 編就行：

```bash
cd panelkey-src
CP=$( { find /c/mc-paper/libraries -name "*.jar"; \
        ls /c/mc-paper/plugins/PlaceholderAPI-*.jar; } \
      | tr '\n' '\0' | xargs -0 cygpath -w | tr '\n' ';')

javac --release 21 -cp "$CP" -d build/classes $(find src/main/java -name "*.java")
cp src/main/resources/*.yml build/classes/
jar cf ../PanelKey-1.3.0.jar -C build/classes .
```

把 `/c/mc-paper` 換成你自己的伺服器路徑。`--release 21` 要對得上伺服器的 Java 版本。
