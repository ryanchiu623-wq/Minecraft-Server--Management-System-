# 完整安裝流程

**繁體中文** · [English](INSTALL.en.md)

從一台什麼都沒有的 Windows 機器，到一個朋友連得進來、會自己備份、當機會自己爬起來的 Minecraft 伺服器。

**這份用 playit 隧道對外開放**，不需要公網 IP、不用動路由器。如果你有公網 IP 而且想要直連（延遲較低），改看 [INSTALL-port-forwarding.md](INSTALL-port-forwarding.md)。兩份只需要看一份。

第 1、2、7 部分是必要的，其餘可以按需要跳過。每一部分結尾都有驗證步驟——**做完就驗，不要一路裝到底再回頭找哪裡壞了**。

| 部分 | 內容 | 必要性 |
|---|---|---|
| [0](#0-需求) | 需求 | 必要 |
| [1](#1-把伺服器跑起來) | Paper 伺服器 + RCON | 必要 |
| [2](#2-安裝-toolkit) | 安裝 toolkit | 必要 |
| [3](#3-對外開放) | 對外開放（playit + 網域） | 選用 |
| [4](#4-基岩版互通) | 基岩版互通（Geyser） | 選用 |
| [5](#5-網頁地圖) | 網頁地圖（BlueMap） | 選用 |
| [6](#6-discord-遙控) | Discord 遙控 | 選用 |
| [7](#7-內網控制台) | 內網控制台 | 必要 |
| [8](#8-排程自動化) | 排程自動化 | 建議 |
| [9](#9-最終驗證) | 最終驗證 | 必要 |

---

## 0. 需求

| 項目 | 版本 | 說明 |
|---|---|---|
| Windows | 10 / 11 | |
| Java | 21 以上 | Paper 1.21+ 的最低要求。本專案開發時用 26.0.1 |
| Python | 3.10 以上 | 開發時用 3.14 |
| 記憶體 | 建議 8 GB 以上 | 伺服器本身配 4 GB 綽綽有餘 |

安裝 Java 和 Python 時**記得勾「Add to PATH」**。裝完開一個新的終端機確認：

```bash
java -version
python --version
```

### 先處理受控資料夾存取

Windows Defender 的「受控資料夾存取」預設保護 `Documents`、`Pictures`、`Desktop`，而且**擋掉寫入時完全不會報錯**——伺服器會莫名其妙死掉、工具會永遠卡住，你完全查不到原因。

```powershell
(Get-MpPreference).EnableControlledFolderAccess
```

回傳 `1` 就是開著。**不要關掉它**，改成把伺服器裝在那些資料夾之外：

```
C:\mc-paper      伺服器
C:\mc-backup     備份
C:\mc-toolkit    這套工具
```

本文件後面都用這組路徑。

---

## 1. 把伺服器跑起來

### 1.1 下載 Paper

到 <https://papermc.io/downloads/paper> 抓最新版，存成 `C:\mc-paper\paper.jar`。

### 1.2 第一次啟動

```bash
cd C:\mc-paper
java -jar paper.jar nogui
```

會產生 `eula.txt` 然後結束。編輯它：

```properties
eula=true
```

再跑一次，等世界產生完成後在主控台輸入 `stop`。

### 1.3 開啟 RCON

RCON 是 toolkit 跟伺服器溝通的唯一管道，**沒開的話後面所有功能都不會動**。編輯 `C:\mc-paper\server.properties`：

```properties
enable-rcon=true
rcon.port=25575
rcon.password=換成一串你自己的長密碼
```

密碼隨便打一串長的就好，你不需要記得——toolkit 會自己從這個檔案讀。

改完重新啟動伺服器。

### ✅ 驗證

另開一個終端機：

```bash
cd C:\mc-toolkit
python scripts\rcon.py "list"
```

看到 `There are 0 of a max of 20 players online:` 就成功了。

失敗的話依序檢查：伺服器有沒有在跑、`enable-rcon` 是不是 `true`、密碼有沒有前後空白。

---

## 2. 安裝 toolkit

```bash
git clone https://github.com/你的帳號/你的repo.git C:\mc-toolkit
cd C:\mc-toolkit
copy config.example.json config.json
```

編輯 `config.json`。**現在只要填這四個**，其餘留著之後填：

```json
{
  "serverDir": "C:\\mc-paper",
  "backupDir": "C:\\mc-backup",
  "startBat": "C:\\mc-paper\\start.bat",
  "keepBackups": 7
}
```

路徑要用雙反斜線 `\\`，這是 JSON 的規則。

把啟動腳本複製到伺服器目錄：

```bash
copy windows\start.bat C:\mc-paper\
```

### ✅ 驗證

```bash
python scripts\rcon.py "list"
```

跟 1.3 一樣要能回應。這次它是透過 `config.json` 找到伺服器目錄的。

---

## 3. 對外開放

家用網路多半在 NAT 後面（甚至是電信商的雙重 NAT），沒有固定 IP，也不能開 port forwarding。用 [playit.gg](https://playit.gg) 打通，免費而且不用動路由器。

### 3.1 安裝 playit

到 <https://playit.gg> 註冊，下載 Windows 版安裝。它會裝成一個系統服務 `playitd`，開機自動啟動。

第一次執行會給你一個網址去綁定帳號。

### 3.2 建立隧道

在 playit 網頁後台建立：

| 類型 | 通訊協定 | 指向本機 |
|---|---|---|
| Minecraft Java | TCP | `127.0.0.1:25565` |
| Minecraft Bedrock | UDP | `127.0.0.1:19132` |

建好之後會拿到類似 `something.tun.ply.gg:12345` 的公開位址。

> **後台顯示「線上」不代表真的通。** playit 後台的狀態只反映它自己有沒有連上，不保證流量真的到得了你的機器。真正的判斷依據是 agent 的日誌（`C:\ProgramData\playit_gg\logs\playitd.log`）和第 9 部分的外部檢測。
>
> 遇到後台一切正常但就是連不進來時，**刪掉 agent 和隧道重新建立**往往是唯一有效的解法。

### 3.3 綁自己的網域（選用）

用 Cloudflare 管理 DNS 的話：

| 類型 | 名稱 | 內容 | Proxy |
|---|---|---|---|
| A | `mc` | playit 給的 IP | **DNS only（灰雲）** |
| SRV | `_minecraft._tcp.mc` | 優先權 0、權重 0、埠 `<playit 的埠>`、目標 `mc.你的網域` | — |
| A | `bedrock` | playit 給的 IP | **DNS only（灰雲）** |

有 SRV 記錄的話，Java 版玩家只要打 `mc.你的網域`，不用加埠號。

**三個坑：**

- **Proxy 一定要關（灰雲）。** 橘雲是 HTTP 代理，Minecraft 的協定過不去。
- **不要建 AAAA 記錄。** playit 會公告 IPv6 位址但不會真的把 IPv6 流量送到 agent，玩家會拿到 `Connection timed out: getsockopt`。整條 DNS 鏈路只用 IPv4。
- **Cloudflare 的 SRV「目標」欄位不要用貼的。** 從別處複製常常帶進看不見的字元，會出現 `Data field "target" contains non-printable characters`。手動打。

### ✅ 驗證

```bash
python scripts\check-server.py
```

DNS 那一層要顯示你的網域指到 playit 的 IP。

---

## 4. 基岩版互通

讓手機、平板、主機版（基岩版）的朋友連進 Java 版伺服器。**他們不需要有 Java 版帳號。**

> 用安裝程式的話這一節可以跳過——它會自動下載 Geyser 和 Floodgate，並在 Geyser 設定檔存在時把 `auth-type` 改成 `floodgate`。

### 4.1 安裝外掛

兩個 jar 都放進 `C:\mc-paper\plugins\`：

- **Geyser**（Spigot 版）—— <https://geysermc.org/download>
- **Floodgate**（Spigot 版）—— 同一頁

Geyser 負責協定轉換，**Floodgate 才是讓沒有 Java 帳號的人能進來的關鍵**。只裝 Geyser 的話，基岩版玩家仍然需要一個 Java 版帳號。

重新啟動伺服器讓它產生設定檔。

### 4.2 設定

`plugins\Geyser-Spigot\config.yml`：

```yaml
bedrock:
  port: 19132
remote:
  auth-type: floodgate
```

`auth-type` 一定要是 `floodgate`。

再重新啟動一次。

### 4.3 更新 config.json

```json
"bedrock": {
  "host": "bedrock.你的網域",
  "tunnelPort": 你的playit UDP埠,
  "localPort": 19132
}
```

`tunnelPort` 是 playit 給的公開埠，**通常不是 19132**。基岩版玩家在遊戲裡要填這個埠。

### ✅ 驗證

```bash
python scripts\check-server.py
```

「基岩」那兩層都要通過。也可以直接叫朋友試連。

---

## 5. 網頁地圖

用 BlueMap 產生 3D 網頁地圖，再推到 Cloudflare Pages 靜態託管——**這樣不用再開第三條隧道**，也不會有人透過地圖網頁打到你家的 IP。

### 5.1 安裝 BlueMap

把 `bluemap-x.y-paper.jar` 放進 `plugins\`，重啟，它會開始算圖（大地圖要跑很久）。

### 5.2 設定 Cloudflare Pages

```bash
npm install -g wrangler
wrangler login
wrangler pages project create 你的專案名
```

把 Cloudflare API token 存成一個純文字檔，**放在 repo 外面**，例如 `C:\Users\你\.secrets\cloudflare-token.txt`。

### 5.3 更新 config.json

```json
"mapUrl": "https://你的專案名.pages.dev",
"cloudflare": {
  "projectName": "你的專案名",
  "accountId": "你的 account ID",
  "tokenFile": "C:\\Users\\你\\.secrets\\cloudflare-token.txt",
  "webDir": "C:\\mc-paper\\bluemap\\web"
}
```

### ✅ 驗證

```bash
powershell -ExecutionPolicy Bypass -File windows\sync-map.ps1
```

跑完之後開 `mapUrl` 應該看得到地圖。

> **不要在 Cloudflare Pages 開壓縮。** BlueMap 的瓷磚已經是壓縮過的，再壓一層瀏覽器會解不開，地圖一片空白。

---

## 6. Discord 遙控

在外面用手機就能開關伺服器、看狀態、下指令。

### 6.1 建立 bot

1. 到 <https://discord.com/developers/applications> 建立 Application
2. 左側 **Bot** → Add Bot → Reset Token → **把 token 存成純文字檔放在 repo 外面**
3. 同一頁把 **Message Content Intent** 打開
4. 左側 **OAuth2 → URL Generator** → 勾 `bot` 和 `applications.commands` → 用產生的網址把 bot 邀進你的伺服器

> **絕對不要把 token 貼進聊天室、截圖或指令列。** 一旦外流，任何人都能用你的 bot。不小心外流就回開發者頁面 Reset Token。

### 6.2 取得 ID

Discord 設定 →「進階」→ 開啟**開發者模式**。之後右鍵任何使用者或頻道都有「複製 ID」。

### 6.3 更新 config.json

```json
"discord": {
  "tokenFile": "C:\\Users\\你\\.secrets\\discord-bot-token.txt",
  "authorizedUserIds": ["你的使用者ID"],
  "rconUserIds": ["你的使用者ID"],
  "logChannelId": "要接收事件通知的頻道ID"
}
```

`rconUserIds` 是獨立的一份名單，因為 RCON 等於完整的伺服器控制權。留空的話會沿用 `authorizedUserIds`。

### 6.4 安裝與啟動

```bash
pip install discord.py
python scripts\discord-control.py
```

### ✅ 驗證

在 Discord 打 `/status`。要回傳伺服器狀態。

沒看到指令的話，等一兩分鐘讓 Discord 同步，或把 bot 重新邀請一次。

---

## 7. 內網控制台

瀏覽器管理頁面，手機、平板、另一台電腦都能開。

```bash
python scripts\web-console.py
```

啟動時會印出網址和控制權杖。權杖存在 `web-console.config.json`，刪掉那個欄位重啟就會產生新的。

### 7.1 防火牆規則

要讓區網其他裝置連得到，需要一條規則。**用系統管理員身分開 PowerShell**：

```powershell
New-NetFirewallRule -DisplayName 'MC Web Console (LAN)' -Direction Inbound `
  -Protocol TCP -LocalPort 8099 -RemoteAddress LocalSubnet -Action Allow `
  -Profile Private,Domain
```

規則只掛 Private 和 Domain，所以**你的網路類別必須是「私人」**：

```powershell
Get-NetConnectionProfile
```

顯示 `Public` 的話規則不會生效，去 Windows 設定裡把該網路改成「私人網路」。

### 7.2 安全性

這個頁面能關伺服器、能執行任意主控台指令。三層防護：內網位址檢查、控制權杖、防火牆規則。所有會改變狀態的動作都會記進 `web-console.log`，含來源 IP。

> **絕對不要幫 8099 開 playit 或任何內網穿透隧道。** 穿透工具的 agent 是從 `127.0.0.1` 連進來的，會通過內網位址檢查——等於把管理頁面送上公網，只剩權杖擋著。

### ✅ 驗證

手機連同一個 Wi-Fi，開 `http://<你的區網IP>:8099`。

連不上的話：確認防火牆規則建好了、網路類別是私人、路由器沒開 AP isolation（把無線裝置彼此隔開的功能）。

---

## 8. 排程自動化

把備份、看門狗、重啟、機器人都掛上 Windows 工作排程器。

| 工作 | 觸發 | 執行 |
|---|---|---|
| 世界備份 | 每天 04:00 | `powershell -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File C:\mc-toolkit\windows\backup-world.ps1` |
| 看門狗 | 每 5 分鐘 | `powershell -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File C:\mc-toolkit\windows\watchdog.ps1` |
| 排程重啟 | 每天，重啟時間**前 5 分鐘** | `pythonw C:\mc-toolkit\scripts\restart-sequence.py` |
| Discord bot | 登入時 | `pythonw C:\mc-toolkit\scripts\discord-control.py` |
| 內網控制台 | 登入時 | `pythonw C:\mc-toolkit\scripts\web-console.py` |

**每個工作的「起始位置」都要設成 `C:\mc-toolkit`**，否則腳本找不到 `config.json`。

### 為什麼一定要 pythonw 和 -WindowStyle Hidden

不加的話，**每次觸發都會在畫面上彈出一個主控台視窗**。看門狗每 5 分鐘一次，玩遊戲玩到一半被打斷會想砸鍵盤。

同理，長時間執行的工作（bot、控制台）記得把「執行時間上限」設成「無限」，預設 3 天會被排程器砍掉。

### ✅ 驗證

在工作排程器裡對每個工作按「執行」，然後：

- 備份 → `C:\mc-backup` 出現 zip
- 看門狗 → `watchdog.log` 多一行
- bot / 控制台 → 服務起得來

---

## 9. 最終驗證

```bash
python scripts\check-server.py
```

六層由上往下排，**下層的問題通常是上層造成的，所以從最上面的失敗項開始查**：

```
本機      伺服器程序本身活著嗎
DNS       網域指到正確的地方嗎
隧道      從這台打得到公開位址嗎
外部視角  第三方檢測服務看得到嗎
網頁地圖  地圖站台回應嗎
```

全部通過就完成了。

最後叫一個朋友實際連連看——**外部檢測通過不等於玩家真的進得來**。

---

## 疑難排解

以下每一項都是實際 debug 出來的，不是理論。

**東西沒有錯誤訊息就死掉／卡住**
先查受控資料夾存取（見第 0 部分）。它擋掉寫入時完全無聲，症狀會指向完全錯誤的方向。

**`.bat` 執行到一半噴出亂碼指令**
批次檔必須是**純 ASCII 且 CRLF 換行**。cmd.exe 用 OEM 編碼讀，UTF-8 中文註解會讓後續指令被切碎後當成指令執行。LF 換行會讓多行 `if (...)` 區塊失效。

**`.ps1` 報 `MissingEndCurlyBrace`，但那一行明明是對的**
含中文的 PowerShell 腳本必須存成 **UTF-8 with BOM**。Windows PowerShell 5.1 把沒有 BOM 的檔案當系統 ANSI 讀，某些中文字的第二個位元組會吃掉後面的大括號。用這個驗證，不要用肉眼看：

```powershell
$e=$null; [void][System.Management.Automation.Language.Parser]::ParseFile('檔案路徑',[ref]$null,[ref]$e); $e
```

**排程工作每次觸發都彈視窗**
用 `pythonw` 取代 `python`，PowerShell 加 `-WindowStyle Hidden`。另外，**沒有主控台的背景程式每叫一個 console 程式就會開一個新視窗**——自己寫的腳本裡所有 `subprocess` 呼叫都要帶 `creationflags=CREATE_NO_WINDOW`。

**PowerShell 叫 .bat 卻毫無反應**
`Start-Process -ArgumentList` 不會替含空白的元素加引號。`'/c','start','MC Server','/min',$bat` 到了 cmd 會變成 `start MC Server /min ...`——`start` 把 `MC` 當視窗標題、去執行一個叫 `Server` 的東西，批次檔根本沒被叫到，而且完全無聲。要寫成 `'"MC Server"'`。

**基岩版玩家連不進來但 Java 版可以**
基岩版走 UDP，要另一條 playit 隧道。而且公開埠通常不是 19132，玩家在遊戲裡要填 playit 給的那個埠。

**玩家拿到 `Connection timed out: getsockopt`**
多半是 IPv6。playit 會公告 AAAA 但不會把 IPv6 流量送到 agent。刪掉所有 AAAA 記錄。

**伺服器沒人時指令會逾時**
Paper 有「閒置時暫停」機制（日誌會出現 `Server empty for 60 seconds, pausing`）。大批次的 RCON 指令這時候容易斷線，分小步下比較穩。

**地圖網頁一片空白**
Cloudflare Pages 的壓縮要關掉。BlueMap 的瓷磚已經壓過，再壓一層瀏覽器解不開。
