# taoyuan-weather-alert
taoyuan-weather-alert
🌧️ 桃園氣象特報監控系統

使用 GitHub Actions + Python + 中央氣象署 CWA Open Data + Redis + Telegram 建立桃園市氣象特報自動監控系統。

系統會定期查詢中央氣象署氣象特報資料，判斷桃園市是否有新的或變更中的氣象特報，並透過 Redis 保存狀態與 Fingerprint，避免相同特報重複發送 Telegram 通知。
📌 系統功能

    定期查詢中央氣象署 CWA Open Data

    監控桃園市氣象特報

    自動篩選桃園市相關資料

    判斷目前特報狀態

    使用 SHA-256 建立特報 Fingerprint

    使用 Redis 保存目前特報狀態

    避免相同特報重複通知

    新特報自動發送 Telegram

    特報內容變更自動通知

    特報解除自動通知

    第一次啟動時避免因「解除特報」產生不必要通知

    保存第一次發現、最後檢查、最後通知時間

    支援 GitHub Actions 手動執行

    不需要自行維護 n8n Server

🏗️ 系統架構

┌──────────────────────────┐
│      GitHub Actions      │
│                          │
│   每小時自動執行          │
└────────────┬─────────────┘
             │
             ▼
┌──────────────────────────┐
│       CWA Open Data      │
│                          │
│       W-C0033-003        │
│       桃園市氣象特報       │
└────────────┬─────────────┘
             │
             ▼
┌──────────────────────────┐
│       Python Script      │
│                          │
│  解析 API                 │
│  桃園市篩選               │
│  Status 判斷              │
│  Fingerprint              │
└────────────┬─────────────┘
             │
             ▼
┌──────────────────────────┐
│          Redis           │
│                          │
│  讀取上一個狀態            │
│  比較 Fingerprint         │
│  保存目前狀態              │
└────────────┬─────────────┘
             │
             ▼
       ┌─────┴─────┐
       │           │
     相同          不同
       │           │
       ▼           ▼
    不通知       Telegram
                    │
                    ▼
              更新 Redis

📂 專案結構

taoyuan-weather-alert/
│
├── .github/
│   └── workflows/
│       └── weather-alert.yml
│
├── src/
│   └── weather_alert.py
│
├── requirements.txt
│
└── README.md

☁️ 使用資料來源

本系統使用中央氣象署 Open Data：

Resource ID:
W-C0033-003

API：

https://opendata.cwa.gov.tw/api/v1/rest/datastore/W-C0033-003

查詢條件：

format=JSON
CountyName=桃園市
expires=true

主要使用欄位：

senderName
headline
description
effective
onset
expires
web
area

官方 Open Data：

    https://opendata.cwa.gov.tw/

API 文件：

    https://opendata.cwa.gov.tw/devManual/insrtuction

⏰ GitHub Actions 排程

Workflow：

.github/workflows/weather-alert.yml

目前設定為每小時執行一次：

on:
  schedule:
    - cron: "10 * * * *"
      timezone: "Asia/Taipei"

也就是台灣時間：

00:10
01:10
02:10
03:10
...
23:10

另外支援手動執行：

workflow_dispatch:

因此可以在 GitHub：

Actions
    ↓
桃園氣象特報監控
    ↓
Run workflow

手動啟動。
🔐 GitHub Secrets

本系統不會把 API Key、Telegram Token、Redis 密碼直接寫在程式碼中。

請到 GitHub Repository：

Settings
  ↓
Secrets and variables
  ↓
Actions
  ↓
New repository secret

建立以下 Secrets。
1. CWA_API_KEY

中央氣象署 Open Data API 授權碼。

CWA_API_KEY

範例：

CWA-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx

不要把真正的 API Key 提交到 Git。
2. TELEGRAM_BOT_TOKEN

Telegram Bot Token。

TELEGRAM_BOT_TOKEN

格式通常類似：

1234567890:xxxxxxxxxxxxxxxxxxxxxxxx

3. TELEGRAM_CHAT_ID

Telegram 通知目標。

TELEGRAM_CHAT_ID

例如：

8683161103

實際使用時請替換成自己的 Chat ID。
4. REDIS_URL

Redis 連線資訊。

一般 Redis：

redis://default:PASSWORD@HOST:6379/0

TLS Redis：

rediss://default:PASSWORD@HOST:6379/0

建議優先使用 TLS：

rediss://

🔑 Secrets 總覽

CWA_API_KEY
TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID
REDIS_URL

Workflow 會透過：

env:
  CWA_API_KEY: ${{ secrets.CWA_API_KEY }}
  TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
  TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
  REDIS_URL: ${{ secrets.REDIS_URL }}

傳給 Python。
🐍 Python Dependencies

requirements.txt：

requests==2.32.5
redis==6.4.0

主要套件用途：
套件	用途
requests	呼叫 CWA API、Telegram API
redis	Redis 連線與狀態管理

Python 建議版本：

Python 3.12

🔄 Workflow 執行流程

完整流程：

GitHub Actions
      │
      ▼
取得 CWA API
      │
      ▼
解析 records.info
      │
      ▼
確認是否為桃園市
      │
      ├── 否 ──→ 結束
      │
      ▼
建立標準 Alert
      │
      ▼
建立 SHA-256 Fingerprint
      │
      ▼
Redis GET
      │
      ▼
比較舊 Fingerprint
      │
      ├── 相同 ──→ 不通知
      │
      └── 不同
             │
             ▼
        Telegram 通知
             │
             ▼
        Redis SET

🌧️ Alert Status

系統目前使用兩種狀態。
active

代表目前存在有效中的氣象特報。

例如：

大雨特報

第一次發現時會發送 Telegram。
resolved

代表特報已解除。

例如：

解除大雨特報

如果從：

active

變成：

resolved

會發送一次 Telegram。
🔐 Fingerprint 機制

為了避免每小時收到相同的 Telegram 通知，系統會根據以下欄位建立 SHA-256：

areaDesc
headline
description
effective
onset
expires

概念：

CWA Alert
    │
    ▼
重要欄位組合
    │
    ▼
SHA-256
    │
    ▼
Fingerprint

例如：

abc123...

下一次執行：

新 Fingerprint
      │
      ▼
與 Redis 比較

如果：

AAA == AAA

代表特報沒有變化：

Telegram ❌

如果：

AAA != BBB

代表特報發生變化：

Telegram ✅
Redis 更新

🗄️ Redis

目前使用：

weather:alert:taoyuan

Redis 儲存 JSON 狀態。

概念：

{
  "version": 1,
  "area": "桃園市",
  "senderName": "中央氣象署",
  "headline": "大雨特報",
  "description": "...",
  "web": "...",
  "effective": "...",
  "onset": "...",
  "expires": "...",
  "status": "active",
  "fingerprint": "abc123...",
  "firstSeenAt": "...",
  "lastCheckedAt": "...",
  "lastNotifiedAt": "..."
}

🕐 Redis 狀態時間
firstSeenAt

第一次發現這個狀態的時間。

如果後續特報持續存在，不會一直更新。
lastCheckedAt

最近一次 GitHub Actions 檢查時間。

每次成功取得有效資料都會更新。
lastNotifiedAt

最近一次發送 Telegram 的時間。

只有需要通知時才更新。
🔔 通知策略
情況	Redis	Telegram
第一次取得有效特報	無	✅
相同特報再次取得	Fingerprint 相同	❌
新特報	Fingerprint 改變	✅
特報內容更新	Fingerprint 改變	✅
特報解除	Fingerprint 改變	✅
相同解除狀態	Fingerprint 相同	❌
第一次執行且目前已解除	無	❌
API 資料異常	不更新	❌
🚨 第一次執行

第一次執行時 Redis 可能沒有資料。
情況一：目前有有效特報

Redis
  ↓
Empty

CWA
  ↓
active

      ↓

Telegram ✅

      ↓

Redis SET

情況二：目前沒有有效中的特報，而 API 回傳解除狀態

Redis
  ↓
Empty

CWA
  ↓
resolved

      ↓

Telegram ❌

      ↓

Redis SET

這可以避免第一次部署系統時收到不必要的「解除」通知。
🔁 相同特報

例如：

08:10
大雨特報
Fingerprint = AAA

發送：

Telegram ✅

Redis：

AAA

接著：

09:10
大雨特報
Fingerprint = AAA

結果：

Telegram ❌

10:10：

AAA == AAA

結果：

Telegram ❌

11:10：

AAA == AAA

結果：

Telegram ❌

因此相同特報不會每小時重複通知。
🆕 新特報

假設：

舊 Fingerprint:
AAA

CWA 後來發布新的特報：

新 Fingerprint:
BBB

系統判斷：

AAA != BBB

因此：

Telegram ✅

然後：

Redis = BBB

📴 特報解除

例如原本：

大雨特報

變成：

解除大雨特報

Fingerprint 發生變化：

AAA
 ↓
BBB

因此：

Telegram ✅

下一次如果還是：

解除大雨特報
Fingerprint = BBB

則：

Telegram ❌

🛡️ API 錯誤處理

如果 CWA API 找不到：

records.info

系統不會把錯誤資料寫入 Redis。

流程：

CWA API
   │
   ▼
資料異常
   │
   ▼
Normalize Failed
   │
   ▼
不修改 Alert State

這可以避免 API 暫時異常時，把原本正常的警報狀態覆蓋掉。
📱 Telegram 通知格式

目前訊息格式：

🌧️ 桃園市氣象警報通知

📍 地區：桃園市
📢 發布單位：中央氣象署

⚠️ 大雨特報

📝 特報說明

🕐 發布時間：2026-09-25T...
⏰ 結束時間：2026-09-25T...

🔗 詳細資訊：
https://...

資料來源為中央氣象署 API。
🧪 本機測試

如果要在本機執行：
1. 建立虛擬環境

python -m venv .venv

Linux / macOS：

source .venv/bin/activate

Windows：

.venv\Scripts\activate

2. 安裝套件

pip install -r requirements.txt

3. 設定環境變數

Linux / macOS：

export CWA_API_KEY="YOUR_CWA_API_KEY"
export TELEGRAM_BOT_TOKEN="YOUR_TELEGRAM_BOT_TOKEN"
export TELEGRAM_CHAT_ID="YOUR_CHAT_ID"
export REDIS_URL="redis://default:PASSWORD@HOST:6379/0"

Windows PowerShell：

$env:CWA_API_KEY="YOUR_CWA_API_KEY"
$env:TELEGRAM_BOT_TOKEN="YOUR_TELEGRAM_BOT_TOKEN"
$env:TELEGRAM_CHAT_ID="YOUR_CHAT_ID"
$env:REDIS_URL="redis://default:PASSWORD@HOST:6379/0"

4. 執行

python src/weather_alert.py

成功時會看到類似：

============================================================
桃園氣象特報監控
============================================================
[1/5] 取得中央氣象署資料...
[2/5] 正規化氣象特報...
地區: 桃園市
標題: 大雨特報
狀態: active
Fingerprint: abc123...
[3/5] 讀取 Redis 狀態...
Redis 已存在舊狀態
[4/5] 比較特報狀態...
Fingerprint Changed: False
Should Notify: False
[5/5] 特報沒有變化，不發送 Telegram
Redis 狀態已更新: weather:alert:taoyuan
============================================================
完成
============================================================

🚀 GitHub 部署
1. 建立 Repository

例如：

taoyuan-weather-alert

2. 上傳檔案

.github/
└── workflows/
    └── weather-alert.yml

src/
└── weather_alert.py

requirements.txt
README.md

3. 設定 Secrets

GitHub：

Settings
  ↓
Secrets and variables
  ↓
Actions

建立：

CWA_API_KEY
TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID
REDIS_URL

4. 啟用 Actions

進入：

Actions

找到：

桃園氣象特報監控

5. 手動測試

選：

Run workflow

執行後查看：

Actions
  ↓
Workflow
  ↓
Job
  ↓
Run log

🌐 Redis 網路需求

GitHub-hosted runner 執行於 GitHub 的雲端環境。

因此：

GitHub Actions
       │
       │ Internet
       ▼
     Redis

Redis 必須能讓 GitHub runner 連線。

如果目前 Redis 只允許：

localhost
內網
VPN
公司網路
家庭 LAN

GitHub-hosted runner 通常無法直接連線。

可以考慮：

    使用提供 TLS 的雲端 Redis

    使用 Redis Cloud

    使用其他可從 Internet 存取的 Redis

    使用 GitHub self-hosted runner

    透過安全的網路架構讓 runner 存取 Redis

不要直接把 Redis 密碼放在 Python 或 Workflow 檔案中。
🔒 Security

請勿將以下內容提交到 Git：

CWA API Key
Telegram Bot Token
Redis Password
Redis URL

不要寫成：

CWA_API_KEY = "真正的 API KEY"

也不要寫成：

REDIS_URL: redis://user:password@example.com:6379

應使用：

${{ secrets.CWA_API_KEY }}
${{ secrets.TELEGRAM_BOT_TOKEN }}
${{ secrets.TELEGRAM_CHAT_ID }}
${{ secrets.REDIS_URL }}

🧹 .gitignore

建議建立：

.gitignore

內容：

# Python
__pycache__/
*.py[cod]
*.pyo

# Virtual environment
.venv/
venv/
env/

# Environment files
.env
.env.*
!.env.example

# IDE
.vscode/
.idea/

# OS
.DS_Store
Thumbs.db

# Logs
*.log

📈 未來擴充

目前：

桃園市

未來可以擴充成：

桃園
新竹
新北
台北
基隆
台中
彰化
台南
高雄

Redis Key 可以改成：

weather:alert:taoyuan
weather:alert:hsinchu
weather:alert:taipei
weather:alert:newtaipei

或者：

weather:alert:<county>

🗺️ 多縣市架構

             CWA Open Data
                    │
                    ▼
             Python Monitor
                    │
        ┌───────────┼───────────┐
        ▼           ▼           ▼
      桃園          台北          新北
        │           │           │
        ▼           ▼           ▼
     Redis        Redis        Redis
        │           │           │
        ▼           ▼           ▼
    Telegram     Telegram     Telegram

📢 多 Telegram 群組

未來可以根據縣市使用不同 Chat ID：

桃園 → 桃園 Telegram 群組
台北 → 台北 Telegram 群組
新竹 → 新竹 Telegram 群組

例如：

TAOYUAN_TELEGRAM_CHAT_ID
TAIPEI_TELEGRAM_CHAT_ID
HSINCHU_TELEGRAM_CHAT_ID

🚨 不同警報等級

未來可以進一步解析：

severity
urgency
certainty

建立：

一般通知
重要通知
緊急通知

並依不同等級採取不同通知方式。
📊 Dashboard

Redis 已保存：

status
firstSeenAt
lastCheckedAt
lastNotifiedAt
effective
onset
expires
fingerprint

因此未來可以搭配 Dashboard 顯示：

桃園市
──────────────
目前狀態：大雨特報
發布時間：08:30
最後檢查：09:10
最後通知：08:30
預計結束：12:00

🔄 與原 n8n Workflow 的對照

原本 n8n：

Schedule Trigger
      ↓
CWA API
      ↓
Normalize Alert
      ↓
Valid Alert?
      ↓
Redis Get
      ↓
Compare Alert State
      ↓
Alert Changed?
      ↓
Telegram
      ↓
Redis Save

GitHub Actions：

Schedule
      ↓
Python
      ↓
fetch_cwa_alert()
      ↓
normalize_alert()
      ↓
Redis
      ↓
compare_state()
      ↓
send_telegram()
      ↓
Redis SET

核心邏輯保持一致。
🧠 設計原則

本系統的核心不是單純：

查詢 API
    ↓
Telegram

而是：

資料取得
   +
資料正規化
   +
狀態判斷
   +
Fingerprint 去重
   +
Redis 狀態管理
   +
通知

因此即使 GitHub Actions 每小時執行一次，也不會因為排程而每小時重複發送相同警報。
⚠️ 注意事項
GitHub Actions 排程不是即時系統

cron 是週期性執行。

因此：

每小時執行

並不代表氣象特報發布後可以在幾秒內收到通知。

例如：

08:35
CWA 發布新特報

09:10
GitHub Actions 執行

09:10
Telegram 收到通知

如果需要更即時的監控，可以將：

每小時

改成：

每 10 分鐘

甚至：

每 5 分鐘

但需要考量 GitHub Actions 使用量與排程延遲。
🛠️ Troubleshooting
CWA API 錯誤

檢查：

CWA_API_KEY

以及 API 是否可以正常存取。
Telegram 沒收到

檢查：

TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID

並確認 Bot 已經可以對指定 Chat 發送訊息。
Redis Connection Error

檢查：

REDIS_URL

以及：

GitHub Actions runner
        ↓
Internet
        ↓
Redis

是否可以連線。
每次都重複通知

檢查 Redis 是否正常保存：

weather:alert:taoyuan

如果 Redis 每次都是空的：

Redis GET
   ↓
None

系統會把每一次執行都視為第一次執行。
GitHub Actions 沒有自動執行

確認：

Actions

已啟用。

也可以先使用：

Run workflow

手動測試。

另外確認：

on:
  schedule:
    - cron: "10 * * * *"

沒有被修改。
📜 License

本專案程式碼可依自己的需求修改與使用。

CWA 氣象資料則依中央氣象署 Open Data 相關使用規範辦理。
🌦️ Summary

                 CWA Open Data
                       │
                       ▼
                GitHub Actions
                       │
                       ▼
                  Python
                       │
          ┌────────────┴────────────┐
          │                         │
          ▼                         ▼
       Redis                    Telegram
          │                         │
          │                         │
          └────── Alert State ──────┘

系統核心：

CWA
 ↓
資料取得
 ↓
桃園市篩選
 ↓
Fingerprint
 ↓
Redis 狀態比較
 ↓
有變化？
 ├── 否 → 不通知
 └── 是 → Telegram
              ↓
           Redis 更新

GitHub Actions 負責排程，Python 負責監控邏輯，CWA 提供氣象資料，Redis 負責狀態與去重，Telegram 負責通知。
