# Word to Card

按下快捷鍵，框選螢幕上的英文單字，自動生成 GRE/TOEFL 等級的 Anki 卡片。

```
截圖 → Gemini Vision 分析 → 歷史去重 → AnkiConnect 寫入
```

## 功能

- **一鍵截圖**：按 `⌥+⇧+S`，拖曳選取包含單字的區域
- **AI 分析**：透過 Gemini Vision 辨識 1～5 個學術單字，附 IPA 發音、詞性、英中定義、例句、同義詞
- **自動去重**：本地歷史記錄防止同一單字重複送入 Anki
- **離線佇列**：Gemini 或 Anki 連線失敗時自動排隊，下次啟動補重試
- **Log 紀錄**：每次截圖流程皆寫入 `word_to_card.log`，方便排查問題

## 前置需求

- macOS（截圖使用 `screencapture`）
- Python 3.11+
- [Anki](https://apps.ankiweb.net/) + [AnkiConnect](https://ankiweb.net/shared/info/2055492159) 外掛（Anki 需保持開啟）
- Gemini API Key（[取得方式](https://aistudio.google.com/app/apikey)）

## 安裝

```bash
git clone https://github.com/yourname/word-to-card.git
cd word-to-card

python3 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
```

## 設定

複製範本並填入 API Key：

```bash
cp .env.example .env
```

`.env` 內容：

```env
GEMINI_API_KEY=your_api_key_here

# 以下為選填，有預設值
ANKI_CONNECT_URL=http://localhost:8765
ANKI_DECK_NAME=Vocabulary::WordToCard
ANKI_MODEL_NAME=Basic
GEMINI_MODEL=gemini-2.0-flash
HOTKEY=<alt>+<shift>+s
```

## 使用

```bash
# 啟動背景監聽
python main.py

# 測試：立即觸發一次截圖（不需要快捷鍵）
python main.py --test
```

啟動後按 `⌥+⇧+S`，拖曳框選含有英文單字的區域，稍等片刻即可在 Anki 收到新卡片。

### 查看 Log

```bash
tail -f word_to_card.log
```

範例輸出：

```
2026-04-16 14:32:01 [INFO] === Word to Card 已啟動 ===
2026-04-16 14:32:01 [INFO] 快捷鍵：⌘+⇧+W
2026-04-16 14:32:01 [INFO] 模型：models/gemini-2.0-flash
2026-04-16 14:32:15 [INFO] ── 開始截圖流程 ──
2026-04-16 14:32:18 [INFO] 截圖完成：captures/capture_20260416_143218.png
2026-04-16 14:32:18 [INFO] 送出截圖至 Gemini（模型：gemini-2.0-flash）
2026-04-16 14:32:21 [INFO] Gemini 辨識到 2 個單字：ephemeral, propitious
2026-04-16 14:32:21 [INFO] 寫入 Anki：ephemeral, propitious
2026-04-16 14:32:21 [INFO] 完成：新增 2 張卡片（ephemeral、propitious）
```

## 打包與發布（執行檔 / Build & Release）

不想裝 Python 的使用者，可直接用打包好的執行檔。

### 直接下載

到本專案的 **Releases** 頁面，依平台下載：

| 平台 | 檔案 |
|------|------|
| Windows x64 | `word-to-card-windows-x64.exe` |
| macOS Apple Silicon | `word-to-card-macos-arm64` |
| macOS Intel | `word-to-card-macos-x64` |
| Linux x64 | `word-to-card-linux-x64` |

執行前準備：

1. 在**執行檔同層**放一個 `.env`（格式見 `.env.example`），至少填入 `GEMINI_API_KEY`。
2. 先開啟 Anki 並安裝 AnkiConnect。

> 資料（單字庫、歷史、log、截圖）預設寫在**執行檔同層**。要改放別處，在 `.env` 設 `W2C_DATA_DIR`：
>
> ```env
> # 絕對路徑、~ 或相對路徑（相對執行檔）皆可
> W2C_DATA_DIR=~/word-to-card-data
> ```

> **macOS 為未簽章檔**，首次開啟若出現「無法驗證開發者」：
>
> ```bash
> xattr -c word-to-card-macos-arm64   # 或 -x64
> chmod +x word-to-card-macos-arm64
> ./word-to-card-macos-arm64
> ```
>
> 或到「系統設定 → 隱私權與安全性」按「仍要開啟」。

### 本機打包

```bash
source .venv/bin/activate
pip install -r requirements.txt        # 已含 pyinstaller
pyinstaller word-to-card.spec
# 產物在 dist/word-to-card（Windows 為 word-to-card.exe）
```

### 自動發布（GitHub Actions）

打包設定在 `word-to-card.spec`，CI 流程在 `.github/workflows/release.yml`。

- **推送 `v*` tag** → 自動在 Windows / macOS(arm64) / macOS(Intel) / Linux 四個環境打包，並建立同名 GitHub Release、上傳四個執行檔。
- **手動觸發**（Actions 分頁的 *Run workflow*）→ 只打包並上傳 artifact，不建立 Release，方便測試。

發布新版本：

```bash
git add .
git commit -m "release v1.0.0"
git tag v1.0.0
git push origin main
git push origin v1.0.0
```

> 目前桌面通知／成功音效僅 macOS 有效（使用 `osascript`／`afplay`）；Windows / Linux 上通知會改寫入 log，核心的截圖→分析→寫入 Anki 流程仍可運作。

## 卡片格式

| 欄位 | 內容 |
|------|------|
| 正面 | 單字、IPA 發音、詞性 |
| 背面 | 英文定義、中文定義、例句、同義詞、原文句子、難度標籤 |

卡片自動標上 `word-to-card`、難度（`gre` / `toefl` / `academic`）、詞性等 tags。

## 專案結構

```
word-to-card/
├── main.py            # 進入點，快捷鍵監聽與主流程
├── llm.py             # Gemini Vision 分析
├── anki.py            # AnkiConnect 卡片寫入
├── screenshot.py      # macOS 截圖
├── history_logger.py  # 本地單字歷史去重
├── queue_manager.py   # 離線重試佇列
├── notify.py          # macOS 通知
├── config.py          # 環境變數讀取
├── requirements.txt
├── word_to_card.log   # 執行 log（自動產生）
├── word_history.json  # 已收錄單字（自動產生）
└── captures/          # 截圖暫存目錄（自動產生）
```
