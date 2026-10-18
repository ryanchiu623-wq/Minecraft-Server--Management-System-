# Minecraft 伺服器操作手冊

**Java Edition 26.3 Wilderness Bound × Server Management System**

這台伺服器的完整操作參考：原版指令、外掛堆疊、以及本機管理工具。
前 24 節是通用的 Minecraft 26.3 指令參考，第 25 節之後是這套 toolkit 搭出來的伺服器的實際操作。

| | |
|---|---|
| 核心 | Paper 26.3（Minecraft Java 26.3，2026-09-15） |
| 需求 | Java 25 以上 · 資料包格式 121.0 |
| 外掛 | Geyser、Floodgate、BlueMap、DeluxeMenus、PlaceholderAPI、LuckPerms、WorldEdit、WorldGuard、DiscordSRV、PanelKey |
| 更新 | 2026 年 10 月 |

> ⚠️ **WorldEdit 是目前 26.3 的卡點。** stable 7.4.5 只宣告到 26.2，26.3 支援在 7.4.6。WorldGuard 沒有 WorldEdit 不會啟動，升級前務必確認。

---

<a id="toc"></a>

## 目錄

|     |                                              |
|-----|----------------------------------------------|
| 01  | [26.3 更新重點與升級須知](#s01)              |
| 02  | [26.3 新增指令：compute 與 posteffect](#s02) |
| 03  | [指令基礎語法與符號慣例](#s03)               |
| 04  | [座標寫法](#s04)                             |
| 05  | [目標選擇器](#s05)                           |
| 06  | [權限等級（OP Level）](#s06)                 |
| 07  | [伺服器控制台與管理指令](#s07)               |
| 08  | [玩家、白名單與封鎖管理](#s08)               |
| 09  | [遊戲規則 gamerule（26.3 全表）](#s09)       |
| 10  | [舊名 → 新名 完整對照表](#s10)               |
| 11  | [世界、時間、天氣與世界邊界](#s11)           |
| 12  | [方塊操作](#s12)                             |
| 13  | [實體與物品](#s13)                           |
| 14  | [傳送與位置](#s14)                           |
| 15  | [效果、附魔、屬性與經驗](#s15)               |
| 16  | [記分板、隊伍與 Bossbar](#s16)               |
| 17  | [訊息、聲音、粒子與 dialog](#s17)            |
| 18  | [execute 完整子指令表](#s18)                 |
| 19  | [資料包、函式與排程](#s19)                   |
| 20  | [進度與配方](#s20)                           |
| 21  | [技術與除錯指令](#s21)                       |
| 22  | [Paper 26.3 專屬指令與效能診斷](#s22)        |
| 23  | [Geyser / Floodgate（基岩版互通）](#s23)     |
| 24  | [DiscordSRV（Discord 橋接）](#s24)           |
| 25  | [這台伺服器的架構](#s25)                     |
| 26  | [日常操作：管理介面](#s26)                   |
| 27  | [排程工作、備份與還原](#s27)                 |
| 28  | [LuckPerms（權限）](#s28)                    |
| 29  | [WorldEdit（建築與修補）](#s29)              |
| 30  | [WorldGuard（區域保護）](#s30)               |
| 31  | [BlueMap（3D 網頁地圖）](#s31)               |
| 32  | [DeluxeMenus 與 PlaceholderAPI](#s32)        |
| 33  | [PanelKey（自製外掛）](#s33)                 |
| 34  | [升級到新版 Paper 的完整流程](#s34)          |
| 35  | [這台伺服器的疑難排解](#s35)                 |
| 36  | [server.properties 重點設定](#s36)           |
| 37  | [實用指令組合與錯誤排查](#s37)               |

<div class="newpage">

<span id="s01"></span>

<a id="s01"></a>

## 01 · 26.3 更新重點與升級須知

### 這一版是什麼

26.3 的正式名稱是 **Wilderness Bound**，2026 年 9 月 15 日發布，是 2026 年的第三個 game drop。主要加入斑駁森林（dappled forest）生態域、白楊木（poplar）整套木材、紅灌木、層架蘑菇、羊毛與混凝土的樓梯與半磚、稻草床、坐墊（cushion），以及新結構「廢棄營地」。

| 項目           | 數值                                                                                       |
|----------------|--------------------------------------------------------------------------------------------|
| 發布日期       | 2026 年 9 月 15 日                                                                         |
| 最低 Java 版本 | **Java SE 25**（自 26.1 起即為此需求，從 26.2 升上來不必換）                               |
| 通訊協定版本   | 777                                                                                        |
| 資料版本       | 5023                                                                                       |
| 資料包格式     | **121.0**                                                                                  |
| 資源包格式     | 97.1                                                                                       |
| Paper 狀態     | 2026 年 10 月 11 日起 build 175 進入 **stable** 頻道（alpha 自發布日、beta 自 9 月 28 日） |

### 伺服器端的升級檢查清單

| 要檢查的東西       | 為什麼                                                                                                                                   |
|--------------------|------------------------------------------------------------------------------------------------------------------------------------------|
| **備份**           | Paper 官方再次明確警告：升級到 26.3 之後**無法降版**。這是單向轉換，沒備份就沒有回頭路                                                   |
| Java 版本          | 必須 Java 25 以上。從 26.1／26.2 升上來不需要動                                                                                          |
| 資料包 pack_format | 改為 **121.0**，舊資料包的 `pack.mcmeta` 要更新                                                                                          |
| 燃料相關資料包     | `#brewing_fuel` 物品標籤**已被移除**，改用 `minecraft:brewing_fuel` 組件；熔爐燃料也改為 `minecraft:cooking_fuel` 組件                   |
| 插件相容性         | 逐一確認插件標示支援 26.3。Geyser 自 10 月 15 日起支援 26.3                                                                              |
| Paper 設定檔       | 26.3 本身沒動，但 Paper 預告**下一個大版本 26.4 會合併設定檔**——bukkit.yml、spigot.yml、paper 各檔的設定將整併到一起。現在就可以開始留意 |

> 🆕 **跨版本連線的過渡方案：**如果你暫時不想動主服，或玩家客戶端版本不一致，ViaVersion 5.12.0 以上可以讓 26.3 的客戶端連進 26.2 的伺服器；反方向（26.2 客戶端連 26.3 伺服器）還要再加 ViaBackwards。換版前記得先通知玩家。

### 從 26.2 升到 26.3 的實際變動

| 變動                           | 影響                                                                                                                       |
|--------------------------------|----------------------------------------------------------------------------------------------------------------------------|
| 新增 `/compute`                | 在各種情境中計算 number provider，可直接餵給 `/data modify`。見下一節                                                      |
| 新增 `/posteffect`             | 對玩家套用畫面後處理著色器                                                                                                 |
| `/publish` 移除 gamemode 參數  | 改由新的世界選項畫面控制                                                                                                   |
| `/data modify ... set compute` | 指令語法配合 number provider 拆分調整                                                                                      |
| **`/gamerule` 行為修正**       | MC-174958 已修復：**設定值與現值相同時指令不再回報成功**。用 `execute store success` 接 `/gamerule` 的自動化腳本要重新驗證 |
| `Silent` NBT 修正              | MC-175180 已修復，部分原本靜音不完全的實體現在真的完全靜音了                                                               |
| 新實體 `cushion`               | 坐墊是**實體**不是方塊。`@e` 不加 `type=` 時會掃到它；它沒有碰撞箱、無法移動                                               |
| 實體資料 `invulnerable_time`   | 新標籤，讓生物在指定刻數內暫時無敵                                                                                         |
| 方塊 predicate `height_range`  | 依高度範圍判定，資料包可用                                                                                                 |
| 規則測試 `minecraft:not`       | 反轉一個 rule test 的結果                                                                                                  |
| 除錯屬性 `ENABLE_FARLANDS`     | 關閉 Beta 1.8 的 modulo 修正，讓遠境重現（純效能比較用途）                                                                 |

> ℹ️ **遊戲規則清單在 26.3 沒有增減。**26.2 的 snake_case 名稱全部沿用，只有兩條規則的說明文字做了標點與大小寫的修正（`fire_spread_radius_around_player` 與 `entity_drops`）。如果你已經做過 26.2 的改名，這一版不必再改。

<span id="s02"></span>

<a id="s02"></a>

## 02 · 26.3 新增指令：compute 與 posteffect

### /compute

在不同的情境（context）中求值一個 number provider，並回傳結果。在所有情境裡，`origin` 會是目前指令的執行位置，`this` 實體會是 `@s`。

| 語法                                                       | 說明                                                        |
|------------------------------------------------------------|-------------------------------------------------------------|
| /compute \<target\> integer \<int_provider\>               | 整數模式                                                    |
| /compute \<target\> float \<float_provider\> \[\<scale\>\] | 浮點模式，`scale` 預設 1.0，結果會乘上 scale 後向負無窮取整 |

#### \<target\> 的三種情境

| target            | 情境                                                                            |
|-------------------|---------------------------------------------------------------------------------|
| default           | `minecraft:command_compute_default`，只有共通參數（位置與 `this` 實體）可用     |
| block \<pos\>     | `minecraft:command_compute_position`，方塊狀態與方塊座標會依 `<pos>` 的方塊設定 |
| entity \<選擇器\> | `minecraft:command_compute_entity`，`target_entity` 設為選擇器結果              |

    # 把 compute 的結果寫進 storage
    /data modify storage foo bar set compute entity @n[type=minecraft:armor_stand] {type:score,target:{type:context,target:target_entity},score:baz}

    # 整數模式：對某座標的方塊求值
    /compute block ~ ~-1 ~ integer <int_provider>

    # 浮點模式並放大 100 倍（保留兩位小數的常見做法）
    /compute default float <float_provider> 100

> ⚠️ **兩個容易中招的地方：**  
> 整數模式會在中間步驟做截斷，所以即使 `scale` 是 1.0，結果也可能與浮點模式不同。  
> number provider 求值失敗時（例如除以零）**整個指令會失敗**，不是回傳 0。寫自動化時要把這個情況考慮進去。

### /posteffect

對玩家加上或移除畫面後處理著色器（post effect）——也就是在遊戲正常渲染完成之後，再套用到玩家螢幕上的效果。

| 指令                                         | 說明                         |
|----------------------------------------------|------------------------------|
| /posteffect add \<player\> \<posteffect\>    | 加上效果（已存在則不重複加） |
| /posteffect remove \<player\> \<posteffect\> | 移除指定效果                 |
| /posteffect clear \<player\>                 | 移除該玩家所有後處理效果     |
| /posteffect list \<target\>                  | 列出目前套用的效果           |

> ⚠️ **後處理效果存在於客戶端，不在伺服器。**它們是資源包的一部分，所以**伺服器無從得知某個效果是否真的會生效**。如果你的玩家沒有載入對應的資源包，指令會成功但畫面不會有任何變化——這在多人伺服器上特別容易誤判成「指令壞了」。  
> 基岩版玩家透過 Geyser 連線時更是完全看不到效果，因為那是 Java 客戶端的渲染管線。

<span id="s03"></span>

<a id="s03"></a>

## 03 · 指令基礎語法與符號慣例

Minecraft Java 版自 1.13 起使用 **Brigadier** 指令解析系統，所有指令在聊天欄以 `/` 開頭；在伺服器控制台輸入時**不加** `/`。

### 本手冊的符號約定

| 符號     | 意義                                         |
|----------|----------------------------------------------|
| \<必填\> | 尖括號代表必須填入的參數，實際輸入時不打括號 |
| \[選填\] | 方括號代表可省略的參數                       |
| A\|B\|C  | 直線代表擇一，只能填其中一個                 |
| ...      | 代表可重複多個相同型別的參數                 |

### 常見參數型別

| 型別        | 說明與範例                                                                |
|-------------|---------------------------------------------------------------------------|
| \<player\>  | 玩家名稱或選擇器，例如 `Ryan`、`@p`                                       |
| \<targets\> | 可指向多個實體的選擇器，例如 `@e[type=zombie]`                            |
| \<pos\>     | 三個數字的座標，例如 `100 64 -250` 或 `~ ~2 ~`                            |
| \<block\>   | 方塊 ID + 方塊狀態 + NBT，例如 `minecraft:repeater[delay=4,facing=north]` |
| \<item\>    | 物品 ID + 組件，例如 `diamond_sword[custom_name='"神劍"']`                |
| \<nbt\>     | SNBT 格式資料，例如 `{NoAI:1b,Silent:1b}`                                 |
| \<json\>    | 文字組件 JSON，用於 tellraw / title                                       |

> ℹ️ **物品組件（Item Components）：**1.20.5 之後物品 NBT 全面改為組件語法。舊寫法 `diamond_sword{Damage:10}` 已失效，必須寫成 `diamond_sword[damage=10]`。實體與方塊實體仍使用傳統 NBT。  
> 26.3 又新增了一批組件：`attack_animation`、`interact_animation`、`block_transformer`、`brewing_fuel`、`cooking_fuel`、`compostable`、`mob_visibility`、`villager_food`、`sign_text_front` / `sign_text_back`、`provides_pottery_pattern`、`waxed`、`cushion/color`。

### SNBT 數值後綴

| 後綴        | 型別                                      |
|-------------|-------------------------------------------|
| 1b          | Byte（布林值常用，0b = false，1b = true） |
| 1s          | Short                                     |
| 1 / 1L      | Int / Long                                |
| 1.0f / 1.0d | Float / Double                            |
| \[I;1,2,3\] | Int 陣列（UUID 常用）                     |

<span id="s04"></span>

<a id="s04"></a>

## 04 · 座標寫法

| 寫法        | 意義                                                    |
|-------------|---------------------------------------------------------|
| 100 64 -250 | **絕對座標**：世界的固定位置                            |
| ~ ~ ~       | **相對座標**：以執行位置為原點                          |
| ~ ~5 ~-3    | 相對：正上方 5 格、Z 軸負向 3 格                        |
| ^ ^ ^5      | **本地座標**：以執行者「視線朝向」為基準，`^左 ^上 ^前` |

> 💡 **本地座標的用途：**`^ ^ ^3` 永遠代表「面朝方向前方 3 格」，不管玩家轉向哪裡。做投射物、雷射、視線追蹤時比相對座標好用太多。三種座標**不可混用**（不能寫 `~ ^ ~`）。

整數座標在指令中會被解讀為**方塊角落**；若要對齊方塊中心請寫小數，例如 `100.5 64 -249.5`。使用 `~` 時則會保留原本的小數位置。

<span id="s05"></span>

<a id="s05"></a>

## 05 · 目標選擇器

| 選擇器 | 指向對象                                        |
|--------|-------------------------------------------------|
| @p     | 最近的玩家                                      |
| @r     | 隨機一位玩家                                    |
| @a     | 所有玩家（含死亡中的玩家）                      |
| @e     | 所有實體（包含掉落物、盔甲座、彈射物、坐墊等）  |
| @s     | 指令執行者本身                                  |
| @n     | 最近的單一實體，等同 `@e[limit=1,sort=nearest]` |

### 選擇器參數完整表

| 參數               | 說明                                                                      |
|--------------------|---------------------------------------------------------------------------|
| x, y, z            | 搜尋原點座標                                                              |
| distance=..5       | 距離範圍。`5`=剛好5、`..5`=5以內、`5..`=5以上、`3..8`=區間                |
| dx, dy, dz         | 以原點為角落的長方體範圍（體積框選）                                      |
| type=zombie        | 實體類型，`type=!player` 為排除。可用實體標籤 `type=#minecraft:skeletons` |
| name="Ryan"        | 自訂名稱比對                                                              |
| tag=marker         | Scoreboard 標籤（用 `/tag` 加的，不是隊伍）                               |
| team=red           | 所屬隊伍，`team=` 表示無隊伍                                              |
| scores={kills=5..} | 記分板分數條件                                                            |
| limit=3            | 最多選中幾個目標                                                          |
| sort=nearest       | `nearest` / `furthest` / `random` / `arbitrary`                           |
| level=10..         | 玩家經驗等級                                                              |
| gamemode=creative  | 遊戲模式                                                                  |
| x_rotation=-90..0  | 垂直視角（俯仰角，-90 為正上方）                                          |
| y_rotation=-45..45 | 水平視角（偏航角）                                                        |
| nbt={NoAI:1b}      | NBT 資料比對（**效能開銷大**）                                            |
| advancements={...} | 進度完成狀態                                                              |
| predicate=my:pred  | 使用資料包中的 predicate 判定                                             |

    # 選中 20 格內、血量低於一半、非旁觀模式的玩家
    @a[distance=..20,gamemode=!spectator,nbt={Health:0.0f..10.0f}]

    # 選中最近 3 隻沒有 AI 的殭屍
    /kill @e[type=zombie,nbt={NoAI:1b},limit=3,sort=nearest]

    # 以 (0,64,0) 為角落，X/Y/Z 各 16 格的長方體內所有掉落物
    /kill @e[type=item,x=0,y=64,z=0,dx=16,dy=16,dz=16]

> ⚠️ **效能提醒：**`@e` 不加 `type=` 會掃描世界上所有實體，在有 Geyser 玩家、實體本來就多的伺服器是明顯的 MSPT 殺手。務必先用 `type=` 縮小範圍，再用 `distance`／`dx dy dz` 限制空間，最後才用 `nbt=`。  
> 26.3 之後要多注意一件事：**坐墊是實體**。玩家蓋的休息區可能放了幾十個坐墊，一個沒加 `type=` 的 `/kill @e[type=!player]` 會把它們全部清掉。

<span id="s06"></span>

<a id="s06"></a>

## 06 · 權限等級（OP Level）

| 等級 | 可用範圍                                                                                 |
|------|------------------------------------------------------------------------------------------|
| 0    | 一般玩家。`/help`、`/list`、`/me`、`/msg`、`/trigger`                                    |
| 1    | 可繞過生怪蛋限制等，實際上很少單獨使用                                                   |
| 2    | 命令方塊等級。`/gamemode`、`/give`、`/tp`、`/effect`、`/summon`、`/gamerule`、`/compute` |
| 3    | 多人管理。`/ban`、`/kick`、`/op`、`/whitelist`                                           |
| 4    | 伺服器擁有者。`/stop`、`/save-all`、`/debug`                                             |

在 `server.properties` 以 `op-permission-level=4` 設定 OP 的預設等級；`function-permission-level=2` 決定資料包函式的執行權限。個別玩家等級記錄於 `ops.json`。Paper 伺服器上，插件權限（LuckPerms 等）與原版 OP 等級是**兩套獨立系統**，Geyser 與 DiscordSRV 的權限節點屬於前者。

<span id="s07"></span>

<a id="s07"></a>

## 07 · 伺服器控制台與管理指令

| 指令                         | 說明                                                                  |
|------------------------------|-----------------------------------------------------------------------|
| /stop                        | 安全關閉伺服器（會先存檔）。**永遠用這個，不要直接 Ctrl+C**           |
| /save-all \[flush\]          | 立即存檔。加 `flush` 會強制寫入磁碟並阻塞主執行緒                     |
| /save-off                    | 停止自動存檔（備份前使用）                                            |
| /save-on                     | 恢復自動存檔                                                          |
| /reload                      | 重新載入資料包與戰利品表（**不會**重載 plugin 或 server.properties）  |
| /list \[uuids\]              | 列出線上玩家（含 Geyser 玩家）                                        |
| /seed                        | 顯示世界種子碼                                                        |
| /setidletimeout \<分鐘\>     | 閒置多久自動踢出，0 為停用                                            |
| /publish \[port\]            | 單人世界開啟區網。**26.3 已移除 gamemode 參數**，改由世界選項畫面控制 |
| /debug start\|stop\|function | 開始／結束效能分析，產出報告檔                                        |
| /perf start\|stop            | 記錄詳細效能取樣，輸出至 debug 資料夾                                 |
| /jfr start\|stop             | Java Flight Recorder 分析                                             |
| /version                     | 顯示核心與版本（Paper 上會顯示 build 編號）                           |

> 💡 **備份標準流程：**  
> `save-off` → `save-all flush` → 複製世界資料夾 → `save-on`  
> 26.1 之後世界格式已改變，且每升一版就無法降回去，備份的重要性比以前更高。少了 `save-off` 就複製，很容易複製到寫到一半的區塊檔而導致存檔損毀。

<span id="s08"></span>

<a id="s08"></a>

## 08 · 玩家、白名單與封鎖管理

| 指令                                    | 說明                                               |
|-----------------------------------------|----------------------------------------------------|
| /op \<player\>                          | 給予管理員權限                                     |
| /deop \<player\>                        | 移除管理員權限                                     |
| /kick \<player\> \[原因\]               | 踢出玩家                                           |
| /ban \<player\> \[原因\]                | 封鎖玩家帳號                                       |
| /ban-ip \<IP\|player\> \[原因\]         | 封鎖 IP 位址                                       |
| /banlist \[ips\|players\]               | 列出封鎖名單                                       |
| /pardon \<player\>                      | 解除帳號封鎖                                       |
| /pardon-ip \<IP\>                       | 解除 IP 封鎖                                       |
| /whitelist on\|off                      | 啟用／停用白名單                                   |
| /whitelist add\|remove \<player\>       | 新增／移除白名單（**基岩版玩家要用 /fwhitelist**） |
| /whitelist list                         | 列出白名單                                         |
| /whitelist reload                       | 重新讀取 whitelist.json（手動改檔後必用）          |
| /gamemode \<模式\> \[targets\]          | survival / creative / adventure / spectator        |
| /defaultgamemode \<模式\>               | 新玩家的預設模式                                   |
| /difficulty \<難度\>                    | peaceful / easy / normal / hard                    |
| /transfer \<host\> \[port\] \[players\] | 將玩家轉送到另一台伺服器                           |
| /fetchprofile \<player\>                | 預先抓取玩家 profile 以填入 UUID／皮膚快取         |

<div class="newpage">

<span id="s09"></span>

<a id="s09"></a>

## 09 · 遊戲規則 gamerule（26.3 全表）

語法：`/gamerule <規則名> [值]`，省略值則顯示目前設定。需要權限等級 2。

> ⚠️ **26.x 的規則名稱一律是 snake_case。**1.21.11 起所有遊戲規則被移進 registry，名稱改成資源位置格式，並且很多規則被**重新命名以對應「編輯遊戲規則」選單的用字**，部分規則的布林值也被反轉。`/gamerule keepInventory true` 在 26.x 是無效指令。舊名對照請看下一節。

> 🆕 **26.3 的行為修正：**MC-174958 已修復——**當你設定的值與目前值相同時，`/gamerule` 不再回報成功**。如果你有用 `execute store success` 接 `/gamerule` 來做狀態偵測或開關鎖定的自動化，這個改動會直接影響判斷結果，升級後務必重測。

### Chat（聊天與回饋）

| 規則                      | 預設 | 說明                                                             |
|---------------------------|------|------------------------------------------------------------------|
| command_block_output      | true | 命令方塊執行時是否通知管理員。**大型紅石作品務必設 false**       |
| log_admin_commands        | true | 管理指令是否寫入伺服器 log                                       |
| send_command_feedback     | true | 玩家執行指令的回饋是否顯示在聊天，也影響命令方塊是否儲存輸出文字 |
| show_advancement_messages | true | 進度達成是否公告                                                 |
| show_death_messages       | true | 死亡訊息，也影響寵物死亡時是否通知主人                           |

### Drops（掉落）

| 規則                         | 預設  | 說明                                                                                            |
|------------------------------|-------|-------------------------------------------------------------------------------------------------|
| block_drops                  | true  | 方塊被破壞時是否掉落。設 false 時容器仍掉出內容物但本體不掉，**界伏盒會整個消失連內容物一起沒** |
| block_explosion_drop_decay   | true  | 方塊爆炸的掉落衰減。設 false 可 100% 回收                                                       |
| entity_drops                 | true  | 非生物實體（載具、盔甲座）掉落。設 false 時從展示框取物不會掉出                                 |
| mob_drops                    | true  | 生物掉落物品與經驗球                                                                            |
| mob_explosion_drop_decay     | true  | 生物爆炸（苦力怕）的掉落衰減                                                                    |
| projectiles_can_break_blocks | true  | 彈射物可打破紫頌花、尖牙石筍、裝飾罐                                                            |
| tnt_explosion_drop_decay     | false | TNT 爆炸的掉落衰減                                                                              |

### Miscellaneous（技術與限制）

| 規則                        | 預設  | 說明                                                                 |
|-----------------------------|-------|----------------------------------------------------------------------|
| command_blocks_work         | true  | 命令方塊是否運作                                                     |
| global_sound_events         | true  | 凋零生成、終界龍死亡、終界傳送門啟動的全域音效                       |
| max_block_modifications     | 32768 | `/clone`、`/fill`、`/fillbiome` 單次可改動的方塊上限（最小 1）       |
| max_command_forks           | 65536 | 單 tick 可產生的 execute 分支（context）數上限（最小 1）             |
| max_command_sequence_length | 65536 | 單一執行來源在一 tick 內的指令鏈長度上限（最小 0）                   |
| max_minecart_speed          | 8     | 礦車最高速度（需開啟 Minecart Improvements 實驗性功能，範圍 1–1000） |
| reduced_debug_info          | false | 限制 F3 資訊，也會關掉 F3+B 判定框與 F3+G 區塊邊界                   |
| tnt_explodes                | true  | TNT 啟動後是否爆炸。設 false 時 TNT 礦車也無法被點燃                 |

### Mobs（生物行為）

| 規則                 | 預設  | 說明                                                                                        |
|----------------------|-------|---------------------------------------------------------------------------------------------|
| forgive_dead_players | true  | 玩家死亡後，附近被激怒的中立生物是否消氣                                                    |
| max_entity_cramming  | 24    | 同格可推擠實體上限，超過每半秒扣 3 顆心。設 0 停用（最小 0）                                |
| mob_griefing         | true  | 生物破壞方塊與撿拾物品。設 false 時苦力怕仍爆炸但不破壞方塊，末影人不搬方塊，豬布林不撿金錠 |
| raids                | true  | 襲擊是否啟用。**注意這是舊 `disableRaids` 的反轉版**                                        |
| universal_anger      | false | 被激怒的中立生物攻擊所有附近玩家，搭配 `forgive_dead_players false` 效果最完整              |

### Player（玩家機制）

| 規則                                 | 預設  | 說明                                                                                          |
|--------------------------------------|-------|-----------------------------------------------------------------------------------------------|
| allow_entering_nether_using_portals  | true  | 是否能用地獄門進入地獄                                                                        |
| drowning_damage                      | true  | 溺水傷害（設 false 仍會掉氧氣，只是不扣血）                                                   |
| elytra_movement_check                | true  | 鞘翅移動速度檢查。**舊 `disableElytraMovementCheck` 的反轉版**                                |
| ender_pearls_vanish_on_death         | true  | 玩家死亡時飛行中的終界珍珠是否消失                                                            |
| fall_damage                          | true  | 摔落傷害                                                                                      |
| fire_damage                          | true  | 火焰、岩漿、營火、鎂岩塊傷害                                                                  |
| fire_spread_radius_around_player     | 128   | **取代舊的 `doFireTick`**。火焰能在玩家周圍蔓延的最大距離；0 = 完全停用蔓延，-1 = 無限距離    |
| freeze_damage                        | true  | 細雪冰凍傷害                                                                                  |
| immediate_respawn                    | false | 跳過死亡畫面直接重生                                                                          |
| keep_inventory                       | false | 死亡保留物品欄與經驗。血量、飢餓、狀態效果仍會重置                                            |
| limited_crafting                     | false | 只能合成已解鎖的配方                                                                          |
| locator_bar                          | true  | 定位條是否啟用                                                                                |
| natural_health_regeneration          | true  | 飽食度自然回血                                                                                |
| player_movement_check                | true  | 玩家速度檢查。**舊 `disablePlayerMovementCheck` 的反轉版**                                    |
| players_nether_portal_creative_delay | 0     | 創造模式站在地獄門中的延遲（最小 0）                                                          |
| players_nether_portal_default_delay  | 80    | 非創造模式的地獄門延遲，單位 tick（最小 0）                                                   |
| players_sleeping_percentage          | 100   | 需多少 % 玩家睡覺才跳過夜晚。0 或更小 = 一人即可（但仍需至少一人睡），大於 100 = 永遠無法跳過 |
| pvp                                  | true  | 玩家互相傷害。**26.x 起這也是遊戲規則，不只是 server.properties**                             |
| respawn_radius                       | 10    | 重生點的隨機半徑（最小 0）。舊名 `spawnRadius`                                                |
| spectators_generate_chunks           | true  | 旁觀模式是否會生成區塊。**設 false 可省下不少效能**                                           |

### Spawning（生成）

| 規則                    | 預設 | 說明                                                     |
|-------------------------|------|----------------------------------------------------------|
| spawn_mobs              | true | 自然生怪總開關。不影響指令、生怪磚、襲擊、生怪蛋、鐵傀儡 |
| spawn_monsters          | true | 敵對生物自然生成                                         |
| spawn_patrols           | true | 災厄巡邏隊                                               |
| spawn_phantoms          | true | 幻翼（舊名 `doInsomnia`）                                |
| spawn_wandering_traders | true | 流浪商人（26.3 起會販售白楊樹苗、白楊原木與層架蘑菇）    |
| spawn_wardens           | true | 伏守者                                                   |
| spawner_blocks_work     | true | 生怪磚方塊是否運作                                       |

### World Updates（世界更新）

| 規則                         | 預設  | 說明                                                                           |
|------------------------------|-------|--------------------------------------------------------------------------------|
| advance_time                 | true  | 晝夜循環與月相推進（舊名 `doDaylightCycle`）                                   |
| advance_weather              | true  | 天氣自然變化，`/weather` 仍可強制改變（舊名 `doWeatherCycle`）                 |
| lava_source_conversion       | false | 無限岩漿源                                                                     |
| max_snow_accumulation_height | 1     | 雪堆積層數（0–8；0 = 不積雪，8 以上等同滿格）                                  |
| random_tick_speed            | 3     | 每區段每 tick 的隨機刻次數。0 停用；超過 4096 生長與腐爛幾乎瞬間完成（最小 0） |
| spread_vines                 | true  | 藤蔓蔓延（洞穴藤蔓、垂淚藤、纏怨藤不受影響）                                   |
| water_source_conversion      | true  | 無限水源                                                                       |

<div class="newpage">

<span id="s10"></span>

<a id="s10"></a>

## 10 · 舊名 → 新名 完整對照表

把舊指令、舊資料包、舊命令方塊搬到 26.x 時，照這張表逐條替換。**標示「值反轉」的三條，除了改名還要把 true/false 對調。**

### 被改名（非單純大小寫轉換）

| 1.21.10 以前                  | 26.x 現行                    | 備註                         |
|-------------------------------|------------------------------|------------------------------|
| announceAdvancements          | show_advancement_messages    |                              |
| commandBlocksEnabled          | command_blocks_work          | 更早期叫 enableCommandBlocks |
| commandModificationBlockLimit | max_block_modifications      |                              |
| disableElytraMovementCheck    | elytra_movement_check        | **值反轉**                   |
| disablePlayerMovementCheck    | player_movement_check        | **值反轉**                   |
| disableRaids                  | raids                        | **值反轉**                   |
| doDaylightCycle               | advance_time                 |                              |
| doEntityDrops                 | entity_drops                 |                              |
| doImmediateRespawn            | immediate_respawn            |                              |
| doInsomnia                    | spawn_phantoms               |                              |
| doLimitedCrafting             | limited_crafting             |                              |
| doMobLoot                     | mob_drops                    |                              |
| doMobSpawning                 | spawn_mobs                   |                              |
| doPatrolSpawning              | spawn_patrols                |                              |
| doTileDrops                   | block_drops                  |                              |
| doTraderSpawning              | spawn_wandering_traders      |                              |
| doVinesSpread                 | spread_vines                 |                              |
| doWardenSpawning              | spawn_wardens                |                              |
| doWeatherCycle                | advance_weather              |                              |
| maxCommandChainLength         | max_command_sequence_length  |                              |
| maxCommandForkCount           | max_command_forks            |                              |
| naturalRegeneration           | natural_health_regeneration  |                              |
| snowAccumulationHeight        | max_snow_accumulation_height |                              |
| spawnRadius                   | respawn_radius               |                              |
| spawnerBlocksEnabled          | spawner_blocks_work          |                              |
| minecartMaxSpeed              | max_minecart_speed           | 實驗性功能                   |

### 單純轉為 snake_case（意義不變）

| 舊名                      | 新名                         | 其他同類                                                |
|---------------------------|------------------------------|---------------------------------------------------------|
| keepInventory             | keep_inventory               | mobGriefing → mob_griefing                              |
| randomTickSpeed           | random_tick_speed            | fallDamage → fall_damage                                |
| fireDamage                | fire_damage                  | freezeDamage → freeze_damage                            |
| drowningDamage            | drowning_damage              | universalAnger → universal_anger                        |
| forgiveDeadPlayers        | forgive_dead_players         | maxEntityCramming → max_entity_cramming                 |
| commandBlockOutput        | command_block_output         | logAdminCommands → log_admin_commands                   |
| sendCommandFeedback       | send_command_feedback        | showDeathMessages → show_death_messages                 |
| reducedDebugInfo          | reduced_debug_info           | globalSoundEvents → global_sound_events                 |
| waterSourceConversion     | water_source_conversion      | lavaSourceConversion → lava_source_conversion           |
| blockExplosionDropDecay   | block_explosion_drop_decay   | mobExplosionDropDecay → mob_explosion_drop_decay        |
| tntExplosionDropDecay     | tnt_explosion_drop_decay     | tntExplodes → tnt_explodes                              |
| projectilesCanBreakBlocks | projectiles_can_break_blocks | enderPearlsVanishOnDeath → ender_pearls_vanish_on_death |
| playersSleepingPercentage | players_sleeping_percentage  | spectatorsGenerateChunks → spectators_generate_chunks   |

### 已被移除的規則

| 已移除                       | 怎麼辦                                                              |
|------------------------------|---------------------------------------------------------------------|
| doFireTick                   | 改用 `fire_spread_radius_around_player`。想完全停用火焰蔓延就設 `0` |
| allowFireTicksAwayFromPlayer | 同上，功能已併入距離參數；設 `-1` 為不限距離                        |
| spawnChunkRadius             | 1.21.9 移除，無替代規則                                             |

> 💡 **批次替換小技巧：**如果你有一整包舊資料包或一堆命令方塊指令要轉，可以先把上面兩張表存成一份 sed 腳本或用編輯器的多重取代跑一遍，再手動處理那三個「值反轉」的規則——它們是唯一無法靠純文字取代解決的。

<span id="s11"></span>

<a id="s11"></a>

## 11 · 世界、時間、天氣與世界邊界

| 指令                                                        | 說明                                             |
|-------------------------------------------------------------|--------------------------------------------------|
| /time set day\|night\|noon\|midnight                        | day=1000、noon=6000、night=13000、midnight=18000 |
| /time set \<tick\>                                          | 設為指定刻（一天 24000 tick）                    |
| /time add \<tick\>                                          | 時間快轉                                         |
| /time query daytime\|gametime\|day                          | 查詢時間，常配合 `execute store` 使用            |
| /weather clear\|rain\|thunder \[秒\]                        | 設定天氣                                         |
| /setworldspawn \[pos\] \[angle\]                            | 設定世界重生點                                   |
| /spawnpoint \[targets\] \[pos\]                             | 設定個別玩家重生點                               |
| /worldborder set \<直徑\> \[秒\]                            | 設定邊界大小，可指定過渡秒數                     |
| /worldborder add \<值\> \[秒\]                              | 增減邊界大小                                     |
| /worldborder center \<x\> \<z\>                             | 設定邊界中心                                     |
| /worldborder damage amount\|buffer \<值\>                   | 越界傷害／緩衝距離                               |
| /worldborder warning distance\|time                         | 警告紅框的距離／時間                             |
| /worldborder get                                            | 查詢目前直徑                                     |
| /locate structure\|biome\|poi \<目標\>                      | 尋找最近的結構／生態域／興趣點                   |
| /place structure\|feature\|jigsaw\|template                 | 在指定位置生成結構或地物                         |
| /fillbiome \<from\> \<to\> \<biome\> \[replace \<filter\>\] | 直接改寫區域生態域                               |

> 🆕 **26.3 的新目標：**`/locate biome minecraft:dappled_forest` 可以找斑駁森林，`/locate structure minecraft:abandoned_camp` 可以找廢棄營地。廢棄營地會生成在草甸、櫻花樹林、各種森林、針葉林、沼澤、莽原、疏林惡地、蒼白花園等十幾個生態域。

<span id="s12"></span>

<a id="s12"></a>

## 12 · 方塊操作

| 指令                                     | 說明                                                |
|------------------------------------------|-----------------------------------------------------|
| /setblock \<pos\> \<block\> \[模式\]     | 放置單一方塊。`replace`（預設）/ `destroy` / `keep` |
| /fill \<from\> \<to\> \<block\> \[模式\] | 填滿長方體區域                                      |
| /fill ... replace \<filter\>             | 只取代指定的方塊類型                                |
| /clone \<from\> \<to\> \<dest\>          | 複製區域                                            |
| /clone from \<維度\> ... to \<維度\> ... | 跨維度複製                                          |

#### fill 模式

| 模式    | 說明                   |
|---------|------------------------|
| replace | 取代全部（預設）       |
| destroy | 破壞原方塊並產生掉落物 |
| keep    | 只填空氣的位置         |
| hollow  | 只填外殼，內部清成空氣 |
| outline | 只填外殼，內部保持原樣 |

#### clone 模式

| 參數                  | 說明                                         |
|-----------------------|----------------------------------------------|
| replace / masked      | 複製全部 / 只複製非空氣方塊                  |
| filtered \<block\>    | 只複製指定方塊                               |
| normal / force / move | 一般 / 允許來源與目標重疊 / 複製後把來源清空 |

    # 清空一個 32x32x32 的區域
    /fill ~-16 ~ ~-16 ~15 ~31 ~15 air

    # 把所有石頭換成玻璃，其他不動
    /fill ~-20 ~-5 ~-20 ~20 ~5 ~20 glass replace stone

    # 建一個空心箱子（保留內部）
    /fill ~-5 ~ ~-5 ~5 ~10 ~5 obsidian outline

    # 放一個朝北、延遲 4 刻的中繼器
    /setblock ~ ~ ~ repeater[delay=4,facing=north]

    # 放一個內含物品的箱子
    /setblock ~ ~1 ~ chest{Items:[{Slot:0b,id:"minecraft:diamond",count:64}]}

> ⚠️ `/fill`、`/clone`、`/fillbiome` 受 `max_block_modifications`（預設 32768）限制。大量填充會造成明顯卡頓與區塊重新光照計算，在正式伺服器上請分批進行。

> ℹ️ **26.3 新方塊的 ID 命名：**白楊木整套走 `minecraft:poplar_*`（`poplar_log`、`poplar_planks`、`poplar_shelf`…），樹葉分三色 `red_poplar_leaves` / `orange_poplar_leaves` / `yellow_poplar_leaves`。羊毛與混凝土的樓梯半磚是 `<顏色>_wool_stairs` / `_wool_slab` / `<顏色>_concrete_stairs` / `_concrete_slab`，共 16 色。稻草床是 `straw_bed`。

<span id="s13"></span>

<a id="s13"></a>

## 13 · 實體與物品

| 指令                                                         | 說明                                         |
|--------------------------------------------------------------|----------------------------------------------|
| /summon \<entity\> \[pos\] \[nbt\]                           | 生成實體                                     |
| /kill \[targets\]                                            | 清除實體。不加參數會殺死自己                 |
| /give \<player\> \<item\> \[數量\]                           | 給予物品                                     |
| /clear \[targets\] \[item\] \[數量\]                         | 清除物品欄內容                               |
| /item replace entity \<targets\> \<slot\> with \<item\>      | 替換指定欄位的物品                           |
| /item replace block \<pos\> \<slot\> with \<item\>           | 替換容器內的物品                             |
| /item modify ...                                             | 套用資料包定義的物品修飾器                   |
| /loot give\|insert\|spawn\|replace                           | 依戰利品表產生物品（可模擬挖掘、擊殺、開箱） |
| /data get entity\|block\|storage \<目標\> \[路徑\]           | 讀取 NBT                                     |
| /data merge ...                                              | 合併 NBT 資料                                |
| /data modify ... set\|append\|insert\|merge\|prepend\|remove | 精細修改 NBT                                 |
| /data modify ... set compute \<target\> \<provider\>         | **26.3 新增**：直接把 compute 的結果寫進 NBT |
| /data remove ...                                             | 刪除指定 NBT 路徑                            |
| /ride \<target\> mount\|dismount \<載具\>                    | 讓實體騎乘／下乘                             |
| /damage \<target\> \<量\> \[類型\]                           | 對實體造成指定類型傷害                       |

#### 常用 slot 名稱

| Slot                             | 位置                     |
|----------------------------------|--------------------------|
| weapon.mainhand / weapon.offhand | 主手 / 副手              |
| armor.head / chest / legs / feet | 頭 / 胸 / 腿 / 腳        |
| hotbar.0 ~ hotbar.8              | 快捷欄                   |
| inventory.0 ~ inventory.26       | 主物品欄                 |
| container.0 ~ container.n        | 容器欄位（箱子、熔爐等） |

    # 生成不會移動、不會發聲、有自訂名的殭屍
    /summon zombie ~ ~ ~ {NoAI:1b,Silent:1b,CustomName:'{"text":"石像"}',CustomNameVisible:1b}

    # 隱形無敵的標記盔甲座（技術用途）
    /summon armor_stand ~ ~ ~ {Marker:1b,Invisible:1b,Invulnerable:1b,NoGravity:1b,Tags:["myMarker"]}

    # 26.3 新增：讓生物在 100 刻內暫時無敵
    /summon zombie ~ ~ ~ {invulnerable_time:100}

    # 物品組件寫法
    /give @s netherite_sword[custom_name='{"text":"斷鋼","color":"red"}',enchantments={sharpness:5},unbreakable={}]

    # 讀取玩家目前站的位置
    /data get entity @s Pos

    # 模擬挖鑽石礦（含幸運）而不真的挖
    /loot spawn ~ ~1 ~ mine ~ ~ ~ diamond_pickaxe[enchantments={fortune:3}]

> 🆕 **26.3 的 `Silent` 修正值得留意。**MC-175180 已修復——過去有些實體即使設了 `Silent:1b` 還是會發出部分聲音，現在真的完全靜音。如果你的地圖或紅石裝置是**靠那些漏出來的聲音**當回饋或觸發，升級後會失效。

<span id="s14"></span>

<a id="s14"></a>

## 14 · 傳送與位置

| 指令                                                              | 說明                                         |
|-------------------------------------------------------------------|----------------------------------------------|
| /tp \<dest\>                                                      | `/teleport` 的縮寫，兩者等價                 |
| /tp \<targets\> \<pos\>                                           | 傳送到座標                                   |
| /tp \<targets\> \<pos\> \<yaw\> \<pitch\>                         | 指定面向角度（yaw：-180~180，pitch：-90~90） |
| /tp \<targets\> \<pos\> facing \<pos\|entity\>                    | 傳送並面向某點或某實體                       |
| /spreadplayers \<x\> \<z\> \<間距\> \<半徑\> \<成隊\> \<targets\> | 隨機分散傳送                                 |
| /spreadplayers ... under \<maxY\> ...                             | 限制最高 Y 值                                |
| /spectate \<target\> \[player\]                                   | 旁觀模式視角鎖定某實體                       |
| /forceload add \<from\> \[to\]                                    | 強制常載區塊                                 |
| /forceload remove \<from\> \[to\] / remove all                    | 取消常載                                     |
| /forceload query \[pos\]                                          | 查詢常載狀態                                 |

> 💡 **forceload 與生電：**常載區塊會被完整 tick，適合農場、自動化系統或跨維度物品運輸。但每個常載區塊都是實打實的 MSPT 成本，建議用 `/forceload query` 定期檢查有沒有忘了關掉的區塊。搭配 `spectators_generate_chunks false` 可以再省一些。

<span id="s15"></span>

<a id="s15"></a>

## 15 · 效果、附魔、屬性與經驗

| 指令                                                           | 說明                               |
|----------------------------------------------------------------|------------------------------------|
| /effect give \<targets\> \<效果\> \[秒\] \[等級\] \[隱藏粒子\] | 秒數可填 `infinite`                |
| /effect clear \[targets\] \[效果\]                             | 清除效果                           |
| /enchant \<targets\> \<附魔\> \[等級\]                         | 為手持物附魔（受原版等級上限限制） |
| /xp add\|set\|query \<targets\> \<量\> \[points\|levels\]      | 經驗值操作                         |
| /attribute \<target\> \<屬性\> get \[倍率\]                    | 讀取屬性值                         |
| /attribute \<target\> \<屬性\> base set \<值\>                 | 設定基礎屬性值                     |
| /attribute \<target\> \<屬性\> modifier add ...                | 加入屬性修飾器                     |
| /posteffect add\|remove\|clear\|list ...                       | **26.3 新增**：畫面後處理著色器    |

#### 常用屬性 ID

| 屬性                     | 說明                     |
|--------------------------|--------------------------|
| max_health               | 最大生命值               |
| movement_speed           | 移動速度（玩家預設 0.1） |
| attack_damage            | 攻擊傷害                 |
| armor / armor_toughness  | 護甲值 / 護甲韌性        |
| knockback_resistance     | 擊退抗性（0–1）          |
| scale                    | 實體大小縮放             |
| block_interaction_range  | 方塊互動距離（預設 4.5） |
| entity_interaction_range | 實體互動距離（預設 3.0） |
| step_height              | 可直接跨上的高度         |
| gravity                  | 重力                     |

> ℹ️ **屬性 ID 的命名空間：**較舊的教學會寫 `generic.max_health`、`player.block_interaction_range`，1.21.2 之後 `generic.` / `player.` 前綴已被移除，直接寫 `minecraft:max_health` 即可。輸入時按 Tab 補完是最保險的做法。

    # 永久夜視，不顯示粒子
    /effect give @s night_vision infinite 0 true

    # 把玩家的最大生命設為 40（20 顆心）
    /attribute @s minecraft:max_health base set 40

    # 把互動距離拉到 10 格（測試紅石很好用）
    /attribute @s minecraft:block_interaction_range base set 10

<span id="s16"></span>

<a id="s16"></a>

## 16 · 記分板、隊伍與 Bossbar

| 指令                                                                 | 說明                                                                              |
|----------------------------------------------------------------------|-----------------------------------------------------------------------------------|
| /scoreboard objectives add \<名稱\> \<準則\> \[顯示名\]              | 準則如 `dummy`、`health`、`deathCount`、`minecraft.mined:minecraft.stone`         |
| /scoreboard objectives remove\|list                                  | 刪除／列出目標                                                                    |
| /scoreboard objectives setdisplay \<位置\> \[名稱\]                  | `sidebar`、`list`（Tab）、`belowName`                                             |
| /scoreboard objectives modify \<名稱\> displayname\|rendertype       | 修改顯示樣式                                                                      |
| /scoreboard players set\|add\|remove \<target\> \<目標\> \<值\>      | 設定／增減分數                                                                    |
| /scoreboard players get\|reset \<target\> \[目標\]                   | 讀取／重設分數                                                                    |
| /scoreboard players operation \<A\> \<目標\> \<運算\> \<B\> \<目標\> | 運算：`= += -= *= /= %= < > ><`（`><` 為交換）                                    |
| /scoreboard players enable \<target\> \<trigger目標\>                | 開放玩家使用 `/trigger`                                                           |
| /trigger \<目標\> \[set\|add \<值\>\]                                | 權限 0 玩家唯一能改分數的指令，選單系統核心                                       |
| /team add\|remove\|empty\|list \<隊伍\>                              | 隊伍管理                                                                          |
| /team join \<隊伍\> \[members\] / leave \<members\>                  | 加入／離開隊伍                                                                    |
| /team modify \<隊伍\> \<選項\> \<值\>                                | `color`、`friendlyFire`、`nametagVisibility`、`collisionRule`、`prefix`、`suffix` |
| /tag \<targets\> add\|remove\|list \<標籤\>                          | 實體標籤（比 NBT 比對輕量，技術玩法首選標記法）                                   |
| /bossbar add\|remove\|list \<id\> \[名稱\]                           | Boss 血條管理                                                                     |
| /bossbar set \<id\> players\|value\|max\|color\|style\|visible\|name | 設定血條內容                                                                      |
| /bossbar get \<id\> value\|max\|players\|visible                     | 讀取血條狀態                                                                      |

> 💡 **collisionRule 的技術用途：**`/team modify <隊伍> collisionRule never` 讓實體之間不再互相推擠，常用於解決農場中生物擁擠造成的 MSPT 飆升，也可搭配 `max_entity_cramming` 設計壓縮式生物處理系統。

<span id="s17"></span>

<a id="s17"></a>

## 17 · 訊息、聲音、粒子與 dialog

| 指令                                                                                 | 說明                                   |
|--------------------------------------------------------------------------------------|----------------------------------------|
| /say \<訊息\>                                                                        | 以伺服器身分廣播                       |
| /msg \<player\> \<訊息\>                                                             | 私訊（`/tell`、`/w` 同義）             |
| /me \<動作\>                                                                         | 第三人稱動作訊息                       |
| /teammsg \<訊息\>                                                                    | 隊伍內訊息（`/tm`）                    |
| /tellraw \<targets\> \<json\>                                                        | 格式化文字（顏色、點擊事件、懸停提示） |
| /title \<targets\> title\|subtitle\|actionbar \<json\>                               | 螢幕標題文字                           |
| /title \<targets\> times \<淡入\> \<停留\> \<淡出\>                                  | 標題時間（tick）                       |
| /title \<targets\> clear\|reset                                                      | 清除／重設標題                         |
| /playsound \<音效\> \<來源\> \<targets\> \[pos\] \[音量\] \[音調\] \[最小音量\]      | 播放音效                               |
| /stopsound \<targets\> \[來源\] \[音效\]                                             | 停止音效                               |
| /music set\|play\|stop                                                               | 控制背景音樂                           |
| /particle \<粒子\> \[pos\] \[delta\] \[速度\] \[數量\] \[force\|normal\] \[viewers\] | 產生粒子效果                           |
| /dialog show \<target\> \<dialog\>                                                   | 對玩家開啟已註冊的對話框 UI            |
| /dialog clear \<target\>                                                             | 關閉對話框                             |

    # 有顏色、可點擊的訊息
    /tellraw @a {"text":"點我傳送到主城","color":"gold","bold":true,"clickEvent":{"action":"run_command","value":"/tp @s 0 100 0"},"hoverEvent":{"action":"show_text","contents":"座標 0, 100, 0"}}

    # 顯示玩家的分數
    /tellraw @a [{"text":"擊殺數：","color":"gray"},{"score":{"name":"@s","objective":"kills"},"color":"red"}]

    # 動作列提示（不遮擋畫面）
    /title @a actionbar {"text":"系統維護中","color":"yellow"}

    # 在指定位置畫出一團 20 顆的紅石粒子
    /particle dust{color:[1.0,0.0,0.0],scale:1.0} ~ ~1 ~ 0.5 0.5 0.5 0 20 normal

> ℹ️ **Geyser 相容性提醒：**基岩版玩家看到的 `tellraw` 格式化文字會由 Geyser 轉譯，複雜的 hoverEvent 與部分 clickEvent 動作在基岩版可能無效或顯示不完整。要讓公告對兩邊玩家都可靠，優先用純文字加顏色碼，把互動功能放在指令而不是點擊事件上。`/posteffect` 對基岩玩家則是完全無效。

<div class="newpage">

<span id="s18"></span>

<a id="s18"></a>

## 18 · execute 完整子指令表

`/execute` 是指令系統的核心。它改變「執行者、位置、朝向、維度」等執行環境，再用 `run` 執行真正的指令。子指令可任意串接。

### 修改執行環境

| 子指令                                             | 說明                                                                                            |
|----------------------------------------------------|-------------------------------------------------------------------------------------------------|
| as \<targets\>                                     | 改變**執行者**（`@s` 指向誰），但**不改變位置**                                                 |
| at \<targets\>                                     | 改變**位置、朝向、維度**，但不改變執行者                                                        |
| positioned \<pos\>                                 | 指定執行位置                                                                                    |
| positioned as \<targets\>                          | 使用目標的位置（不改朝向）                                                                      |
| positioned over \<高度圖\>                         | 移到地表高度，如 `world_surface`、`motion_blocking`                                             |
| rotated \<yaw\> \<pitch\> / rotated as \<targets\> | 指定朝向 / 使用目標朝向                                                                         |
| facing \<pos\>                                     | 朝向某座標                                                                                      |
| facing entity \<targets\> eyes\|feet               | 朝向某實體的眼睛或腳                                                                            |
| align \<xyz\>                                      | 座標向下取整對齊方塊，例如 `align xz`                                                           |
| anchored eyes\|feet                                | 設定 `^` 本地座標的基準點                                                                       |
| in \<維度\>                                        | `overworld` / `the_nether` / `the_end`                                                          |
| on \<關係\>                                        | 切換到關聯實體：`attacker`、`controller`、`leasher`、`owner`、`passengers`、`target`、`vehicle` |
| summon \<entity\>                                  | 生成實體並立即以它為執行者                                                                      |

### 條件判斷 if / unless

| 子指令                                                    | 說明                                 |
|-----------------------------------------------------------|--------------------------------------|
| if\|unless block \<pos\> \<block\>                        | 判斷單一方塊                         |
| if\|unless blocks \<from\> \<to\> \<dest\> all\|masked    | 比對兩個區域是否相同                 |
| if\|unless entity \<targets\>                             | 判斷是否存在符合的實體               |
| if\|unless score \<A\> \<目標\> \<運算\> \<B\> \<目標\>   | 比較分數（`< <= = >= >`）            |
| if\|unless score \<A\> \<目標\> matches \<範圍\>          | 分數落在範圍內，例如 `matches 5..10` |
| if\|unless data block\|entity\|storage \<路徑\>           | 判斷 NBT 路徑是否存在                |
| if\|unless predicate \<predicate\>                        | 資料包 predicate 判定                |
| if\|unless biome \<pos\> \<biome\>                        | 判斷生態域                           |
| if\|unless dimension \<維度\>                             | 判斷目前維度                         |
| if\|unless loaded \<pos\>                                 | 判斷區塊是否已載入                   |
| if\|unless items block\|entity \<來源\> \<slot\> \<item\> | 判斷容器／欄位中的物品               |
| if\|unless function \<function\>                          | 依函式回傳值判斷                     |

### 結果儲存 store

| 子指令                                                                  | 說明                                              |
|-------------------------------------------------------------------------|---------------------------------------------------|
| store result\|success score \<target\> \<目標\>                         | 把回傳值存進記分板                                |
| store result\|success block\|entity\|storage \<路徑\> \<型別\> \<倍率\> | 存進 NBT，型別如 `int`、`float`、`double`、`byte` |
| store result\|success bossbar \<id\> value\|max                         | 存進 Boss 血條                                    |

`result` 存指令的實際回傳數值（例如偵測到幾個實體）；`success` 存成功與否（0 或 1）。

> 🆕 **26.3 要重測的地方：**`/gamerule` 在設定值與現值相同時不再回報成功。所以 `execute store success ... run gamerule <規則> <值>` 這種「順便偵測目前設定」的寫法，行為跟 26.2 不一樣了。要讀取現值請改用 `/gamerule <規則>` 不帶值的查詢形式。

    # 讓每個玩家在自己腳下放一塊金磚
    /execute as @a at @s run setblock ~ ~-1 ~ gold_block

    # 只有站在紅石塊上的玩家才會被傳送
    /execute as @a at @s if block ~ ~-1 ~ redstone_block run tp @s 0 100 0

    # 在玩家視線前方 5 格產生粒子
    /execute as @a at @s anchored eyes run particle flame ^ ^ ^5

    # 把玩家 Y 座標存成分數（乘 100 保留小數）
    /execute as @a store result score @s posY run data get entity @s Pos[1] 100

    # 跨維度：在地獄的相同座標放置方塊
    /execute in the_nether positioned ~ ~ ~ run setblock ~ ~ ~ glowstone

    # 統計某區域內的殭屍數量並顯示在 bossbar
    /execute store result bossbar mob_count value run execute if entity @e[type=zombie,distance=..50]

    # 對攻擊者反擊（on 子指令）
    /execute as @e[type=villager] on attacker run damage @s 2 minecraft:magic

    # 只在斑駁森林裡生效（26.3 新生態域）
    /execute as @a at @s if biome ~ ~ ~ minecraft:dappled_forest run effect give @s regeneration 5 0 true

> ℹ️ **as 與 at 的差別是最常搞混的地方：**  
> `execute as @a run ...` — 執行者變成每位玩家，但位置還在原地。  
> `execute at @a run ...` — 位置變成每位玩家所在處，但執行者沒變。  
> 大多數情況要寫 `as @a at @s`，代表「以每個玩家的身分，在他自己的位置」。

<span id="s19"></span>

<a id="s19"></a>

## 19 · 資料包、函式與排程

| 指令                                                     | 說明                                        |
|----------------------------------------------------------|---------------------------------------------|
| /function \<命名空間:路徑\>                              | 執行 .mcfunction 檔，可帶參數 `{key:value}` |
| /return \<值\> / /return run \<指令\>                    | 從函式提前回傳                              |
| /datapack list \[available\|enabled\]                    | 列出資料包                                  |
| /datapack enable \<名稱\> \[first\|last\|before\|after\] | 啟用並指定優先順序                          |
| /datapack disable \<名稱\>                               | 停用資料包                                  |
| /reload                                                  | 重新載入所有資料包                          |
| /schedule function \<函式\> \<時間\> \[append\|replace\] | 延後執行，時間可用 `100t` / `5s` / `1d`     |
| /schedule clear \<函式\>                                 | 取消排程                                    |
| /data ... storage \<命名空間\>                           | 獨立於世界的資料儲存空間，適合當全域變數    |

#### 資料包目錄結構

    world/datapacks/我的資料包/
    ├── pack.mcmeta          ← 26.3 的 pack_format 是 121.0
    └── data/
        └── mypack/
            ├── function/          ← 1.21 起為單數，舊版是 functions/
            │   ├── tick.mcfunction
            │   └── load.mcfunction
            ├── advancement/
            ├── loot_table/
            ├── predicate/
            └── recipe/
    data/minecraft/tags/function/tick.json   ← 每 tick 執行
    data/minecraft/tags/function/load.json   ← 載入時執行

> ⚠️ **升級資料包的三道關卡：**  
> 1. **資料夾單數化**（1.21）：`functions`→`function`、`advancements`→`advancement`、`loot_tables`→`loot_table`。整包會直接失效。  
> 2. **gamerule 改名**（26.x）：資料包裡任何 `/gamerule doDaylightCycle` 之類的指令全部要改。  
> 3. **pack_format 與燃料標籤**（26.3）：`pack.mcmeta` 改成 `121.0`；`#brewing_fuel` 物品標籤**已被移除**，想註冊新的釀造燃料必須改用 `minecraft:brewing_fuel` 組件，熔爐燃料則用 `minecraft:cooking_fuel`。

> ℹ️ **26.3 的資料包新工具：**方塊 predicate 新增 `minecraft:height_range`（依高度範圍判定，用 Vertical Anchor 指定上下界），規則測試新增 `minecraft:not`（反轉另一個 rule test 的結果）。這兩個配合 `/execute if predicate` 可以少寫很多條件分支。

<span id="s20"></span>

<a id="s20"></a>

## 20 · 進度與配方

| 指令                                                         | 說明                                   |
|--------------------------------------------------------------|----------------------------------------|
| /advancement grant \<targets\> everything                    | 給予全部進度                           |
| /advancement grant \<targets\> only \<進度\> \[條件\]        | 只給單一進度                           |
| /advancement grant \<targets\> from\|through\|until \<進度\> | 給予該進度之後／前後全部／之前的進度樹 |
| /advancement revoke ...                                      | 撤銷進度（參數與 grant 相同）          |
| /recipe give\|take \<targets\> \<配方\|\*\>                  | 解鎖／收回配方                         |

<span id="s21"></span>

<a id="s21"></a>

## 21 · 技術與除錯指令

### tick 指令

對紅石與生電除錯極為重要，可以把世界「凍結」再一格一格前進，仔細觀察每個遊戲刻發生了什麼。

| 指令                    | 說明                                         |
|-------------------------|----------------------------------------------|
| /tick query             | 查詢目前 tick 速率與 MSPT                    |
| /tick freeze            | 凍結遊戲刻（實體、紅石全停，玩家仍可移動）   |
| /tick unfreeze          | 解除凍結                                     |
| /tick step \[幾刻\]     | 在凍結狀態下前進指定刻數，預設 1             |
| /tick step stop         | 中止正在進行的 step                          |
| /tick rate \<每秒刻數\> | 改變遊戲速度，預設 20.0（設 5.0 慢動作觀察） |
| /tick sprint \<刻數\>   | 用最快速度衝刺指定刻數，測試農場產能         |
| /tick sprint stop       | 停止衝刺                                     |

### 其他除錯

| 指令                          | 說明                                                 |
|-------------------------------|------------------------------------------------------|
| /debug start / stop           | 效能分析，結果寫入 `debug/` 資料夾                   |
| /debug function \<函式\>      | 追蹤函式的每一行執行結果                             |
| /perf start / stop            | 更詳細的伺服器取樣報告                               |
| /forceload query              | 檢查常載區塊（找出效能黑洞）                         |
| /gamerule random_tick_speed 0 | 暫停隨機刻，排除作物生長等干擾                       |
| /kill @e\[type=item\]         | 清除掉落物（緊急救卡頓手段）                         |
| F3 + G / F3 + B / F3 + H      | 區塊邊界 / 實體判定框 / 進階物品提示（客戶端快捷鍵） |

> 💡 **生電除錯流程：**  
> 1. `/tick freeze` 凍住世界 → 2. 觸發輸入訊號 → 3. `/tick step 1` 一刻一刻推進 → 4. 開 F3+G 看區塊邊界、F3+B 看實體判定框 → 5. 用 `/data get block ~ ~ ~` 讀取方塊實體的實際 NBT 狀態。  
> 比起憑感覺猜「是不是延遲差一刻」，這樣可以直接看到答案。  
> **基岩版玩家沒有 F3。**Geyser 提供 `/geyser tooltips` 切換進階物品提示，但區塊邊界與判定框無法顯示——要除錯還是得用 Java 客戶端連進來。

> ℹ️ **26.3 的冷知識：**新增除錯屬性 `ENABLE_FARLANDS`，會關閉 Beta 1.8 的 modulo 修正，讓遠境（Far Lands）與其他浮點精度錯誤重新出現。因為主世界還有其他機制會先崩壞，傳統形態的遠境只會在地獄與終界出現。Mojang 加這個純粹是為了**比較那個修正的效能成本**，不是給一般玩家用的。

<span id="s22"></span>

<a id="s22"></a>

## 22 · Paper 26.3 專屬指令與效能診斷

| 指令                         | 說明                                          |
|------------------------------|-----------------------------------------------|
| /plugins（/pl）              | 列出已安裝插件                                |
| /version（/ver）\[插件\]     | 查看核心或單一插件版本                        |
| /tps                         | 過去 1／5／15 分鐘的 TPS                      |
| /mspt                        | 每刻平均／最大耗時，比 TPS 更能看出瓶頸       |
| /spark profiler start / stop | Spark 效能分析（Paper 26.x 內建 spark-paper） |
| /spark tps / /spark health   | 即時效能與記憶體狀況                          |
| /spark heapsummary           | 記憶體物件統計，找記憶體洩漏用                |
| /paper reload                | 重載 paper-global.yml 設定                    |
| /paper entity list           | 統計各維度的實體數量與分布                    |
| /paper chunkinfo             | 顯示區塊載入統計                              |
| /paper dumpitem              | 輸出手持物品的完整資料                        |

> 🆕 **26.3 版的 Paper 動態：**  
> • JAR 檔案體積減少約 10MB，CI 建置與部署速度大幅加快。  
> • 大量原本標示為 experimental 的 API（包含多數 data component API）已移除實驗性註記，插件可以放心使用。  
> • **26.4 會做設定檔合併**：目前散落在 bukkit.yml、spigot.yml、paper 各檔的設定將整併到一起。如果你有自動化部署腳本在讀這些檔案，先有個心理準備。

> ⚠️ **不要用 `/reload confirm`。**它會嘗試重載所有插件，很容易造成記憶體洩漏與插件狀態錯亂——DiscordSRV 官方也明確說過只能用它自己的 `/discordsrv reload`。需要套用設定就重啟伺服器。

> 💡 **MSPT 比 TPS 更誠實。**TPS 只要沒滿載就一直顯示 20.0，看不出問題；MSPT（每刻毫秒數）低於 50ms 才算健康，超過 50ms 代表已經跟不上。診斷卡頓時先看 `/mspt`，再用 `/spark profiler` 找出是哪段程式碼吃掉時間。  
> **有 Geyser 的伺服器要特別注意：**Geyser 的封包轉譯本身會佔用資源，但它跑在自己的執行緒上，所以 spark 報告裡看到 Geyser 相關的耗時未必等於主執行緒卡頓。先確認瓶頸在主執行緒還是在轉譯層。

<div class="newpage">

<span id="s23"></span>

<a id="s23"></a>

## 23 · Geyser / Floodgate（基岩版互通）

Geyser 是把基岩版客戶端翻譯成 Java 版連線的橋接器；Floodgate 則讓這些基岩玩家能在 `online-mode=true` 的正版驗證伺服器上加入。兩者通常成對安裝。

> 🆕 **26.3 支援狀態：**Geyser 在 26.3 發布後有一段時間仍以 26.2 客戶端自居，那段期間要在 26.3 伺服器上跑 Geyser 必須加裝 ViaVersion 與 ViaBackwards。**自 2026 年 10 月 15 日起，Geyser 已正式將 Java 26.3 列入支援版本**，不再需要 Via 系列當中介。升級前還是建議用 `/geyser version` 確認你手上那份的實際版本。

### Geyser 指令與權限節點

| 指令                             | 權限節點                    | 說明                                              |
|----------------------------------|-----------------------------|---------------------------------------------------|
| /geyser                          | geyser.command              | 根指令，執行任何 Geyser 指令都需要這個權限        |
| /geyser help                     | geyser.command.help         | 顯示所有已註冊指令的說明                          |
| /geyser advancements             | geyser.command.advancements | 開啟 Java 版進度選單                              |
| /geyser statistics               | geyser.command.statistics   | 開啟 Java 版統計選單                              |
| /geyser dump                     | geyser.command.dump         | **回報 bug 時第一個要跑的指令**，輸出完整除錯資訊 |
| /geyser list                     | geyser.command.list         | 列出所有透過 Geyser 連線的玩家                    |
| /geyser offhand                  | geyser.command.offhand      | 把物品放到副手（基岩版沒有副手鍵）                |
| /geyser reload                   | geyser.command.reload       | 重載 Geyser 設定。**會把所有玩家踢出去**          |
| /geyser settings                 | geyser.command.settings     | 開啟設定選單，可調整世界相關選項                  |
| /geyser tooltips                 | geyser.command.tooltips     | 切換進階物品提示（等同 Java 的 F3+H）             |
| /geyser ping                     | geyser.command.ping         | 顯示玩家與 Geyser 之間的延遲                      |
| /geyser version                  | geyser.command.version      | 顯示版本並檢查更新                                |
| /geyser extensions               | geyser.command.extensions   | 列出已載入的擴充（有擴充時才註冊此指令）          |
| /geyser options                  | geyser.command.options      | 開啟「暫停畫面附加項」對話框                      |
| /geyser quickactions             | geyser.command.quickactions | 開啟「快速動作」對話框                            |
| /geyser shutdown（/geyser stop） | geyser.command.shutdown     | 關閉 Geyser。**僅 Standalone 模式可用**           |

#### 非指令類權限

| 權限                      | 作用                                          |
|---------------------------|-----------------------------------------------|
| geyser.settings.server    | 允許玩家使用遊戲設定選單（同時仍需要 OP）     |
| geyser.settings.gamerules | 允許在設定選單中修改遊戲規則（同時仍需要 OP） |
| geyser.update             | 加入時是否收到 Geyser 更新通知                |

### Floodgate 指令

| 指令                             | 權限節點                        | 說明                                     |
|----------------------------------|---------------------------------|------------------------------------------|
| /fwhitelist add\|remove \<玩家\> | floodgate.command.fwhitelist    | **基岩版玩家專用的白名單指令**           |
| /linkaccount                     | floodgate.command.linkaccount   | 本地帳號連結（把基岩帳號綁到 Java 帳號） |
| /unlinkaccount                   | floodgate.command.unlinkaccount | 解除本地帳號連結                         |
| /floodgate version               | —                               | 顯示 Floodgate 版本並檢查更新            |

### 實務注意事項

| 狀況                  | 處理方式                                                                                                        |
|-----------------------|-----------------------------------------------------------------------------------------------------------------|
| 基岩玩家加不進白名單  | 用 `/fwhitelist add`，不要用 `/whitelist add`；輸入名稱時**不要加** Floodgate 設定的前綴（通常是 `.`）          |
| 名稱仍然抓不到        | 改用 floodgateUUID 加入白名單。格式為 `00000000-0000-0000-xxxx-xxxxxxxxxxxx`，把 x 換成該玩家 XUID 的十六進位值 |
| Java 玩家             | 照舊用 `/whitelist add`                                                                                         |
| 紅石／指令／農場行為  | 完全與 Java 版一致。Geyser 只模擬客戶端，**不改變伺服器行為**，所以生電機器不受影響                             |
| 26.3 新內容的顯示     | 白楊木、坐墊、稻草床等新方塊需要 Geyser 支援 26.3 的版本才會正確顯示；版本不符時基岩玩家可能看到錯誤的方塊外觀  |
| 權限套用在 proxy 架構 | 用 BungeeCord／Velocity 時，權限必須在 **proxy 端**用 LuckPerms 之類的插件設定，設在後端伺服器無效              |
| 離線模式驗證插件      | Geyser **不支援**離線模式使用。Floodgate 會修改登入流程，可能與部分插件衝突                                     |
| 版本檢查              | Geyser 與 Floodgate 的檔名不含版本號，只能靠 `/geyser version`、`/floodgate version` 查                         |

<span id="s24"></span>

<a id="s24"></a>

## 24 · DiscordSRV（Discord 橋接）

DiscordSRV 把 Minecraft 聊天與 Discord 頻道雙向串接，並提供遠端主控台功能。主指令是 `/discord`，別名 `/discordsrv`，所有功能都是它的子指令。

### 玩家指令

| 指令            | 權限               | 說明                                         |
|-----------------|--------------------|----------------------------------------------|
| /discord        | discordsrv.discord | 顯示設定好的 Discord 邀請連結與歡迎訊息      |
| /discord help   | discordsrv.help    | 列出你有權限使用的指令                       |
| /discord link   | discordsrv.link    | 產生 4 位數連結碼，到 Discord 輸入以綁定帳號 |
| /discord linked | discordsrv.linked  | 查詢自己的帳號綁定狀態                       |
| /discord unlink | discordsrv.unlink  | 解除自己的綁定                               |

### 管理指令

| 指令                                              | 權限                     | 說明                                                                              |
|---------------------------------------------------|--------------------------|-----------------------------------------------------------------------------------|
| /discord link \<MC玩家\> \<Discord用戶\>          | discordsrv.link.others   | 管理員直接綁定兩個帳號。MC 端可用名稱或 UUID，Discord 端可用 ID、用戶名或顯示名稱 |
| /discord linked \<目標\>                          | discordsrv.linked.others | 查詢他人的綁定狀態                                                                |
| /discord unlink \<目標\>                          | discordsrv.unlink.others | 解除他人的綁定                                                                    |
| /discord reload                                   | discordsrv.reload        | 重載設定檔。**只能用這個，不要用伺服器的 /reload**                                |
| /discord broadcast \<訊息\>                       | discordsrv.bcast         | 發送訊息到設定好的 Discord 主頻道                                                 |
| /discord resync                                   | discordsrv.resync        | 強制重新同步所有玩家群組與 Discord 身分組                                         |
| /discord debug                                    | discordsrv.debug         | 產生除錯報告並上傳到 paste 服務                                                   |
| /discord debugger start\|stop\|upload \[類別...\] | discordsrv.debug         | 即時除錯記錄，可指定類別聚焦特定模組                                              |
| /discord language \<語言代碼\>                    | discordsrv.language      | 切換插件語言                                                                      |

### 權限架構

| 權限節點                         | 預設  | 說明                           |
|----------------------------------|-------|--------------------------------|
| discordsrv.player                | true  | **父權限**，包含所有玩家功能   |
| discordsrv.admin                 | op    | **父權限**，包含所有管理功能   |
| discordsrv.chat                  | true  | 此玩家的聊天是否轉發到 Discord |
| discordsrv.nicknamesync          | true  | 暱稱同步                       |
| discordsrv.updatenotification    | op    | 加入時收到更新通知             |
| discordsrv.groupsyncwithcommands | op    | 透過權限指令觸發群組同步       |
| discordsrv.silentjoin            | false | 不廣播此玩家的加入訊息         |
| discordsrv.silentquit            | false | 不廣播此玩家的離開訊息         |
| discordsrv.sync.\<群組\>         | —     | 群組↔身分組同步的對應權限      |

> ⚠️ **主控台頻道的安全性。**DiscordSRV 可以指定一個 Discord 文字頻道當遠端主控台，該頻道的訊息會**以伺服器主控台權限直接執行**。這等於把 `/op`、`/stop` 的權力交給任何能在那個頻道發言的人。  
> 務必把發言權限限縮到你本人或最高信任的身分組。善用 Discord 權限可以做出「可讀不可寫」的唯讀主控台給其他管理看。

> ℹ️ **常見設定項（config.yml）：**  
> `DiscordChatChannelAllowedCommands` — 允許從 Discord 執行的指令白名單，預設只有 `say`、`me`。  
> `RequireLinkedAccount` — 是否強制玩家綁定帳號才能加入。  
> `DiscordToMinecraftChatMessageFormat` / `MinecraftChatToDiscordMessageFormat` — 雙向訊息格式。  
> 多台伺服器要共用綁定資料時可以接 MySQL（`Experiment_Jdbc` 相關選項）。  
> 設定 Bot 時記得在 Discord Developer Portal 開啟 **SERVER MEMBERS INTENT** 與 **MESSAGE CONTENT INTENT**，這兩個沒開會有一堆莫名其妙的問題。

> 💡 **三個插件的權限是同一套。**Geyser、Floodgate、DiscordSRV 的權限節點都走 Bukkit 權限系統，建議統一用 LuckPerms 管理，不要混用原版 OP 與插件權限。  
> 一個常見組合：把 `geyser.command.dump`、`discordsrv.debug`、`discordsrv.reload` 這類指令收進一個 `staff` 群組，一般玩家只保留 `discordsrv.player` 與 `geyser.command.help`。

<div class="newpage">

<span id="s25"></span>

<a id="s25"></a>

## 25 · 這台伺服器的架構

以下章節是針對 **Minecraft Server Management System** 這套自建工具所搭出來的伺服器寫的。前面的章節是通用的原版指令參考，從這裡開始是這台機器的實際操作。

| 層         | 內容                                                                                                                    |
|------------|-------------------------------------------------------------------------------------------------------------------------|
| 主機       | 家用 Windows 10 / 11，需要系統管理員權限（防火牆規則）                                                                  |
| 執行環境   | **Java 25 以上**（26.x 全系列的硬性需求）                                                                               |
| 伺服器核心 | Paper                                                                                                                   |
| 對外       | playit 隧道（TCP 25565 / UDP 19132），繞過 CGNAT，不動路由器                                                            |
| 外掛       | Geyser、Floodgate、BlueMap、DeluxeMenus、PlaceholderAPI、LuckPerms、WorldEdit、WorldGuard、DiscordSRV、PanelKey（自製） |
| 管理介面   | 內網控制台網頁、Discord 機器人、桌面控制台、RCON                                                                        |
| 自動化     | 看門狗（5 分鐘）、每日備份（保留 7 份）、排程重啟、地圖發布                                                             |

### 三個連接埠不要搞混

| 埠          | 用途                          | 對外                                                      |
|-------------|-------------------------------|-----------------------------------------------------------|
| 25565 / TCP | Minecraft Java 版             | 走 playit 隧道                                            |
| 19132 / UDP | Minecraft 基岩版（Geyser）    | 走 playit 隧道，公開埠通常**不是** 19132                  |
| 8099 / TCP  | 內網控制台                    | **絕對不要對外**                                          |
| 8100 / TCP  | BlueMap 內建網頁伺服器        | 用 sync-map.ps1 推靜態輸出到 Cloudflare Pages，不直接曝露 |
| RCON 埠     | 控制台與 Discord bot 下指令用 | 僅本機                                                    |

> ⚠️ **控制台的埠永遠不要開隧道。**playit 這類穿透工具的 agent 是從 `127.0.0.1` 連進本機服務的，會**通過內網位址檢查**——等於把能關伺服器、能執行任意主控台指令的管理頁面直接送上公網，只剩控制權杖擋著。這條規則沒有例外。

<span id="s26"></span>

<a id="s26"></a>

## 26 · 日常操作：管理介面

### 內網控制台（`http://localhost:8099`）

在同一個區網的任何裝置都能開，手機躺在沙發上也看得到。

| 功能        | 說明                                                             |
|-------------|------------------------------------------------------------------|
| 狀態磚      | 伺服器是否在跑、線上人數、資源狀況。**純看狀態不需要權杖**       |
| 啟動 / 停止 | 需要控制權杖                                                     |
| 備份        | 手動觸發一次完整備份流程                                         |
| RCON        | 直接下主控台指令，等同在伺服器視窗打字                           |
| 日誌        | 即時查看 latest.log                                              |
| 遊戲規則    | 圖形化改 gamerule（**26.x 的 snake_case 名稱**，見前面的對照表） |
| 記憶體配置  | 調整 JVM 的 -Xmx / -Xms                                          |

#### 三層防護

| 層           | 作用                                                                                                                                                                                 |
|--------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| 內網位址檢查 | 明確列舉 `127/8`、`10/8`、`172.16/12`、`192.168/16`、`169.254/16`、`::1`、`fc00::/7`、`fe80::/10`。刻意不用 `ipaddress.is_private`，因為它把 `203.0.113.0/24` 這類文件網段也算成私有 |
| 控制權杖     | 只有會改變狀態的動作需要                                                                                                                                                             |
| 防火牆規則   | 限定 LocalSubnet                                                                                                                                                                     |

所有會改變狀態的動作都會記進 `web-console.log`，含來源 IP。伺服器出了怪事先翻這個檔。

### Discord 機器人

| 指令           | 說明                                  |
|----------------|---------------------------------------|
| /status        | 伺服器狀態與線上玩家                  |
| /start         | 啟動伺服器                            |
| /stop          | 關閉伺服器                            |
| /rcon \<指令\> | 透過 RCON 執行主控台指令              |
| /ip            | 顯示目前的連線位址（playit 隧道位址） |
| /render        | 觸發 BlueMap 重新渲染                 |

> ⚠️ `/rcon` 等於主控台權限。它跟 DiscordSRV 的主控台頻道是**兩條各自獨立的通道**，兩邊的 Discord 權限都要鎖。只要有一邊漏掉，`/op` 和 `/stop` 就等於公開。

### 健康檢查

    python scripts/check-server.py

六層檢查：**本機 → DNS → 隧道 → 外部視角 → 網頁地圖**。判斷「朋友到底連不連得進來」只看**外部視角那一層**，其他層通過都不算數。

> 💡 **playit 後台顯示「線上」不代表真的通。**那只反映 agent 有沒有連上 playit 的服務，不保證流量到得了你的機器。真正的判斷依據是 agent 日誌（`C:\ProgramData\playit_gg\logs\playitd.log`）和這支腳本的外部視角那一層。  
> 遇到後台一切正常但就是連不進來時，**刪掉 agent 和隧道重新建立**往往是唯一有效的解法。  
> 最後一步永遠是叫朋友實際連連看——外部檢測通過不等於玩家真的進得來。

### 排程重啟

    pythonw scripts/restart-sequence.py

重啟前 5／3／1 分鐘各廣播一次，最後 30 秒倒數。手動想做同樣的事就是：

    # 等效的手動版本
    /say 伺服器將於 5 分鐘後重啟
    /title @a actionbar {"text":"5 分鐘後重啟","color":"yellow"}
    # ... 倒數 ...
    /save-all flush
    /stop

<span id="s27"></span>

<a id="s27"></a>

## 27 · 排程工作、備份與還原

### Windows 工作排程器

| 工作        | 觸發              | 執行                                                  |
|-------------|-------------------|-------------------------------------------------------|
| 世界備份    | 每天 04:00        | powershell -WindowStyle Hidden -File backup-world.ps1 |
| 看門狗      | 每 5 分鐘         | powershell -WindowStyle Hidden -File watchdog.ps1     |
| 排程重啟    | 重啟時間前 5 分鐘 | pythonw restart-sequence.py                           |
| Discord bot | 登入時            | pythonw discord-control.py                            |
| 內網控制台  | 登入時            | pythonw web-console.py                                |

> ℹ️ 用 `pythonw` 和 `-WindowStyle Hidden` 不是為了好看：不加的話每次觸發都會彈一個主控台視窗，看門狗每 5 分鐘一次，玩遊戲會一直被打斷。  
> 長時間執行的工作記得把「**執行時間上限**」設成無限，預設 3 天會被排程器砍掉。

### 備份流程

`backup-world.ps1` 做的事，順序不能換：

| 步驟               | 對應指令                  |
|--------------------|---------------------------|
| 1\. 暫停自動存檔   | save-off                  |
| 2\. 強制落盤       | save-all flush            |
| 3\. 複製世界資料夾 | 檔案層級複製              |
| 4\. 壓縮           | 打包成壓縮檔              |
| 5\. 恢復自動存檔   | save-on                   |
| 6\. 輪替           | 保留最近 7 份，刪掉更舊的 |

> ⚠️ 少了步驟 1 就直接複製，很容易抓到寫到一半的區塊檔，還原時才會發現存檔損壞。  
> **26.x 之後備份的重要性再升一級：世界一旦升版就無法降回去。**升級 Paper 版本之前，先手動跑一次備份並確認壓縮檔真的產出來了，不要只相信排程。

### 還原

1.  控制台或 Discord 下 `/stop`，確認程序真的結束
2.  **先把看門狗的排程工作停掉**——否則你還在解壓縮，它已經把伺服器拉起來了，直接寫壞你正在還原的世界
3.  把現有世界資料夾改名（不要刪，萬一還原的那份也有問題）
4.  解壓縮備份到原位
5.  啟動，進遊戲確認沒問題
6.  重新啟用看門狗

<span id="s28"></span>

<a id="s28"></a>

## 28 · LuckPerms（權限）

這台伺服器有三套權限系統並存：**原版 OP 等級**（0–4）、**Bukkit 權限節點**（所有外掛走這套）、以及 **Discord 身分組**。LuckPerms 管的是中間那套，也是實際決定誰能用什麼指令的那套。

| 指令                                                  | 說明                                                                             |
|-------------------------------------------------------|----------------------------------------------------------------------------------|
| /lp editor                                            | **最好用的功能**：產生一個一次性網址，在瀏覽器裡拖拉設定權限，存檔後貼回指令套用 |
| /lp user \<玩家\> info                                | 查看某人的群組與權限                                                             |
| /lp user \<玩家\> parent add \<群組\>                 | 把玩家加進群組                                                                   |
| /lp user \<玩家\> parent remove \<群組\>              | 移出群組                                                                         |
| /lp user \<玩家\> permission set \<節點\> true\|false | 單獨給／擋一個權限                                                               |
| /lp user \<玩家\> permission info                     | 列出該玩家所有權限來源                                                           |
| /lp group \<群組\> permission set \<節點\> true       | 群組層級給權限                                                                   |
| /lp creategroup \<群組\>                              | 建立群組                                                                         |
| /lp group \<群組\> meta setprefix \<權重\> "\<前綴\>" | 設定聊天前綴（需 Vault 或聊天外掛支援）                                          |
| /lp group \<群組\> parent add \<父群組\>              | 群組繼承                                                                         |
| /lp verbose on / off                                  | **除錯神器**：即時顯示伺服器正在檢查哪些權限節點                                 |
| /lp verbose record / paste                            | 錄一段權限檢查並上傳成網頁報告                                                   |
| /lp tree \<節點前綴\>                                 | 列出某個命名空間底下所有已註冊的權限                                             |
| /lp sync                                              | 重新同步（多台共用資料庫時用）                                                   |

> 💡 **「某個指令他明明應該有權限卻不能用」的標準解法：**  
> `/lp verbose on` → 叫他執行那個指令 → `/lp verbose off`。伺服器會把實際檢查的節點名稱印出來，通常你會發現節點名稱跟文件寫的不一樣，或是被某個 `false` 擋掉了。這比猜快十倍。

### 這台伺服器的建議群組設計

<table class="r">
<colgroup>
<col style="width: 33%" />
<col style="width: 33%" />
<col style="width: 33%" />
</colgroup>
<thead>
<tr class="header">
<th>群組</th>
<th>給什麼</th>
<th>說明</th>
</tr>
</thead>
<tbody>
<tr class="odd">
<td class="c">default</td>
<td class="c">discordsrv.player<br />
geyser.command.help<br />
geyser.command.offhand<br />
geyser.command.ping<br />
geyser.command.list</td>
<td>一般玩家。<code>offhand</code> 對基岩玩家是必要的，因為他們沒有副手鍵</td>
</tr>
<tr class="even">
<td class="c">trusted</td>
<td>繼承 default<br />
+ PanelKey 的一般功能</td>
<td>熟人，可以用遊戲內選單但不能改世界</td>
</tr>
<tr class="odd">
<td class="c">staff</td>
<td>繼承 trusted<br />
+ worldedit.*<br />
+ worldguard.region.*<br />
+ bluemap.*<br />
+ geyser.command.dump<br />
+ discordsrv.debug</td>
<td>幫忙管理的人。<strong>注意 worldedit.* 等於給了改寫世界的能力</strong></td>
</tr>
<tr class="even">
<td class="c">admin</td>
<td>繼承 staff<br />
+ discordsrv.admin<br />
+ geyser.command.reload<br />
+ 原版 OP 4</td>
<td>只給你自己</td>
</tr>
</tbody>
</table>

> ⚠️ **基岩玩家的名稱有前綴。**Floodgate 預設會在基岩玩家名稱前面加一個 `.`。用 `/lp user` 指定他們時要**連前綴一起打**，或是直接用 UUID——否則 LuckPerms 會找不到人，而且錯誤訊息不會告訴你是前綴的問題。

<span id="s29"></span>

<a id="s29"></a>

## 29 · WorldEdit（建築與修補）

> ⚠️ **26.3 相容性：**WorldEdit 的 stable 7.4.5 只宣告到 **26.2**，26.3 支援在 7.4.6 的 beta 版本（Modrinth 上的專案頁近期已列出 26.3，所以 7.4.6 可能已轉正式——下載前確認 channel）。  
> 這點會連帶影響 WorldGuard：**WorldGuard 沒有 WorldEdit 根本起不來**。安裝程式如果抓「最新 stable」，在 26.3 上會拿到不相容的 7.4.5，然後 WorldGuard 啟動失敗。

| 指令                                | 說明                                           |
|-------------------------------------|------------------------------------------------|
| //wand                              | 拿到選取工具（木斧）。左鍵點 pos1、右鍵點 pos2 |
| //pos1 / //pos2                     | 用目前站的位置設定選取點                       |
| //hpos1 / //hpos2                   | 用視線指向的方塊設定選取點（遠距離好用）       |
| //sel cuboid\|extend\|poly\|sphere  | 切換選取模式                                   |
| //expand \<數量\> \[方向\]          | 擴大選取區，`//expand vert` 直接擴到天地       |
| //contract \<數量\> \[方向\]        | 縮小選取區                                     |
| //size                              | 顯示選取區大小與方塊數                         |
| //set \<方塊\>                      | 填滿選取區                                     |
| //replace \<舊\> \<新\>             | 取代指定方塊                                   |
| //walls \<方塊\>                    | 只建四面牆                                     |
| //outline \<方塊\>                  | 建外殼（含上下）                               |
| //copy / //cut / //paste            | 複製／剪下／貼上，`//paste -a` 忽略空氣        |
| //stack \<次數\> \[方向\]           | 沿方向重複堆疊選取區                           |
| //move \<距離\> \[方向\]            | 整塊移動                                       |
| //rotate \<角度\> / //flip \[方向\] | 旋轉／鏡射剪貼簿                               |
| //undo / //redo                     | 復原／重做（**每個玩家各自的歷史**）           |
| //schem save \<名稱\>               | 把剪貼簿存成 schematic                         |
| //schem load \<名稱\>               | 載入 schematic 到剪貼簿                        |
| //schem list                        | 列出所有 schematic                             |
| //brush sphere \<方塊\> \<半徑\>    | 球形筆刷                                       |
| //none                              | 解除筆刷                                       |
| //drain \<半徑\>                    | 抽乾水／岩漿                                   |
| //limit \<數量\>                    | 設定單次操作的方塊上限                         |
| /toggleeditwand                     | 暫時把木斧切回普通斧頭                         |

> ⚠️ **WorldEdit 的 `//set` 不寫入容器內容物。**這是做生電機器時最容易中招的地方：用 `//paste` 放一台全物品分類器，過濾漏斗會**全部是空的**，機器不動而且完全不報錯。  
> 要保留容器內容請走結構方塊，或用 repo 裡的 `litematic2structure.py` 轉換。

<span id="s30"></span>

<a id="s30"></a>

## 30 · WorldGuard（區域保護）

> ℹ️ **版本需求：**WorldGuard 7.0.19 支援 26.2 與 26.3，但**要求 26.2 以上**。如果哪天要退回 26.1.x，WorldGuard 也要降到 7.0.18。

| 指令                                          | 說明                                                 |
|-----------------------------------------------|------------------------------------------------------|
| //wand → /rg define \<區域名\>                | 用 WorldEdit 選區，再定義成保護區                    |
| /rg define \<名稱\> \[擁有者...\]             | 建立區域                                             |
| /rg redefine \<名稱\>                         | 用目前選取區重新劃定範圍（保留旗標與成員）           |
| /rg remove \<名稱\>                           | 刪除區域                                             |
| /rg list                                      | 列出所有區域                                         |
| /rg info \[名稱\]                             | 查看區域的旗標、成員、優先權。不帶名稱就查你站的位置 |
| /rg addowner \<名稱\> \<玩家\>                | 加擁有者                                             |
| /rg addmember \<名稱\> \<玩家\>               | 加成員                                               |
| /rg addmember \<名稱\> g:\<群組\>             | 加整個 LuckPerms 群組（`g:` 前綴）                   |
| /rg removemember \<名稱\> \<玩家\>            | 移除成員                                             |
| /rg flag \<名稱\> \<旗標\> \<值\>             | 設定旗標                                             |
| /rg flag \<名稱\> \<旗標\> -g \<群體\> \<值\> | 只對某類人生效（`members`、`nonmembers`、`all`）     |
| /rg setpriority \<名稱\> \<數字\>             | 區域重疊時數字大的贏                                 |
| /rg select \<名稱\>                           | 把某區域載入成 WorldEdit 選取區                      |

#### 常用旗標

| 旗標                      | 作用                             |
|---------------------------|----------------------------------|
| build                     | 能否建造與破壞（最常用的總開關） |
| pvp                       | 區域內的玩家互傷                 |
| chest-access              | 能否開容器                       |
| use                       | 能否使用按鈕、拉桿、門           |
| interact                  | 更廣義的互動                     |
| mob-spawning              | 區域內是否生怪                   |
| creeper-explosion / tnt   | 爆炸是否破壞方塊                 |
| entry / exit              | 能否進入／離開                   |
| greeting / farewell       | 進出時顯示的訊息                 |
| block-break / block-place | 比 build 更細的控制              |

> 💡 **`__global__` 是整個世界的預設區域。**想做「全世界禁止生怪，只有特定區域可以」這種設定，就是 `/rg flag __global__ mob-spawning deny`，再在農場區域單獨 `allow` 並把優先權調高。  
> **但生電農場要小心：**WorldGuard 的 `mob-spawning deny` 會直接讓刷怪塔停擺。遇到「農場突然不出貨」先檢查有沒有不小心套到全域旗標。

<span id="s31"></span>

<a id="s31"></a>

## 31 · BlueMap（3D 網頁地圖）

> ℹ️ **26.3 相容性：**BlueMap 自 5.24 起支援 26.3 世界，5.28 也是。目標 Java 版本是 25，跟伺服器一致。

| 指令                       | 說明                                  |
|----------------------------|---------------------------------------|
| /bluemap                   | 顯示目前狀態與渲染進度                |
| /bluemap reload            | 重載設定                              |
| /bluemap update \[地圖\]   | 觸發重新渲染                          |
| /bluemap freeze \<地圖\>   | 凍結該地圖的更新（效能吃緊時用）      |
| /bluemap unfreeze \<地圖\> | 解除凍結                              |
| /bluemap purge \<地圖\>    | 清掉已渲染的資料，下次從頭來          |
| /bluemap marker ...        | 管理地圖上的標記                      |
| /bluemap debug block       | 查看你指向的方塊在 BlueMap 眼中的狀態 |

> 💡 **首次渲染非常吃資源。**一個玩了一陣子的世界第一次跑完整渲染可能要數小時，期間 MSPT 會明顯上升。建議挑沒人在線的時段跑，或先 `/bluemap freeze` 再分次 unfreeze。  
> Discord bot 的 `/render` 就是在觸發這件事——不要在尖峰時間按。

`windows/sync-map.ps1` 把 BlueMap 的靜態輸出推到 Cloudflare Pages，所以玩家看地圖不會連到你家機器，也不用把 8100 埠曝露出去。

<span id="s32"></span>

<a id="s32"></a>

## 32 · DeluxeMenus 與 PlaceholderAPI

這台伺服器裝了四份管理選單（`bundled/deluxemenus/`），安裝程式會一併註冊。

| 指令                           | 說明                                       |
|--------------------------------|--------------------------------------------|
| /dm open \<選單名\>            | 開啟指定選單                               |
| /dm open \<選單名\> \<玩家\>   | 幫別人開（需額外權限）                     |
| /dm list                       | 列出所有已載入的選單                       |
| /dm reload                     | 重載選單設定                               |
| /dm dump                       | 輸出除錯資訊                               |
| /papi reload                   | 重載 PlaceholderAPI                        |
| /papi list                     | 列出已載入的擴充                           |
| /papi ecloud list              | 列出雲端可下載的擴充                       |
| /papi ecloud download \<擴充\> | 下載擴充（下載完要 `/papi reload`）        |
| /papi parse me %player_name%   | **測試佔位符**：看某個變數實際會展開成什麼 |

> 💡 **選單裡的變數不會展開時，先用 `/papi parse me` 單獨測那個佔位符。**九成是對應的 expansion 沒裝——PlaceholderAPI 本身只提供框架，每個外掛的變數要各自 `ecloud download`。

<span id="s33"></span>

<a id="s33"></a>

## 33 · PanelKey（自製外掛）

內建在 `bundled/`，含原始碼，安裝程式會一併裝上。

| 功能         | 說明                 |
|--------------|----------------------|
| /menu        | 開啟遊戲內管理面板   |
| /spawn       | 回到出生點           |
| 行動工作台   | 隨身開啟工作台       |
| 指定給予對象 | 給予物品時指定接收者 |

> ℹ️ **這一節需要你補完。**完整的指令清單、權限節點與依賴寫在 `bundled/README.md`，我沒辦法直接讀到那份檔案的內容。把它貼給我，我可以把這張表補成跟其他章節一樣的完整格式（指令 / 權限節點 / 說明三欄）。

> ⚠️ **升級 Paper 版本前要重新驗證 PanelKey。**26.x 有兩個變動可能影響自製外掛：  
> • **26.2**：床不再是 block entity，失去存放 PersistentDataContainer 的能力。  
> • **26.3**：大量原本標示 experimental 的 API（包含多數 data component API）移除了實驗性註記——好消息是可以放心用，但如果你原本有針對 experimental 做過相容處理，那些程式碼可能要清掉。  
> 升版前先在測試世界跑一次，不要直接上主服。

<span id="s34"></span>

<a id="s34"></a>

## 34 · 升級到新版 Paper 的完整流程

這是把前面所有注意事項串起來的實際步驟。

| 步驟 | 做什麼                                                                        |
|------|-------------------------------------------------------------------------------|
| 1    | **手動跑一次備份**，並打開壓縮檔確認內容真的在。不要只相信排程                |
| 2    | 停掉看門狗的排程工作，否則升級過程中它會把舊版拉起來                          |
| 3    | 確認 **Java 版本**符合目標版本（26.x 需要 Java 25）                           |
| 4    | 逐一確認外掛支援目標版本，特別是 **WorldEdit → WorldGuard** 這條依賴鏈        |
| 5    | 確認 **Geyser** 支援目標版本，否則基岩玩家進不來                              |
| 6    | 重新建置並測試 **PanelKey**                                                   |
| 7    | 檢查資料包的 `pack_format` 與資料夾結構                                       |
| 8    | 換 Paper JAR，**在測試世界先開一次**                                          |
| 9    | 開主服，檢查 `server.properties` 的 **white-list**（26.3 全新安裝預設是開的） |
| 10   | 跑 `check-server.py`，確認外部視角通過                                        |
| 11   | 叫一位 Java 玩家與一位基岩玩家各自實際連一次                                  |
| 12   | 重新啟用看門狗                                                                |

> ⚠️ **世界一旦升版就無法降回去。**這不是「盡量備份」的等級，是「沒備份就等於賭上整個世界」。步驟 1 沒做完不要往下走。

<span id="s35"></span>

<a id="s35"></a>

## 35 · 這台伺服器的疑難排解

| 症狀                                            | 先檢查什麼                                                                                                                 |
|-------------------------------------------------|----------------------------------------------------------------------------------------------------------------------------|
| 朋友連不進來，但後台顯示 playit 線上            | 後台的「線上」只代表 agent 連上服務。看 `playitd.log` 和 `check-server.py` 的外部視角層。刪掉 agent 和隧道重建往往是唯一解 |
| 玩家拿到 `Connection timed out: getsockopt`     | DNS 建了 AAAA 記錄。playit 會公告 IPv6 但不路由 IPv6，整條 DNS 鏈路只能用 IPv4                                             |
| Cloudflare 設好了但連不進                       | Proxy 要關（**灰雲**）。橘雲是 HTTP 代理，Minecraft 協定過不去                                                             |
| 全新裝好的 26.3 伺服器所有人都進不來            | **白名單預設是開的。**`/whitelist off` 或把玩家加進去。基岩玩家要用 `/fwhitelist add`                                      |
| 伺服器起不來、沒有明確錯誤                      | Java 版本（26.x 需要 25）；或工作目錄落在受保護資料夾內                                                                    |
| 程式無聲死掉或卡住                              | **受控資料夾存取**會無聲擋掉寫入。Windows Defender 預設保護 Documents、Pictures、Desktop。把東西移出去就好，不需要關掉防護 |
| WorldGuard 啟動失敗                             | WorldEdit 版本不相容或沒裝。WorldGuard 沒有 WorldEdit 不會啟動                                                             |
| 農場突然不出貨                                  | WorldGuard 的 `mob-spawning deny` 套到了 `__global__`；或 `spawn_mobs` 被關掉                                              |
| 貼上的機器不會動、漏斗是空的                    | WorldEdit 的 `//set` / `//paste` 不寫入容器內容。改走結構方塊                                                              |
| 改了磁碟上的 .nbt 但結構沒變                    | 伺服器把結構模板**快取在記憶體**。換檔名或重啟才會生效                                                                     |
| 基岩玩家加不進白名單                            | 用 `/fwhitelist`；名稱不要加 Floodgate 前綴；必要時改用 floodgateUUID                                                      |
| LuckPerms 找不到基岩玩家                        | 反過來，`/lp user` 要**連前綴一起打**，或用 UUID                                                                           |
| 某人應該有權限卻不能用指令                      | `/lp verbose on` → 叫他執行 → `/lp verbose off`，看實際檢查的節點名稱                                                      |
| DeluxeMenus 的變數沒展開                        | `/papi parse me <佔位符>` 單獨測。多半是 expansion 沒 `ecloud download`                                                    |
| 排程工作跑一跑就沒了                            | 「執行時間上限」預設 3 天會被排程器砍掉，長駐工作要設成無限                                                                |
| 每 5 分鐘彈一個黑視窗                           | 看門狗沒用 `-WindowStyle Hidden`；或 subprocess 沒帶 `CREATE_NO_WINDOW`                                                    |
| PowerShell 報 MissingEndCurlyBrace 但那行是對的 | 含中文的 `.ps1` 必須存成 **UTF-8 with BOM**。沒 BOM 會被當 ANSI 讀，中文字第二個位元組吃掉大括號                           |
| 批次檔完全沒被執行且無聲                        | `.bat` 必須純 ASCII 且 CRLF 換行；`Start-Process -ArgumentList` 不會替含空白的元素加引號，要自己寫成 `'"MC Server"'`       |

<span id="s36"></span>

<a id="s36"></a>

## 36 · server.properties 重點設定

| 設定項                            | 預設    | 說明                                                                                   |
|-----------------------------------|---------|----------------------------------------------------------------------------------------|
| server-port                       | 25565   | Java 版連接埠。**Geyser 的基岩連接埠（預設 19132）另外在 Geyser 設定檔指定**           |
| max-players                       | 20      | 最大同時上線人數（Java + 基岩合計）                                                    |
| online-mode                       | true    | 正版驗證。**有 Floodgate 時應維持 true**，基岩玩家由 Floodgate 處理驗證                |
| white-list                        | false   | 白名單開關                                                                             |
| enforce-whitelist                 | false   | 白名單變更時立即踢出非名單玩家                                                         |
| view-distance                     | 10      | 視野距離（區塊）。**對效能影響最大的單一設定**                                         |
| simulation-distance               | 10      | 模擬距離。決定生怪、紅石、實體運算範圍，可設得比 view-distance 小                      |
| max-tick-time                     | 60000   | 單刻超時看門狗上限，設 -1 停用（除錯時常用）                                           |
| spawn-protection                  | 16      | 出生點保護半徑，設 0 關閉                                                              |
| enable-command-block              | false   | **命令方塊總開關，預設是關的**。26.x 另有 `command_blocks_work` 遊戲規則，兩者都要通過 |
| allow-flight                      | false   | 允許飛行（用飛行插件或鞘翅時需開）                                                     |
| difficulty                        | easy    | 難度                                                                                   |
| level-seed / level-type           | —       | 世界種子 / 類型（`flat`、`largeBiomes`、`amplified`）                                  |
| enable-rcon                       | false   | 遠端主控台，需搭配 `rcon.password`                                                     |
| enable-query                      | false   | 對外查詢伺服器狀態                                                                     |
| network-compression-threshold     | 256     | 封包壓縮門檻。同機或區網可設 -1 降低延遲                                               |
| sync-chunk-writes                 | true    | 同步寫入區塊。設 false 提升效能但當機風險較高                                          |
| entity-broadcast-range-percentage | 100     | 實體同步範圍百分比，調低可減輕頻寬負擔                                                 |
| region-file-compression           | deflate | 26.1 起 Paper 的 `compression-format` 已併入此項，可選 gzip                            |

> ℹ️ 修改 `server.properties` 後**必須重啟伺服器**才會生效，`/reload` 沒有用。  
> `pvp` 在 26.x 同時存在於 server.properties 與遊戲規則中；若行為與預期不符，兩邊都檢查一次。  
> Paper 預告 **26.4 會把 bukkit.yml、spigot.yml 與 paper 各設定檔合併**，屆時這張表的對應關係會有變動。

<span id="s37"></span>

<a id="s37"></a>

## 37 · 實用指令組合與錯誤排查

#### 清理與維護

    # 清除所有掉落物與經驗球（緊急降卡頓）
    /kill @e[type=item]
    /kill @e[type=experience_orb]

    # 只清除離玩家很遠的掉落物，保留手邊的
    /execute as @e[type=item] at @s unless entity @a[distance=..64] run kill @s

    # 統計世界上各類實體數量
    /paper entity list

    # 檢查有沒有忘了關的常載區塊
    /forceload query

> ⚠️ **26.3 之後請避免 `/kill @e[type=!player]`。**坐墊（cushion）是實體，玩家蓋的休息區、廢棄營地裡原生的坐墊都會被一次清光，而且沒辦法復原。清理時一律明確指定 `type=item`、`type=experience_orb` 等具體類型。

#### 常見管理場景

    # 全服公告 + 音效提示（Java 與基岩玩家都收得到）
    /title @a title {"text":"伺服器將於 5 分鐘後重啟","color":"red"}
    /playsound minecraft:block.note_block.pling master @a
    /discord broadcast 伺服器將於 5 分鐘後重啟

    # 把所有玩家傳到主城
    /tp @a 0 100 0

    # 把玩家分散到半徑 500 的隨機位置
    /spreadplayers 0 0 200 500 false @a

    # 加白名單：Java 玩家與基岩玩家用不同指令
    /whitelist add JavaPlayerName
    /fwhitelist add BedrockPlayerName

#### 紅石與技術測試

    # 站上鑽石磚就給速度效果
    /execute as @a at @s if block ~ ~-1 ~ diamond_block run effect give @s speed 3 2 true

    # 檢查中繼器的實際延遲設定
    /data get block ~ ~ ~ delay

    # 讀取熔爐的燃燒剩餘時間
    /data get block ~ ~ ~ BurnTime

    # 讓漏斗暫時停止運作
    /data merge block ~ ~ ~ {TransferCooldown:32767}

    # 慢動作觀察電路（每秒 5 刻）
    /tick rate 5

    # 快轉一小時測試農場產能
    /tick sprint 72000

    # 測試時關掉干擾因素（26.x 的規則名稱）
    /gamerule random_tick_speed 0
    /gamerule spawn_mobs false
    /gamerule advance_time false
    /gamerule command_block_output false

#### 用 storage 做全域變數

    # 寫入
    /data modify storage server:config spawnRadius set value 500

    # 讀出到記分板
    /execute store result score #radius temp run data get storage server:config spawnRadius

    # 條件判斷
    /execute if data storage server:config {maintenance:1b} run kick @a[tag=!admin] 維護中

### 錯誤排查對照表

| 症狀                            | 可能原因                                                                        |
|---------------------------------|---------------------------------------------------------------------------------|
| gamerule 指令說找不到規則       | **最常見**：還在用 camelCase 舊名。改成 snake_case，見「舊名 → 新名」那節       |
| 改了 gamerule 但行為相反        | 踩到「值反轉」的三條：`raids`、`elytra_movement_check`、`player_movement_check` |
| gamerule 自動化腳本在 26.3 失準 | 設定值與現值相同時不再回報成功（MC-174958 修正）。改用不帶值的查詢形式讀現值    |
| 火焰蔓延關不掉                  | `doFireTick` 已移除，改用 `fire_spread_radius_around_player 0`                  |
| 指令說「未知的指令」            | 權限不足（會被隱藏）、拼字錯誤、或該版本尚未加入此指令                          |
| 命令方塊完全沒反應              | `enable-command-block=false` 沒開，或 `command_blocks_work` 被設為 false        |
| posteffect 指令成功但看不到效果 | 後處理著色器在客戶端的資源包裡，伺服器無從得知是否真的存在。基岩玩家則一律無效  |
| compute 整個指令失敗            | number provider 求值失敗（例如除以零）時指令會失敗，不是回傳 0                  |
| 物品 NBT 寫法失效               | 1.20.5 起改為物品組件語法，用 `[]` 而非 `{}`                                    |
| 釀造台燃料資料包壞掉            | 26.3 移除了 `#brewing_fuel` 物品標籤，改用 `minecraft:brewing_fuel` 組件        |
| 資料包載入後沒作用              | 1.21 資料夾需改單數；`pack_format` 要設成 **121.0**                             |
| fill 顯示「方塊過多」           | 超過 `max_block_modifications`，分批執行或調高規則值                            |
| execute 選不到目標              | 檢查是否漏了 `at @s`，選擇器的搜尋原點可能還在原本的執行位置                    |
| 白名單改了沒生效                | 手動編輯 whitelist.json 後需 `/whitelist reload`                                |
| 基岩玩家進不來                  | 用 `/fwhitelist` 而非 `/whitelist`；檢查名稱前綴；確認 Geyser 版本已支援 26.3   |
| 基岩玩家看到奇怪的方塊          | Geyser 版本對不上 26.3，新方塊（白楊木、坐墊、稻草床）無法正確映射              |
| DiscordSRV 改了設定沒反應       | 用 `/discordsrv reload`，不要用伺服器的 `/reload`；部分改動需重啟               |
| Discord 訊息傳不進遊戲          | Bot 缺少 MESSAGE CONTENT INTENT，到 Developer Portal 開啟                       |
| 伺服器根本起不來                | Java 版本太舊。26.x 需要 **Java 25** 以上                                       |
| 升級後世界壞掉                  | 26.1+ 無法降版。只能從備份還原——這就是為什麼備份是必要的                        |

本手冊以 Minecraft Java Edition 26.3 Wilderness Bound / Paper 26.3 的指令行為撰寫。Geyser、Floodgate、DiscordSRV 為第三方專案，其指令與權限節點可能隨版本調整。遇到不確定的語法時，在遊戲內輸入指令名稱後按 Tab 鍵，Brigadier 會即時提示該版本實際支援的參數——這永遠是最可靠的答案來源。

</div>

</div>

</div>

</div>

</div>

</div>
