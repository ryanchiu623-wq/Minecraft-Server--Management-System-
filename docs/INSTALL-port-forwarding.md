# 完整安裝流程（路由器轉埠版）

跟 [INSTALL.md](INSTALL.md) 是同一套流程，差別只在**怎麼讓外面連進來**：這份用你自己的路由器轉埠，不經過第三方隧道。

**兩份只需要看一份。** 先用下面的表決定看哪一份：

| | 路由器轉埠（本文件） | playit 隧道（[INSTALL.md](INSTALL.md)） |
|---|---|---|
| 需要公網 IP | **必須** | 不用 |
| 需要動路由器 | 要 | 不用 |
| 延遲 | 直連，最低 | 多一段中轉 |
| 你家 IP 是否曝光 | **會** | 不會 |
| DDoS 防護 | 沒有 | 隧道商吸收 |
| 連線位址 | 你的網域或 IP | 隧道商給的位址 |
| 成本 | 免費 | 免費（付費版有固定位址） |

**台灣的家用寬頻很多是 CGNAT，轉埠不可能成功**——這種情況只能用 playit 版。第 3.0 節教你怎麼判斷，**請務必先做那一步再往下**。

第 1、2、7 部分是必要的，其餘可按需要跳過。每一部分結尾都有驗證步驟——做完就驗，不要一路裝到底再回頭找哪裡壞了。

---

## 0. 需求

| 項目 | 版本 | 說明 |
|---|---|---|
| Windows | 10 / 11 | |
| Java | 21 以上 | Paper 1.21+ 的最低要求 |
| Python | 3.10 以上 | 用安裝程式的話不需要 |
| 網路 | **要有公網 IP** | 見第 3.0 節 |
| 路由器 | 能自己登入設定 | 電信商的機器通常也可以，密碼在機身貼紙上 |

安裝 Java 和 Python 時**記得勾「Add to PATH」**。

### 先處理受控資料夾存取

Windows Defender 的「受控資料夾存取」預設保護 `Documents`、`Pictures`、`Desktop`，而且**擋掉寫入時完全不會報錯**——伺服器會莫名其妙死掉、工具會永遠卡住，你完全查不到原因。

```powershell
(Get-MpPreference).EnableControlledFolderAccess
```

回傳 `1` 就是開著。**不要關掉它**，改成把東西裝在那些資料夾之外：

```
C:\mc-paper      伺服器
C:\mc-backup     備份
C:\mc-toolkit    這套工具
```

---

## 1. 把伺服器跑起來

跟 playit 版完全相同。

### 1.1 下載 Paper

到 <https://papermc.io/downloads/paper> 抓最新版，存成 `C:\mc-paper\paper.jar`。

### 1.2 第一次啟動

```bash
cd C:\mc-paper
java -jar paper.jar nogui
```

會產生 `eula.txt` 然後結束。編輯它把 `eula=false` 改成 `eula=true`，再跑一次，等世界產生完成後輸入 `stop`。

### 1.3 開啟 RCON

RCON 是 toolkit 跟伺服器溝通的唯一管道，**沒開的話後面所有功能都不會動**。編輯 `C:\mc-paper\server.properties`：

```properties
enable-rcon=true
rcon.port=25575
rcon.password=換成一串你自己的長密碼
server-port=25565
```

> **RCON 埠（25575）絕對不要轉出去。** 那是完整的主控台權限，只有一層密碼。只轉遊戲用的 25565。

### ✅ 驗證

```bash
cd C:\mc-toolkit
python scripts\rcon.py "list"
```

看到 `There are 0 of a max of 20 players online:` 就成功了。

---

## 2. 安裝 toolkit

```bash
git clone https://github.com/ryanchiu623-wq/Minecraft-Server--Management-System-.git C:\mc-toolkit
cd C:\mc-toolkit
copy config.example.json config.json
```

編輯 `config.json`，先填這四個：

```json
{
  "serverDir": "C:\\mc-paper",
  "backupDir": "C:\\mc-backup",
  "startBat": "C:\\mc-paper\\start.bat",
  "keepBackups": 7
}
```

路徑要用雙反斜線 `\\`，這是 JSON 的規則。

把啟動腳本複製過去：

```bash
copy windows\start.bat C:\mc-paper\
```

> `start.bat` 裡有啟動 playit 的段落。用轉埠的話那幾行會因為找不到服務而靜靜跳過，不影響運作；介意的話可以把 `sc start playitd` 那行刪掉。

---

## 3. 對外開放（路由器轉埠）

### 3.0 先確認你有公網 IP

**這是整份文件最重要的一步。** 如果你在電信商的 CGNAT 後面，轉埠**不可能**成功——不是設定錯誤，是物理上做不到，因為那個公網 IP 是幾百個用戶共用的，你的路由器沒有權限決定它的通訊埠要送給誰。

判斷方法：**比對兩個 IP**。

**A. 路由器上的 WAN IP** —— 登入路由器管理頁面，找「WAN 狀態」「網際網路」「連線資訊」之類的頁面，記下它顯示的對外 IP。

**B. 外界看到的 IP** —— 在瀏覽器開 <https://api.ipify.org>，或：

```powershell
(Invoke-WebRequest -Uri https://api.ipify.org -UseBasicParsing).Content
```

**兩個一樣** → 你有公網 IP，可以繼續。

**兩個不一樣** → 你在 CGNAT 後面，**轉埠不會有用**，請改用 [INSTALL.md](INSTALL.md) 的 playit 版。

另外，路由器的 WAN IP 如果落在這些網段，也是 CGNAT，不用比對就可以確定：

| 網段 | |
|---|---|
| `100.64.0.0/10` | CGNAT 專用（RFC 6598），最常見 |
| `10.0.0.0/8` | 私有 |
| `172.16.0.0/12` | 私有 |
| `192.168.0.0/16` | 私有 |

> **只查「我的 IP 是什麼」是沒有用的。** 那種網站在 CGNAT 後面一樣會回你一個公網位址——那是電信商的，不是你的。一定要跟路由器上顯示的 WAN IP 比對才有意義。

> **雙重 NAT**：有些人的環境是「電信商數據機 + 自己的路由器」兩層。這種情況兩台都要轉埠，或是把數據機改成橋接模式。先確認你設定的是最外層那台。

### 3.1 固定伺服器電腦的內網 IP

轉埠是把外面的連線指到一個**內網 IP**。如果那台電腦的 IP 會變（DHCP 預設會），某天重開機之後轉埠就指向別人了。

查目前的內網 IP：

```powershell
Get-NetIPConfiguration | Where-Object { $_.NetProfile.IPv4Connectivity -eq 'Internet' } |
  Select-Object InterfaceAlias, IPv4Address, IPv4DefaultGateway
```

固定方法二選一，**建議用第一種**：

**A. 路由器的 DHCP 保留（推薦）** —— 在路由器裡找「DHCP 保留」「靜態 DHCP」「Address Reservation」，把這台電腦的 MAC 位址綁定到一個固定 IP。好處是電腦端不用改任何設定，換網路環境也不會出問題。

**B. 電腦端設固定 IP** —— Windows 設定 → 網路 → 編輯 IP 指派 → 手動。要自己填 IP、子網路遮罩、閘道、DNS，填錯會整台上不了網。

### 3.2 在路由器上轉埠

管理頁面裡找「連接埠轉發」「Port Forwarding」「虛擬伺服器」「NAT 設定」。不同廠牌名稱不一樣，通常在「進階」底下。

新增兩條規則：

| 用途 | 通訊協定 | 外部埠 | 內部 IP | 內部埠 |
|---|---|---|---|---|
| Minecraft Java | **TCP** | 25565 | 你的伺服器內網 IP | 25565 |
| Minecraft 基岩版 | **UDP** | 19132 | 同上 | 19132 |

**通訊協定不能選錯**：Java 版是 TCP，基岩版是 UDP。有些路由器有「TCP/UDP 兩者」的選項，選那個也可以。

不玩基岩版的話第二條可以不建。

> **只轉這兩個埠。** 不要為了省事開 DMZ（把整台電腦暴露出去），那等於把你電腦上所有服務都放上公網。也不要轉 RCON 的 25575。

### 3.3 Windows 防火牆

轉埠只是讓路由器願意送過來，Windows 這邊還要願意收。**用系統管理員身分開 PowerShell**：

```powershell
New-NetFirewallRule -DisplayName 'Minecraft Java' -Direction Inbound `
  -Protocol TCP -LocalPort 25565 -Action Allow -Profile Private,Domain

New-NetFirewallRule -DisplayName 'Minecraft Bedrock' -Direction Inbound `
  -Protocol UDP -LocalPort 19132 -Action Allow -Profile Private,Domain
```

規則掛在 Private 和 Domain，所以你的網路類別必須是「私人」：

```powershell
Get-NetConnectionProfile
```

顯示 `Public` 的話規則不會生效，到 Windows 設定把該網路改成「私人網路」。

> 有人會建議加上 `-Profile Any` 或連 Public 一起開。**不要**——那會讓你在咖啡廳連公用 Wi-Fi 時也開著這些埠。

### 3.4 綁自己的網域

沒有網域的話，朋友直接用你的公網 IP 連也可以，跳過這節。但家用寬頻的 IP 通常會變（斷線重連、電信商重新配發），**所以強烈建議綁網域**，IP 變了只要改一筆記錄。

用 Cloudflare 管理 DNS 的話：

| 類型 | 名稱 | 內容 | Proxy |
|---|---|---|---|
| A | `mc` | 你的公網 IP | **DNS only（灰雲）** |
| A | `bedrock` | 你的公網 IP | **DNS only（灰雲）** |

**Proxy 一定要關（灰雲）。** 橘雲是 HTTP 代理，Minecraft 的協定過不去。

因為外部埠就是標準的 25565，**不需要 SRV 記錄**，玩家直接打 `mc.你的網域` 就會連到。（這點比 playit 版單純，playit 給的埠不是 25565，所以那邊要靠 SRV 隱藏埠號。）

**IP 會變怎麼辦** —— 用動態 DNS。Cloudflare 有 API 可以寫個小腳本定時更新，或用 No-IP、DuckDNS 這類免費服務（它們提供一個 Windows 客戶端，IP 變了自動更新）。判斷你的 IP 會不會變，最簡單的方法是隔幾天再查一次 <https://api.ipify.org>。

### ✅ 驗證

**先從外部確認埠真的通了**，不要用自己家的網路測——很多路由器不支援從內部連自己的公網 IP（NAT 回環），會讓你誤判成失敗。

用手機關掉 Wi-Fi 走行動網路，或用線上工具：

- <https://mcsrvstat.us> 輸入你的網域或 IP
- 或任何「port checker」網站，測 TCP 25565

然後：

```bash
python scripts\check-server.py
```

DNS 那一層要顯示你的網域指到你的公網 IP，外部視角那一層要通過。

---

## 3.5 安全性：轉埠跟隧道的差別

這節在 playit 版沒有，因為那些風險是隧道商幫你擋掉的。用轉埠就得自己面對。

**你家的 IP 會公開。** 任何連進來的人、任何查你網域的人都看得到。IP 可以查到大致地理位置和你的 ISP。介意的話用 playit 版。

**你會被掃描，而且是持續的。** 這不是危言聳聽——我們在隧道那側實際量測過：18 小時內單一掃描機器人連了 **906 次**，佔全部連線的 99.3%。暴露在公網的 Minecraft 埠一定會被找到。轉埠的話這些連線是直接打到你家的線路。

**沒有 DDoS 防護。** 家用寬頻沒有任何緩衝，被打就是整條線路不能用，連家人上網都會受影響。隧道商有基本的吸收能力。

實務上該做的：

- **開白名單**。這是最有效的一招。只有名單上的人能進來，掃描機器人再多也沒用。
  ```bash
  python scripts\rcon.py "whitelist on" "whitelist add 朋友的ID"
  ```
- **保持 Paper 更新**。伺服器軟體的漏洞是真的存在的。
- **`online-mode=true`**（預設值，不要改）。改成 false 任何人都能冒充任何帳號。
- **RCON 埠不要轉出去**，前面說過了。
- 覺得被針對的話，路由器通常有「封鎖 IP」的功能，把來源擋掉。

---

## 4. 基岩版互通

讓手機、平板、主機版的朋友連進來。**他們不需要 Java 版帳號。**

> 用安裝程式的話這節可以跳過。

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

再重新啟動一次。

### 4.3 更新 config.json

```json
"bedrock": {
  "host": "bedrock.你的網域",
  "tunnelPort": 19132,
  "localPort": 19132
}
```

**這裡跟 playit 版不一樣**：playit 會給你一個奇怪的公開埠，轉埠版的對外埠就是 19132，兩個欄位填一樣的值。基岩版玩家在遊戲裡也填 19132。

### ✅ 驗證

```bash
python scripts\check-server.py
```

「基岩」那兩層都要通過。

---

## 5. 網頁地圖

跟 playit 版完全相同，照 [INSTALL.md 第 5 節](INSTALL.md#5-網頁地圖)做。

重點：BlueMap 產生靜態網頁，推到 Cloudflare Pages 託管。**不要為了地圖再轉一個埠出去**——那會多一個對外的攻擊面，而且地圖網頁會直接曝光你家 IP 給每個看地圖的人。用靜態託管就沒這個問題。

> Cloudflare Pages 的壓縮要關掉。BlueMap 的瓷磚已經壓過，再壓一層瀏覽器解不開，地圖會一片空白。

---

## 6. Discord 遙控

跟 playit 版完全相同，照 [INSTALL.md 第 6 節](INSTALL.md#6-discord-遙控)做。

> **絕對不要把 bot token 貼進聊天室、截圖或指令列。** 一旦外流，任何人都能用你的 bot。不小心外流就回開發者頁面 Reset Token。

---

## 7. 內網控制台

```bash
python scripts\web-console.py
```

啟動時會印出網址和控制權杖。權杖存在 `web-console.config.json`。

防火牆規則（**要系統管理員權限**）：

```powershell
New-NetFirewallRule -DisplayName 'MC Web Console (LAN)' -Direction Inbound `
  -Protocol TCP -LocalPort 8099 -RemoteAddress LocalSubnet -Action Allow `
  -Profile Private,Domain
```

注意 `-RemoteAddress LocalSubnet`——這條跟第 3.3 節的遊戲埠不同，**只允許同一個區網**。

> **絕對不要把 8099 轉出去。** 這個頁面能關伺服器、能執行任意主控台指令。它的內網位址檢查會擋掉外部來源，但轉埠出去等於主動把管理介面放上公網，只剩權杖擋著。要在外面管理伺服器就用 Discord 機器人。

---

## 8. 排程自動化

跟 playit 版完全相同，照 [INSTALL.md 第 8 節](INSTALL.md#8-排程自動化)做。

用 `pythonw` 和 `-WindowStyle Hidden`，不然每次觸發都會彈主控台視窗，看門狗每 5 分鐘一次會很煩。長時間執行的工作記得把「執行時間上限」設成無限。

---

## 9. 最終驗證

```bash
python scripts\check-server.py
```

由上往下排，**下層的問題通常是上層造成的，從最上面的失敗項開始查**：

```
本機      伺服器程序本身活著嗎
DNS       網域指到你的公網 IP 嗎
隧道      這一層轉埠版意義不同，見下方
外部視角  第三方檢測服務看得到嗎
網頁地圖  地圖站台回應嗎
```

> **「隧道」那一層在轉埠版可以忽略。** 它是設計來檢查 playit 的；轉埠的話真正有意義的是「外部視角」那層。

最後叫朋友實際連連看——**外部檢測通過不等於玩家真的進得來**。

---

## 疑難排解

### 轉埠特有的

**外部檢測說連不到，但伺服器明明開著**

照順序排除：

1. **你在 CGNAT 後面**（第 3.0 節）。最常見，而且怎麼設定都沒用。
2. **內網 IP 變了**，轉埠指到別台機器。查一次目前的 IP 跟路由器上填的是否一致，然後做 DHCP 保留。
3. **Windows 防火牆沒開**，或網路類別是「公用」導致規則沒生效。
4. **雙重 NAT**，最外層那台沒設定。
5. **ISP 封鎖**。少數電信商會擋常見的服務埠，可以試著把外部埠改成別的（例如外部 25566 → 內部 25565，玩家連的時候要加 `:25566`）。

**自己連 `你的網域:25565` 連不進去，但朋友可以**

正常。很多路由器不支援 NAT 回環（從內部連自己的公網 IP）。在自己家裡就用內網 IP 連，例如 `192.168.1.50`。

**昨天還好好的，今天朋友連不進來**

你的公網 IP 變了。查 <https://api.ipify.org> 跟 DNS 上的記錄是否一致。這就是第 3.4 節建議綁網域和動態 DNS 的原因。

**基岩版連不進來但 Java 版可以**

基岩版走 UDP，轉埠規則的通訊協定選成 TCP 的話就會這樣。回去確認 19132 那條是 UDP。

### 通用的

**東西沒有錯誤訊息就死掉／卡住**
先查受控資料夾存取（第 0 節）。它擋掉寫入時完全無聲，症狀會指向完全錯誤的方向。

**`.bat` 執行到一半噴出亂碼指令**
批次檔必須是**純 ASCII 且 CRLF 換行**。cmd.exe 用 OEM 編碼讀，UTF-8 中文註解會讓後續指令被切碎後當成指令執行。

**`.ps1` 報 `MissingEndCurlyBrace`，但那一行明明是對的**
含中文的 PowerShell 腳本必須存成 **UTF-8 with BOM**。用這個驗證，不要用肉眼看：

```powershell
$e=$null; [void][System.Management.Automation.Language.Parser]::ParseFile('檔案路徑',[ref]$null,[ref]$e); $e
```

**排程工作每次觸發都彈視窗**
用 `pythonw` 取代 `python`，PowerShell 加 `-WindowStyle Hidden`。自己寫的腳本裡所有 `subprocess` 呼叫都要帶 `creationflags=CREATE_NO_WINDOW`。

**伺服器沒人時 RCON 指令會逾時**
Paper 有「閒置時暫停」機制（日誌會出現 `Server empty for 60 seconds, pausing`）。大批次的 RCON 指令這時候容易斷線，分小步下比較穩。

**地圖網頁一片空白**
Cloudflare Pages 的壓縮要關掉。
