# Minecraft Server Toolkit

家用 Windows 機器上跑 Paper 伺服器的一整套管理工具：內網監控網頁、Discord 遙控機器人、桌面控制台、自動備份、看門狗、排程重啟，以及把 Litematica 藍圖轉成結構方塊檔的轉換器。

全部只用 Python 標準函式庫（Discord bot 除外），一份 `config.json` 設定完畢。

> A toolkit for self-hosting a Paper Minecraft server on a home Windows box:
> LAN-only web console, Discord control bot, desktop console, automated
> backups, watchdog, scheduled restarts, and a Litematica→structure-block
> converter. The user interface is in Traditional Chinese.

---

## 內容

| 元件 | 檔案 | 做什麼 |
|---|---|---|
| **內網控制台** | `scripts/web-console.py`<br>`scripts/web-console.html` | 瀏覽器管理頁：即時狀態磚、啟停伺服器、備份、RCON、日誌尾巴。只接受內網連線 |
| **健康檢查** | `scripts/check-server.py` | 六層檢查：本機服務 → DNS → 隧道 → 外部視角 → 網頁地圖。由上往下排，下層問題通常是上層造成的 |
| **Discord 機器人** | `scripts/discord-control.py` | 手機遙控：`/status` `/start` `/stop` `/rcon` `/ip` `/render`，加上事件回報頻道 |
| **桌面控制台** | `scripts/console-gui.py` | tkinter 圖形介面，功能同網頁版 |
| **RCON 用戶端** | `scripts/rcon.py` | 可當指令列工具，也可被其他腳本 import |
| **排程重啟** | `scripts/restart-sequence.py` | 重啟前 5／3／1 分鐘廣播，最後 30 秒倒數 |
| **藍圖轉換器** | `scripts/litematic2structure.py` | `.litematic` → 結構方塊 `.nbt`，保留容器內容與實體 |
| **啟動腳本** | `windows/start.bat` | 起隧道、起地圖同步、起伺服器，並處理當機與快速重啟的競態 |
| **備份** | `windows/backup-world.ps1` | 暫停自動存檔 → 落盤 → 複製 → 壓縮 → 輪替 |
| **看門狗** | `windows/watchdog.ps1` | 每 5 分鐘檢查，伺服器意外死掉就拉起來 |
| **地圖發布** | `windows/sync-map.ps1`<br>`windows/sync-loop.ps1` | 把 BlueMap 的靜態輸出推到 Cloudflare Pages |

---

## 需求

- Windows 10/11
- Python 3.10+
- Java 21+（Paper 需要）
- 選用：`discord.py`（只有 Discord bot 需要）、`wrangler`（只有地圖發布需要）

```bash
pip install discord.py
```

---

## 安裝

### 用安裝程式（最省事）

到 [Releases](../../releases) 下載 `MinecraftToolkitSetup.exe` 執行。它會檢查環境、下載 Paper、開啟 RCON、寫好 `config.json`、註冊排程工作、建立防火牆規則和桌面捷徑。

需要系統管理員權限（防火牆規則要）。

自行建置：

```bash
pip install pyinstaller
python installer/build_exe.py
```

### 手動安裝

完整的逐步流程（含 playit 對外開放、基岩版互通、網頁地圖、Discord bot、排程自動化）在 **[docs/INSTALL.md](docs/INSTALL.md)**。

下面是最短路徑：

**1. 複製設定範本**

```bash
copy config.example.json config.json
```

**2. 填入你的資訊**

`config.json` 裡最少要填 `serverDir`、`backupDir`、`java.host`、`bedrock.host`。用不到的功能（Discord、Cloudflare）整段留空即可。

**3. 開啟 RCON**

在伺服器的 `server.properties`：

```properties
enable-rcon=true
rcon.port=25575
rcon.password=挑一個長一點的密碼
```

**4. 確認可以連上**

```bash
python scripts/check-server.py
```

**5. 啟動內網控制台**

```bash
python scripts/web-console.py
```

啟動時會印出網址與控制權杖。權杖存在 `web-console.config.json`，刪掉該欄位重啟就會產生新的。

要讓區網其他裝置連得到，需要一條防火牆規則（**要系統管理員權限**）：

```powershell
New-NetFirewallRule -DisplayName 'MC Web Console (LAN)' -Direction Inbound `
  -Protocol TCP -LocalPort 8099 -RemoteAddress LocalSubnet -Action Allow `
  -Profile Private,Domain
```

---

## 安全性

這套東西能關伺服器、能執行任意主控台指令。設計上有三層：

1. **內網位址檢查** — 明確列舉 `127/8`、`10/8`、`172.16/12`、`192.168/16`、`169.254/16`、`::1`、`fc00::/7`、`fe80::/10`。刻意不用 `ipaddress.is_private`，因為它把 `203.0.113.0/24` 這類文件網段也算成私有。
2. **控制權杖** — 只有會改變狀態的動作需要；純看狀態不用，手機拿起來就能看。
3. **防火牆規則** 限定 LocalSubnet。

所有會改變狀態的動作都會記進 `web-console.log`，含來源 IP。

**絕對不要幫控制台的埠開 playit 或任何內網穿透隧道。** 穿透工具的 agent 是從 `127.0.0.1` 連進本機服務的，會通過內網位址檢查——等於把管理頁面直接送上公網，只剩權杖擋著。

機密一律放在 repo 外的檔案，由 `config.json` 用路徑指向：Discord bot token、Cloudflare API token 都是這樣處理。`config.json` 本身也在 `.gitignore` 裡，因為它帶著你的網域和 ID。

---

## 排程工作

`windows/` 底下的腳本設計成由 Windows 工作排程器呼叫。建議的組合：

| 工作 | 觸發 | 執行 |
|---|---|---|
| 看門狗 | 每 5 分鐘 | `powershell -WindowStyle Hidden -File watchdog.ps1` |
| 世界備份 | 每天 04:00 | `powershell -WindowStyle Hidden -File backup-world.ps1` |
| 排程重啟 | 每天，重啟時間前 5 分鐘 | `pythonw restart-sequence.py` |
| Discord bot | 登入時 | `pythonw discord-control.py` |
| 內網控制台 | 登入時 | `pythonw web-console.py` |

用 `pythonw` 和 `-WindowStyle Hidden` 是有原因的：不加的話每次觸發都會在畫面上彈一個主控台視窗。看門狗每 5 分鐘一次，玩遊戲時會被打斷到想砸鍵盤。

---

## 踩過的坑

這些都是實際debug出來的，寫在這裡省下重蹈覆轍的時間。

**背景程式每叫一個主控台程式就開一個新視窗。** `pythonw.exe` 自己沒有主控台，所以它 `subprocess` 出去的每個 console 程式都會拿到一個新視窗。所有 `subprocess` 呼叫都要帶 `creationflags=CREATE_NO_WINDOW`。

**`Start-Process -ArgumentList` 不會替含空白的元素加引號。** `'/c','start','MC Server','/min',$bat` 送到 cmd 會變成 `start MC Server /min ...`，`start` 把 `MC` 當視窗標題、去執行一個叫 `Server` 的東西，批次檔根本沒被叫到——而且完全無聲。要寫成 `'"MC Server"'`。

**含中文的 `.ps1` 必須存成 UTF-8 with BOM。** Windows PowerShell 5.1 把沒有 BOM 的檔案當成系統 ANSI 編碼讀，某些中文字的第二個位元組會吃掉後面的大括號，然後報 `MissingEndCurlyBrace` 並指向一行完全正確的程式碼。

**`.bat` 必須是純 ASCII 且 CRLF 換行。** cmd.exe 用 OEM 編碼讀批次檔，UTF-8 中文註解會讓後續指令被切碎後當成指令執行。LF 換行會讓多行 `if (...)` 區塊失效。

**Windows 的受控資料夾存取會無聲擋掉寫入。** 預設保護 `Documents`、`Pictures`、`Desktop`。伺服器或工具的工作目錄放在那底下，會出現「沒有錯誤訊息但程式就是死掉或卡住」。把東西放到那些資料夾之外。

**伺服器會把結構模板快取在記憶體。** 改了磁碟上的 `.nbt` 之後，同一個 ID 仍然沿用舊版；換檔名或重啟才會生效。

---

## 藍圖轉換器

```bash
python scripts/litematic2structure.py 藍圖.litematic 輸出目錄 --prefix 名稱
```

Litematica 逐塊放置且不管相依順序，鐵軌會在底下的方塊還沒放好就先放然後掉下來；更糟的是走 WorldEdit `//set` 的放置**不會寫入容器內容物**，全物品分類器的過濾漏斗會全空，機器不動而且不報錯。

結構方塊是整批放置、不觸發方塊更新，而且帶得動容器內容。轉換器保留原始 NBT 標籤型別（物品堆疊的 `Slot` 是 TAG_Byte，寫成 int 容器就會被當成空的）、保留實體與方塊實體，並且把空氣一起寫進去（結構只會放置它列出的方塊，漏掉空氣就會讓機器被原地形埋住）。

超過 48×48×48 會自動切片，並印出每片該放的相對座標。

輸出目錄是 `<世界>/generated/minecraft/structure/`（**單數** `structure`）。

---

## 授權

MIT
