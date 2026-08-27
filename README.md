# Minecraft Server Management System

在家裡的 Windows 電腦上開 Minecraft 伺服器，並且讓它自己照顧自己。

一支安裝程式把伺服器、外掛、管理工具、排程全部裝好；之後用瀏覽器或 Discord 管理，不用再回到電腦前面。

> Self-hosting toolkit for a Paper Minecraft server on a home Windows machine.
> One installer sets up the server, plugins and automation; a LAN-only web
> console and a Discord bot handle day-to-day management. The interface is in
> Traditional Chinese.

[![下載](https://img.shields.io/badge/%E4%B8%8B%E8%BC%89-MinecraftToolkitSetup.exe-2ea44f?style=for-the-badge)](../../releases/latest)

---

## 這套東西解決什麼

家用網路沒有固定 IP、不能開通訊埠，朋友連不進來；伺服器半夜當掉沒人知道；想關伺服器得跑回電腦前；基岩版的朋友（手機、平板、主機）連不進 Java 版伺服器。

| 你想做的事 | 怎麼做到 |
|---|---|
| 讓朋友從外網連進來 | playit 隧道，不用動路由器 |
| 手機／平板／主機版朋友也能玩 | Geyser + Floodgate，他們不需要 Java 帳號 |
| 在沙發上看伺服器狀況 | 內網控制台網頁 |
| 人在外面想開關伺服器 | Discord 機器人 |
| 伺服器當掉 | 看門狗每 5 分鐘檢查，自動拉起來 |
| 世界壞掉想還原 | 每日自動備份，保留 7 份 |
| 看世界長什麼樣 | BlueMap 3D 網頁地圖 |

---

## 快速開始

到 [Releases](../../releases/latest) 下載 `MinecraftToolkitSetup.exe` 執行。

安裝程式會做這些，每一項都能個別取消勾選：

1. 檢查 Java 版本、受控資料夾存取狀態、管理員權限
2. 下載你選的 Paper 版本
3. 下載外掛（Geyser、Floodgate、BlueMap、DeluxeMenus、PlaceholderAPI、LuckPerms、WorldEdit、WorldGuard、DiscordSRV）
4. 裝上內建的 PanelKey 外掛與四份管理選單
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

| 元件 | 位置 | 做什麼 |
|---|---|---|
| **安裝程式** | `installer/` | 上面那八件事，圖形介面 |
| **內網控制台** | `scripts/web-console.py` | 瀏覽器管理頁：狀態磚、啟停、備份、RCON、日誌。只接受內網連線 |
| **健康檢查** | `scripts/check-server.py` | 六層檢查：本機 → DNS → 隧道 → 外部視角 → 網頁地圖 |
| **Discord 機器人** | `scripts/discord-control.py` | `/status` `/start` `/stop` `/rcon` `/ip` `/render` |
| **桌面控制台** | `scripts/console-gui.py` | tkinter 圖形介面，功能同網頁版 |
| **排程重啟** | `scripts/restart-sequence.py` | 重啟前 5／3／1 分鐘廣播，最後 30 秒倒數 |
| **看門狗** | `windows/watchdog.ps1` | 每 5 分鐘檢查，意外死掉就拉起來 |
| **備份** | `windows/backup-world.ps1` | 暫停自動存檔 → 落盤 → 複製 → 壓縮 → 輪替 |
| **地圖發布** | `windows/sync-map.ps1` | BlueMap 靜態輸出推到 Cloudflare Pages |
| **PanelKey 外掛** | `bundled/` | 遊戲內管理面板：`/menu`、`/spawn`、行動工作台、指定給予對象。含原始碼 |
| **管理選單** | `bundled/deluxemenus/` | 四份 DeluxeMenus 選單，安裝時一併註冊 |
| **藍圖轉換器** | `scripts/litematic2structure.py` | `.litematic` → 結構方塊 `.nbt`，保留容器內容 |

除了 Discord 機器人需要 `discord.py`，其餘只用 Python 標準函式庫。

---

## 需求

| 項目 | 版本 |
|---|---|
| Windows | 10 / 11 |
| Java | 21 以上 |
| Python | 3.10 以上（只有手動安裝需要，EXE 已內含） |

---

## 設定

一份 `config.json` 設定所有工具：

```bash
copy config.example.json config.json
```

用安裝程式的話這步會自動完成，之後只要補對外網域、Discord、Cloudflare 那幾欄。

機密**不寫在設定檔裡**，而是用路徑指向 repo 外的檔案：

```json
"discord": { "tokenFile": "C:\\Users\\你\\.secrets\\discord-bot-token.txt" }
```

`config.json` 本身也在 `.gitignore` 裡，因為它帶著你的網域和 ID。

---

## 安全性

控制台能關伺服器、能執行任意主控台指令，所以有三層防護：

1. **內網位址檢查** —— 明確列舉 `127/8`、`10/8`、`172.16/12`、`192.168/16`、`169.254/16`、`::1`、`fc00::/7`、`fe80::/10`。刻意不用 `ipaddress.is_private`，因為它把 `203.0.113.0/24` 這類文件網段也算成私有。
2. **控制權杖** —— 只有會改變狀態的動作需要；純看狀態不用，手機拿起來就能看。
3. **防火牆規則** 限定 LocalSubnet。

所有會改變狀態的動作都會記進 `web-console.log`，含來源 IP。

> **絕對不要幫控制台的埠開 playit 或任何內網穿透隧道。** 穿透工具的 agent 是從 `127.0.0.1` 連進本機服務的，會通過內網位址檢查——等於把管理頁面直接送上公網，只剩權杖擋著。

---

## 排程工作

`windows/` 的腳本設計成由 Windows 工作排程器呼叫。安裝程式會建好備份、看門狗、控制台三個，其餘可自行加：

| 工作 | 觸發 | 執行 |
|---|---|---|
| 世界備份 | 每天 04:00 | `powershell -WindowStyle Hidden -File backup-world.ps1` |
| 看門狗 | 每 5 分鐘 | `powershell -WindowStyle Hidden -File watchdog.ps1` |
| 排程重啟 | 重啟時間前 5 分鐘 | `pythonw restart-sequence.py` |
| Discord bot | 登入時 | `pythonw discord-control.py` |
| 內網控制台 | 登入時 | `pythonw web-console.py` |

用 `pythonw` 和 `-WindowStyle Hidden` 不是為了好看：不加的話每次觸發都會彈一個主控台視窗，看門狗每 5 分鐘一次，玩遊戲會一直被打斷。長時間執行的工作記得把「執行時間上限」設成無限，預設 3 天會被排程器砍掉。

---

## 踩過的坑

以下每一項都是實際 debug 出來的，寫在這裡省下重蹈覆轍的時間。

**受控資料夾存取會無聲擋掉寫入。** Windows Defender 預設保護 `Documents`、`Pictures`、`Desktop`。伺服器或工具的工作目錄放在那底下，症狀是「沒有錯誤訊息但程式就是死掉或卡住」，而且會把你引導到完全錯誤的方向。東西放在那些資料夾之外就好，不需要關掉這個防護。

**沒有主控台的背景程式，每叫一個主控台程式就開一個新視窗。** `pythonw.exe` 自己沒有主控台，所以它 `subprocess` 出去的每個 console 程式都會拿到一個新視窗。所有 `subprocess` 呼叫都要帶 `creationflags=CREATE_NO_WINDOW`。

**`Start-Process -ArgumentList` 不會替含空白的元素加引號。** `'/c','start','MC Server','/min',$bat` 送到 cmd 會變成 `start MC Server /min ...`——`start` 把 `MC` 當成視窗標題、去執行一個叫 `Server` 的東西，批次檔根本沒被叫到，而且完全無聲。要寫成 `'"MC Server"'`。

**含中文的 `.ps1` 必須存成 UTF-8 with BOM。** Windows PowerShell 5.1 把沒有 BOM 的檔案當系統 ANSI 讀，某些中文字的第二個位元組會吃掉後面的大括號，然後報 `MissingEndCurlyBrace` 並指向一行完全正確的程式碼。

**`.bat` 必須純 ASCII 且 CRLF 換行。** cmd.exe 用 OEM 編碼讀批次檔，UTF-8 中文註解會讓後續指令被切碎後當成指令執行。LF 換行會讓多行 `if (...)` 區塊失效。

**開了 DPI awareness 卻不自己縮放，比不開還糟。** 開了之後 Windows 就不再放大你的視窗，程式必須自己處理字體與尺寸，否則在 2.25× 螢幕上全部縮成三分之一，而且放大視窗沒有用。另外 `SetProcessDpiAwareness` 必須在建立視窗**之前**呼叫，寫在後面完全沒作用。

**playit 後台顯示「線上」不代表真的通。** 那只反映 agent 有沒有連上服務，不保證流量到得了你的機器。判斷依據是 agent 日誌和外部檢測。另外 playit 會公告 IPv6 位址卻不路由 IPv6，所以 DNS 不要建 AAAA 記錄，否則玩家會拿到 `Connection timed out: getsockopt`。

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

## 授權

MIT
