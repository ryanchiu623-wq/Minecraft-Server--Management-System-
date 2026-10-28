# bundled

**繁體中文** · [English](README.en.md)

伺服器上用的檔案：兩個自己寫的 Paper 外掛和 DeluxeMenus 選單。安裝程式會把 PanelKey 和選單一起裝好；RyanDrawers 要自己建置。

| 目錄／檔案 | 內容 |
|---|---|
| `PanelKey-1.7.0.jar` | 建置好的 PanelKey，安裝程式用這個 |
| `panelkey-src/` | PanelKey 原始碼 |
| `drawers-src/` | RyanDrawers 原始碼，和它的自動測試外掛 `selftest/` |
| `deluxemenus/` | 選單 YAML：`admin_panel`、`admin_stop_confirm`、`toolbox`、`stations`、`player_menu` |

---

## PanelKey

遊戲內的管理入口。

| 指令／操作 | 做什麼 |
|---|---|
| Shift + 換手鍵（F） | 有 `serverpanel.admin` 權限開管理面板，其他人開玩家選單 |
| `/menu` | 開管理面板（DeluxeMenus） |
| `/spawn` | 回到出生點，一般玩家也能用 |
| `/mobile <站別>`（`/mb`） | 行動工作台：工作台、終界箱、鐵砧、附魔台、砂輪、切石機、鍛造台、織布機、製圖台 |
| `/givetarget`（`/gt`） | 選一個玩家當「給予對象」，之後工具箱發的東西都給他 |
| `/tpamenu`（`/tpam`） | 列出線上玩家，點頭像就送出 EssentialsX 的 `/tpa` |
| `/serverctl <stop\|restart\|cancel>` | 透過工具包的 `restart-sequence.py` 倒數 5 分鐘關服或重開，或取消倒數 |
| 遊戲內打 `/stop`、`/restart` | `guard-stop: true` 時改成跟 `/serverctl` 一樣的 5 分鐘倒數。主控台和 RCON 仍然立即關服 |

它也註冊 `%panelkey_target%` 這個 PlaceholderAPI 變數，讓選單 YAML 能把物品發給指定的人。

另外可以只把 QualityArmory 的槍械材質包發給有 `serverpanel.gunpack` 權限的人（預設 OP），其他人用不了 `/qa getResourcepack`、`/qa sendResourcepack`。要記得把 QualityArmory 設定裡的 `sendOnJoin` 關掉。

**設定**（`plugins/PanelKey/config.yml`）：

| 項目 | 說明 |
|---|---|
| `sequence-command` | 執行 `restart-sequence.py` 的指令，例如 `["C:/.../pythonw.exe", "C:/mc-toolkit/scripts/restart-sequence.py"]`。留空會停用 `/serverctl` 和 `guard-stop` |
| `guard-stop` | 遊戲內的 `/stop`、`/restart` 改成倒數 |
| `gun-pack-url` | 槍械材質包網址，留空就不發 |
| `require-sneak` | `false` 時單按 F 就開選單，代價是不能正常換手 |

**依賴**：DeluxeMenus（選單由它提供）、PlaceholderAPI（選填，只有 `%panelkey_target%` 需要）。`/tpamenu` 需要 EssentialsX。

---

## RyanDrawers

仿 Storage Drawers 模組的抽屜。方塊本身是木桶，正面用浮空的物品和文字顯示裡面放了什麼，所以玩家不用裝模組或材質包。基岩版玩家看到的顯示還沒驗證過。

| 操作 | 做什麼 |
|---|---|
| 右鍵正面 | 把手上的東西放進點到的那一格 |
| 快速連點兩下 | 把背包裡所有抽屜已經有的東西都放進去 |
| 左鍵正面 | 拿一組；蹲下左鍵拿一個 |
| 拿升級右鍵 | 裝上容量升級 |
| 蹲下空手右鍵 | 開設定選單：鎖定格子、拆裝升級 |
| 挖掉 | 掉出一個帶著全部內容、升級和鎖定的抽屜，放回去就還原 |

- 三種抽屜：單格、上下兩格、2×2 四格。合成是木板圍著箱子（任何木材可以混用）。
- 五種升級：黑曜石、鐵、金、鑽石、綠寶石，倍率 ×2／×4／×8／×16／×32，可以疊加。
- 漏斗可以送進和抽出。爆炸炸不掉、火燒不掉。從正面一下就打掉會被擋下，避免本來想拿東西卻把整個抽屜挖掉。
- 管理員指令：`/drawers give <玩家> <single|double|quad|upgrade1..5> [數量]`、`/drawers place <世界> <x> <y> <z> <1|2|4> <方向>`、`/drawers info <世界> <x> <y> <z>`。

**設定**（`plugins/RyanDrawers/config.yml`）：每種抽屜的基本組數、升級倍率、升級格數上限、是否開放合成、圖示顯示距離。

### 自動測試

`drawers-src/selftest/` 是只裝在測試服的外掛。它用一個假玩家把真的事件（右鍵、左鍵、挖掘、放置、選單點擊、爆炸、燃燒、區塊載入）交給 RyanDrawers，再檢查抽屜記的數量、正面顯示和假玩家的背包。OP 在測試服打 `/drawerstest`，結果寫進伺服器日誌，每一項是一行 `PASS` 或 `FAIL`。

它看不到畫面，所以圖示在遊戲裡的樣子、基岩版的顯示，還是要真人進去看。**不要裝在正式伺服器上**：它會在世界裡放方塊做測試。

---

## 自行建置

沒有用 Maven 或 Gradle，直接 `javac` 對著 Paper 自己的 libraries 編就行。以 PanelKey 為例（Git Bash）：

```bash
cd panelkey-src
CP=$( { find /c/mc-paper/libraries -name "*.jar"; \
        ls /c/mc-paper/plugins/PlaceholderAPI-*.jar; } \
      | tr '\n' '\0' | xargs -0 cygpath -w | tr '\n' ';')

javac --release 21 -cp "$CP" -d build/classes $(find src/main/java -name "*.java")
cp src/main/resources/*.yml build/classes/
jar cf ../PanelKey-1.7.0.jar -C build/classes .
```

RyanDrawers 一樣，只是不需要 PlaceholderAPI；建置 `selftest/` 時 classpath 還要加上 RyanDrawers 的 jar。

把 `/c/mc-paper` 換成你自己的伺服器路徑。`--release 21` 是編出來的 class 版本，Java 21 以上的伺服器都能載入。

伺服器執行中 Windows 會鎖住外掛 jar，要換版本用 `scripts/swap-plugin.py`，它會先倒數關服再換。
