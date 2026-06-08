# NVIDIA Telegram Bot MVP

這是一個可部署在 Zeabur 的 Telegram bot MVP，使用 NVIDIA NIM 的 OpenAI-compatible API 作為 LLM 後端，並以 Supabase Postgres 儲存對話記憶。

## 已完成的 MVP 範圍

- Telegram polling bot 骨架
- `general` / `career` / `ielts` 三種模式切換
- `general` 通用聊天，可回答任何問題
- `career` 職涯顧問模式
- `ielts_speaking` / `ielts_writing` 練習軌道切換
- `/brief` 半導體晨報（SMH、VOO 持股追蹤）
- 每日定時晨報排程
- Supabase Postgres 對話記憶
- SQLite fallback（本機開發可用）
- health endpoint（`/healthz`）
- `.env` 設定載入
- Docker / Zeabur 部署檔

## Bot 指令

| 指令 | 說明 |
|---|---|
| `/start` | 啟動 bot，顯示目前模式 |
| `/help` | 顯示所有可用指令 |
| `/mode general` | 切換到通用聊天模式 |
| `/mode career` | 切換到職涯顧問模式 |
| `/mode ielts` | 切換到雅思教練模式 |
| `/ielts_speaking` | 切換到口說練習 |
| `/ielts_writing` | 切換到寫作練習 |
| `/ielts_new` | 產生新的 IELTS 題目 |
| `/ielts_eval` | 產生目前 IELTS 總結評估 |
| `/ielts_status` | 查看 IELTS 練習狀態 |
| `/brief` | 立即產生半導體晨報 |
| `/clear` | 清空記憶與狀態 |

## 必要環境變數

- `TELEGRAM_BOT_TOKEN`
- `NVIDIA_API_KEY`
- `NVIDIA_BASE_URL`
- `NVIDIA_MODEL`
- `PORT`

可選環境變數：

| 變數 | 說明 | 預設值 |
|---|---|---|
| `DATABASE_URL` | Supabase Postgres 連線字串 | 空（使用 SQLite） |
| `BOT_USERNAME` | Bot 使用者名稱 | 空 |
| `MEMORY_DB_PATH` | SQLite 資料庫路徑 | `./data/memory.db` |
| `LOG_LEVEL` | 日誌等級 | `INFO` |
| `MAX_HISTORY_MESSAGES` | 對話記憶上限 | `12` |
| `ALPHAVANTAGE_API_KEY` | AlphaVantage API 金鑰（晨報用） | 空 |
| `TARGET_CHAT_ID` | 每日晨報推送的 Chat ID | 空 |
| `BRIEF_HOUR` | 晨報發送時間（小時） | `8` |
| `BRIEF_MINUTE` | 晨報發送時間（分鐘） | `0` |
| `BRIEF_TZ` | 晨報時區 | `Asia/Taipei` |
| `HOLDINGS_PATH` | 持股設定檔路徑 | `bot/holdings.json` |

如果你本機還沒準備 Supabase，可以先不填 `DATABASE_URL`，程式會退回 SQLite。
`NVIDIA_BASE_URL` 應填 `https://integrate.api.nvidia.com/v1`。

## 本機執行

1. 複製 `.env.example` 為 `.env`
2. 填入 `TELEGRAM_BOT_TOKEN` 與 `NVIDIA_API_KEY`
3. 確認 `NVIDIA_BASE_URL=https://integrate.api.nvidia.com/v1`
4. 本機開發建議 `DATABASE_URL=`（留空，使用 SQLite）
5. 本機開發建議 `MEMORY_DB_PATH=./data/memory.db`
6. 執行：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m bot.main
```

## Zeabur 部署

1. 把專案推到 GitHub
2. 在 Zeabur 建立 Project
3. 以 GitHub 或 Local Project 匯入專案
4. 使用專案根目錄的 `Dockerfile` 部署
5. 在 Zeabur Variables 設定：
   - `TELEGRAM_BOT_TOKEN`
   - `NVIDIA_API_KEY`
   - `NVIDIA_BASE_URL=https://integrate.api.nvidia.com/v1`
   - `NVIDIA_MODEL`
   - `DATABASE_URL`（若要使用 Supabase Postgres）
   - `PORT=8080`
6. 如果沒有設定 `DATABASE_URL`，程式會退回 SQLite；這適合本機開發，不建議當成正式環境的持久化儲存
7. 在 Supabase 專案取得 Postgres 連線字串，建議使用 session pooler
8. 部署完成後可檢查 `/healthz`

## docker compose

本機仍可使用：

```bash
docker compose up --build -d
```

## 目前保留給後續擴充

- IELTS 全科輪替策略更細緻的排程
- `/ielts_eval` 總評分分析
- quota 告警與雲端監控
- 正式 migration 工具
