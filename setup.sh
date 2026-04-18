#!/bin/bash
set -e

echo "=== Word to Card 安裝程序 ==="

# 1. 建立虛擬環境
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
    echo "✓ 建立 .venv"
fi

# 2. 安裝依賴
source .venv/bin/activate
pip install -q --upgrade pip
pip install -q -r requirements.txt
echo "✓ 安裝套件完成"

# 3. 建立 captures/、vocabulary/ 目錄
mkdir -p captures vocabulary
echo "✓ 建立 captures/、vocabulary/ 目錄"

# 4. 建立 .env（若不存在）
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "✓ 建立 .env（請填入 GEMINI_API_KEY）"
else
    echo "  .env 已存在，跳過"
fi

echo ""
echo "=== 安裝完成 ==="
echo ""
echo "下一步："
echo "  1. 編輯 .env，填入你的 GEMINI_API_KEY"
echo "     → 從 https://aistudio.google.com/app/apikey 免費取得"
echo "  2. 確認 Anki 已開啟，且安裝了 AnkiConnect 擴充套件"
echo "     → https://ankiweb.net/shared/info/2055492159"
echo "  3. 執行測試："
echo "     source .venv/bin/activate && python main.py --test"
echo "  4. 確認無誤後啟動背景監聽："
echo "     python main.py"
echo ""
echo "首次執行 pynput 時，macOS 會要求「輔助使用」權限："
echo "  系統設定 → 隱私與安全性 → 輔助使用 → 允許你的終端機"
