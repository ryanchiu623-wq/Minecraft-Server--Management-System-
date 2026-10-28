# Minecraft Server Management System

**繁體中文** · [English](README.en.md)

在家裡的 Windows 電腦上開 Paper 伺服器，讓它自己照顧自己：當掉會自己起來、每天備份並驗證、要關機或重開時一定先在遊戲裡倒數 5 分鐘。平常用瀏覽器、Discord 或遊戲內選單管理，不用回到電腦前面。

> Self-hosting toolkit for a Paper Minecraft server on a home Windows machine.
> One installer sets up the server, plugins and automation; a web console,
> a Discord bot and an in-game panel handle day-to-day management.
> The interface is in Traditional Chinese.

[![下載](https://img.shields.io/badge/%E4%B8%8B%E8%BC%89-MinecraftToolkitSetup.exe-2ea44f?style=for-the-badge)](../../releases/latest)

---

## 文件

| 文件 | 內容 |
|---|---|
| [安裝流程（playit 隧道）](docs/INSTALL.md) | **多數人看這份。** 從零開始的完整流程，不需要公網 IP |
| [安裝流程（路由器轉埠）](docs/INSTALL-port-forwarding.md) | 你有公網 IP、想直連降低延遲時看這份 |
| [內建外掛說明](bundled/README.md) | PanelKey 和 RyanDrawers 的指令、設定、自行建置方式 |

本頁下面有 [對外開放](#對外開放playit)、[遠端控制台](#從外面管理cloudflare-隧道)、[安全性](#安全性)、[排程工作](#排程工作)、[踩過的坑](#踩過的坑)。

---

## 這套東西解決什麼

| 你想做的事 | 怎麼做到 |
|---|---|
| 讓朋友從外網連進來 | playit 隧道，不用動路由器 |
| 手機／平板／主機版朋友也能玩 | Geyser + Floodgate，他們不需要 Java 帳號 |
| 在沙發上看伺服器狀況 | 內網控制台網頁，手機打開就能看 |
| 人在外面想管伺服器 | Discord 機器人，或經 Cloudflare 隧道登入的遠端控制台 |
| 在遊戲裡管伺服器 | PanelKey 外掛的 `/menu` 管理面板 |
| 關服、重開不嚇到玩家 | 所有入口都走同一支倒數腳本，先廣播 5 分鐘，可以取消 |
| 伺服器當掉 | 看門狗每 5 分鐘檢查，自動拉起來 |
| 世界壞掉想還原 | 每天備份世界和設定，逐一驗證區塊，再複製一份到另一顆硬碟 |
| 回頭看發生了什麼事 | SimplyFlashback 替每個上線玩家自動錄影，保留 36 小時 |
| 看世界長什麼樣 | BlueMap 3D 網頁地圖，發布到 Cloudflare Pages |

---

## 快速開始

到 [Releases](../../releases/latest) 下載 `MinecraftToolkitSetup.exe` 執行。

安裝程式會做這些，每一項都能個別取消勾選：

1. 檢查 Java 版本、受控資料夾存取狀態、管理員權限
2. 下載你選的 Paper 版本
3. 下載外掛（Geyser、Floodgate、BlueMap、DeluxeMenus、PlaceholderAPI、LuckPerms、WorldEdit、WorldGuard、DiscordSRV）
4. 裝上內建的 PanelKey 外掛與管理選單
5. 開啟 RCON 並產生密碼
6. 寫好 `config.json`
7. 註冊排程工作（備份、看門狗、控制台）
8. 建立防火牆規則與桌面捷徑

需要系統管理員權限（防火牆規則要）。裝完啟動伺服器，然後開 `http://localhost:8099`。

不想用安裝程式的話，有兩份從零開始的手動流程，每一節都附驗證步驟。差別只在怎麼讓外面連進來，**只需要看一份**：

| | 適用 |
|---|---|
| [INSTALL.md](docs/INSTALL.md) | **多數人選這份。** 用 playit 隧道，不需要公網 IP、不用動路由器。台灣家用寬頻常見的 CGNAT 也能用 |
| [INSTALL-port-forwarding.md](docs/INSTALL-port-forwarding.md) | 你有公網 IP，想直連降低延遲。需要自己設定路由器，而且你家 IP 會曝光 |

---

## 內容

### 管理介面

| 元件 | 位置 | 做什麼 |
|---|---|---|
| **網頁控制台** | `scripts/web-console.py` | 狀態磚、啟動／倒數關閉／重開／取消、備份、RCON、日誌、遊戲規則、記憶體配置，還有各外掛的操作面板（`plugin_panels.py`）。區網直接用；外網走另一個要登入的入口 |
| **桌面控制台** | `scripts/console-gui.py` | tkinter 圖形介面，功能同網頁版 |
| **Discord 機器人** | `scripts/discord-control.py` | `/status` `/start` `/stop` `/restart` `/cancel` `/rcon` `/render` `/ip` `/inv`（唯讀看玩家背包）`/console-password`。伺服器或隧道狀態改變時主動通知 |
| **PanelKey 外掛** | `bundled/panelkey-src/` | 遊戲內管理面板、玩家選單、`/tpamenu`、行動工作台；把遊戲內的 `/stop`、`/restart` 改成 5 分鐘倒數。見 [bundled/README.md](bundled/README.md) |
| **管理選單** | `bundled/deluxemenus/` | DeluxeMenus 選單：管理面板、關服確認、工具箱、行動工作站、玩家選單 |

### 開關與重開

| 元件 | 位置 | 做什麼 |
|---|---|---|
| **倒數關閉／重開** | `scripts/restart-sequence.py` | 所有管理介面共用：遊戲內廣播 5／3／1 分鐘，最後 30 秒倒數，可以取消 |
| **啟動伺服器** | `scripts/start-server.py` | 桌面捷徑。不開主控台視窗，避免有人關掉視窗把伺服器砍掉 |
| **安全重開電腦／安全關機** | `scripts/safe-power.py` | 桌面捷徑。先倒數關服、等 java 存完檔，才重開或關掉 Windows |
| **換外掛** | `scripts/swap-plugin.py` | 伺服器鎖著 jar 時用：倒數關服 → 換 jar → 重開。`--wait-empty` 等沒人在線再做 |
| **看門狗** | `windows/watchdog.ps1` | 每 5 分鐘檢查伺服器和隧道，意外死掉就拉起來 |
| **開機自動鎖定** | `windows/lock-after-autologon.ps1` | Windows 設成自動登入時，登入後馬上鎖住螢幕，伺服器照常在背景執行 |

### 備份與紀錄

| 元件 | 位置 | 做什麼 |
|---|---|---|
| **世界備份** | `windows/backup-world.ps1` | 暫停自動存檔 → 落盤 → 複製 → 壓縮 → 輪替 |
| **設定備份** | `scripts/backup-config.py` | 白名單、ops、外掛資料、外掛 jar、工具包本身、隧道憑證。LuckPerms 和 SQLite 用線上匯出，不會讀到寫一半的檔案。**這個 zip 含機密，請妥善保管** |
| **備份驗證** | `scripts/verify-backup.py` | 不解壓，逐一讀每個區塊的 NBT，並比對各維度的區域檔數量 |
| **異地副本** | `windows/mirror-backup.ps1` | 驗證通過的備份複製到另一顆實體硬碟 |
| **自動錄影** | `scripts/flashback-record.py` | 每分鐘幫沒在錄的線上玩家開始 SimplyFlashback 錄影，並複製一份給 Flashback 模組觀看 |
| **錄影清理** | `windows/flashback-cleanup.ps1` | 刪掉超過保留時數的錄影 |

### 其他

| 元件 | 位置 | 做什麼 |
|---|---|---|
| **安裝程式** | `installer/` | 上面「快速開始」那八件事，圖形介面 |
| **健康檢查** | `scripts/check-server.py` | 本機 → DNS → 隧道 → 外部視角 → 網頁地圖，每條路徑用玩家實際連線的方式檢查 |
| **地圖發布** | `windows/sync-map.ps1` | BlueMap 靜態輸出推到 Cloudflare Pages |
| **RyanDrawers 外掛** | `bundled/drawers-src/` | Storage Drawers 風格的抽屜，用木桶做，玩家不用裝模組。含自動測試外掛。安裝程式不會裝，要自己建置 |
| **藍圖轉換器** | `scripts/litematic2structure.py` | `.litematic` → 結構方塊 `.nbt`，保留容器內容 |

除了 Discord 機器人需要 `discord.py`，其餘只用 Python 標準函式庫。

---

## 需求

| 項目 | 版本 |
|---|---|
| Windows | 10 / 11 |
| Java | 25 以上 |
| Paper | 26.x（外掛以 `api-version: 1.21` 編譯） |
| Python | 3.10 以上（只有手動安裝需要，EXE 已內含） |

---

## 設定

一份 `config.json` 設定所有工具：

```bash
copy config.example.json config.json
```

用安裝程式的話這步會自動完成，之後只要補對外網域、Discord、Cloudflare 那幾欄。`config.example.json` 每一段都有註解；用不到的功能（異地備份、自動錄影、遠端控制台）留空或刪掉即可。

機密**不寫在設定檔裡**，而是用路徑指向 repo 外的檔案：

```json
"discord": { "tokenFile": "C:\\Users\\你\\.secrets\\discord-bot-token.txt" }
```

`config.json` 本身也在 `.gitignore` 裡，因為它帶著你的網域和 ID。

---

## 對外開放（playit）

**安裝程式不會做這一步**，因為它需要你自己註冊帳號。這也是朋友能不能連進來的關鍵，所以放在這裡。

家用網路多半沒有固定 IP、不能開通訊埠（台灣的家用寬頻很多是電信商的 CGNAT）。playit 用一條由內往外建立的隧道繞過這個限制，免費、不用動路由器。

### 1. 安裝

到 <https://playit.gg> 註冊，下載 Windows 版安裝。它會裝成系統服務 `playitd`，開機自動啟動。第一次執行會給你一個網址去綁定帳號。

### 2. 建立隧道

在網頁後台建立兩條，**通訊協定不能選錯**：

| 類型 | 通訊協定 | 指向本機 |
|---|---|---|
| Minecraft Java | **TCP** | `127.0.0.1:25565` |
| Minecraft 基岩版 | **UDP** | `127.0.0.1:19132` |

建好會拿到類似 `something.tun.ply.gg:12345` 的公開位址。不玩基岩版的話第二條可以不建。

### 3. 填進 config.json

```json
"java":    { "host": "something.tun.ply.gg", "port": 25565 },
"bedrock": { "host": "something.tun.ply.gg", "tunnelPort": 12345 },
"tunnel":  { "java": "playit", "bedrock": "playit", "web": "pages" }
```

`tunnelPort` 填 playit 給的**公開 UDP 埠**，通常不是 19132——基岩版玩家在遊戲裡要填這個。`tunnel` 告訴看門狗和健康檢查每條路徑走哪種隧道（Java 也可以用 `cloudflared`，基岩版也可以用 Geyser 的 `warden`）。

### 4. 綁自己的網域（選用）

用 Cloudflare 的話：

| 類型 | 名稱 | 內容 | Proxy |
|---|---|---|---|
| A | `mc` | playit 給的 IP | **DNS only（灰雲）** |
| SRV | `_minecraft._tcp.mc` | 優先權 0、權重 0、埠 `<playit 的埠>`、目標 `mc.你的網域` | — |
| A | `bedrock` | playit 給的 IP | **DNS only（灰雲）** |

有 SRV 記錄的話，Java 版玩家只要打 `mc.你的網域`，不用加埠號。

### 三個會卡住你的地方

**Proxy 一定要關（灰雲）。** 橘雲是 HTTP 代理，Minecraft 的協定過不去。

**不要建 AAAA 記錄。** playit 會公告 IPv6 位址但不會真的把 IPv6 流量送到 agent，玩家會拿到 `Connection timed out: getsockopt`。整條 DNS 鏈路只用 IPv4。

**後台顯示「線上」不代表真的通。** 那只反映 agent 有沒有連上 playit 的服務，不保證流量到得了你的機器。判斷依據是 agent 日誌（`C:\ProgramData\playit_gg\logs\playitd.log`）和 `python scripts/check-server.py` 的外部視角那一層。遇到後台一切正常但就是連不進來時，**刪掉 agent 和隧道重新建立**往往是唯一有效的解法。

### 驗證

```bash
python scripts/check-server.py
```

「外部視角」那一層通過就是真的通了。最後叫朋友實際連連看——外部檢測通過不等於玩家真的進得來。

完整版（含疑難排解）在 [docs/INSTALL.md 第 3 節](docs/INSTALL.md#3-對外開放)。

---

## 從外面管理（Cloudflare 隧道）

區網控制台（8099）只收內網連線。要從外面用，控制台另外開一個**只綁 `127.0.0.1` 的登入入口**（`webConsole.publicPort`，預設 8098），讓 Cloudflare Tunnel 指向它：

1. 在電腦前設定帳號密碼（密碼只存加鹽的 PBKDF2 雜湊）：
   ```bash
   python scripts/console_auth.py
   ```
   人不在電腦前時，也可以用 Discord 的 `/console-password` 設定。
2. Cloudflare Tunnel 的公開主機名稱指向 `http://127.0.0.1:8098`。
3. `config.json` 的 `webConsole.publicUrl` 填那個網址。

登入後，會改變狀態的按鈕一樣要控制權杖。登入失敗會依來源位址和總次數限速。

---

## 安全性

控制台能關伺服器、能執行任意主控台指令，所以區網入口有三層防護：

1. **內網位址檢查** —— 明確列舉 `127/8`、`10/8`、`172.16/12`、`192.168/16`、`169.254/16`、`::1`、`fc00::/7`、`fe80::/10`。刻意不用 `ipaddress.is_private`，因為它把 `203.0.113.0/24` 這類文件網段也算成私有。
2. **控制權杖** —— 只有會改變狀態的動作需要；純看狀態不用，手機拿起來就能看。
3. **防火牆規則** 限定 LocalSubnet。

外網入口再多一層帳號密碼。外掛面板送出的每個參數都先用固定格式檢查過才放進指令，因為 RCON 以主控台權限執行一切。所有會改變狀態的動作都會記進 `web-console.log`，含來源 IP。

> **絕對不要把隧道指向區網控制台的埠（8099）。** 隧道 agent 是從 `127.0.0.1` 連進本機服務的，會通過內網位址檢查——等於把管理頁面直接送上公網，只剩權杖擋著。要從外面用，只能走上面那個要登入的入口。

---

## 排程工作

`windows/` 和 `scripts/` 的腳本設計成由 Windows 工作排程器呼叫。安裝程式會建好備份、看門狗、控制台三個，其餘可自行加：

| 工作 | 觸發 | 執行 |
|---|---|---|
| 世界與設定備份 | 每天 04:00 | `powershell -WindowStyle Hidden -File backup-world.ps1`（之後自動跑設定備份、驗證、異地副本） |
| 看門狗 | 每 5 分鐘 | `powershell -WindowStyle Hidden -File watchdog.ps1` |
| 排程重啟 | 重啟時間前 5 分鐘 | `pythonw restart-sequence.py` |
| Discord bot | 登入時 | `pythonw discord-control.py` |
| 內網控制台 | 登入時 | `pythonw web-console.py` |
| 自動錄影 | 每 1 分鐘 | `pythonw flashback-record.py` |
| 錄影清理 | 每 1 小時 | `powershell -WindowStyle Hidden -File flashback-cleanup.ps1` |
| 開機自動鎖定 | 登入時 | `powershell -WindowStyle Hidden -File lock-after-autologon.ps1` |

用 `pythonw` 和 `-WindowStyle Hidden` 不是為了好看：不加的話每次觸發都會彈一個主控台視窗，看門狗每 5 分鐘一次，玩遊戲會一直被打斷。長時間執行的工作記得把「執行時間上限」設成無限，預設 3 天會被排程器砍掉。

---

## 踩過的坑

以下每一項都是實際 debug 出來的，寫在這裡省下重蹈覆轍的時間。

**受控資料夾存取會無聲擋掉寫入。** Windows Defender 預設保護 `Documents`、`Pictures`、`Desktop`。伺服器或工具的工作目錄放在那底下，症狀是「沒有錯誤訊息但程式就是死掉或卡住」，而且會把你引導到完全錯誤的方向。東西放在那些資料夾之外就好，不需要關掉這個防護。

**直接重開或關掉 Windows 會讓伺服器沒存檔就被砍掉。** 所以有「安全重開電腦」「安全關機」兩個捷徑，先倒數關服、等 java 結束，再交給 Windows。

**伺服器開在主控台視窗裡，關掉視窗就等於強制結束。** 改成背景啟動（`start-server.py`），關服一律走倒數腳本。

**原版 `/stop` 和 Spigot 的 `/restart` 會立刻關服。** 管理員順手一打，承諾玩家的 5 分鐘預告就沒了。PanelKey 把遊戲內打的這兩個指令改成倒數；主控台和 RCON 保留立即關服，留給緊急狀況。

**Paper 的 RCON 只回傳指令執行當下印出的東西。** LuckPerms、WorldGuard、spark、Floodgate 都是非同步回覆，從 RCON 永遠收不到。控制台的外掛面板改成送出指令後，去讀外掛自己寫的檔案（LuckPerms 匯出、`regions.yml`、spark 的 `activity.json`、`whitelist.json`）。

**沒有主控台的背景程式，每叫一個主控台程式就開一個新視窗。** `pythonw.exe` 自己沒有主控台，所以它 `subprocess` 出去的每個 console 程式都會拿到一個新視窗。所有 `subprocess` 呼叫都要帶 `creationflags=CREATE_NO_WINDOW`。

**`Start-Process -ArgumentList` 不會替含空白的元素加引號。** `'/c','start','MC Server','/min',$bat` 送到 cmd 會變成 `start MC Server /min ...`——`start` 把 `MC` 當成視窗標題、去執行一個叫 `Server` 的東西，批次檔根本沒被叫到，而且完全無聲。要寫成 `'"MC Server"'`。

**含中文的 `.ps1` 必須存成 UTF-8 with BOM。** Windows PowerShell 5.1 把沒有 BOM 的檔案當系統 ANSI 讀，某些中文字的第二個位元組會吃掉後面的大括號，然後報 `MissingEndCurlyBrace` 並指向一行完全正確的程式碼。

**`.bat` 必須純 ASCII 且 CRLF 換行。** cmd.exe 用 OEM 編碼讀批次檔，UTF-8 中文註解會讓後續指令被切碎後當成指令執行。LF 換行會讓多行 `if (...)` 區塊失效。

**開了 DPI awareness 卻不自己縮放，比不開還糟。** 開了之後 Windows 就不再放大你的視窗，程式必須自己處理字體與尺寸，否則在 2.25× 螢幕上全部縮成三分之一，而且放大視窗沒有用。另外 `SetProcessDpiAwareness` 必須在建立視窗**之前**呼叫，寫在後面完全沒作用。

**Flashback 模組只列出 `.zip`。** SimplyFlashback 存的 `.flashback` 其實就是 zip，複製過去時改副檔名就能看。

**伺服器會把結構模板快取在記憶體。** 改了磁碟上的 `.nbt` 之後，同一個 ID 仍然沿用舊版；換檔名或重啟才會生效。

---

## 藍圖轉換器

```bash
python scripts/litematic2structure.py 藍圖.litematic 輸出目錄 --prefix 名稱
```

Litematica 逐塊放置且不管相依順序，鐵軌會在底下的方塊還沒放好就先放，然後掉下來。更糟的是走 WorldEdit `//set` 的放置**不會寫入容器內容物**——全物品分類器的過濾漏斗會全空，機器不動而且不報錯。

結構方塊是整批放置、不觸發方塊更新，而且帶得動容器內容。轉換器：

- 保留原始 NBT 標籤型別（物品堆疊的 `Slot` 是 TAG_Byte，寫成 int 容器就會被判定為空）
- 保留實體與方塊實體
- 把空氣一起寫進去（結構只放置它列出的方塊，漏掉空氣會讓機器被原地形埋住）
- 超過 48×48×48 自動切片，並印出每片該放的相對座標

輸出到 `<世界>/generated/minecraft/structure/`（**單數** `structure`）。

---

## 自行建置安裝程式

```bash
pip install pyinstaller
python installer/build_exe.py
```

產出 `dist/MinecraftToolkitSetup.exe`，單檔自帶所有內容。

---

## 靈感來源

安裝程式的構想來自
[tntapple219/MinecraftServerManager](https://github.com/tntapple219/MinecraftServerManager)（MIT 授權）——
用一支 PyInstaller 打包的圖形程式把整套安裝跑完。

---

## 授權

MIT
