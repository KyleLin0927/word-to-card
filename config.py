import os
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
ANKI_CONNECT_URL = os.environ.get("ANKI_CONNECT_URL", "http://localhost:8765")
ANKI_DECK_NAME = os.environ.get("ANKI_DECK_NAME", "Vocabulary::WordToCard")
ANKI_MODEL_NAME = os.environ.get("ANKI_MODEL_NAME", "Basic")
ANKI_AUDIO_FIELD = os.environ.get("ANKI_AUDIO_FIELD", "Audio")

# 預設使用穩定且目前可用的新模型；仍可用 .env 的 GEMINI_MODEL 覆寫
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

TTS_VOICE = os.environ.get("TTS_VOICE", "en-US-JennyNeural")

CAPTURES_DIR = os.path.join(os.path.dirname(__file__), "captures")
QUEUE_FILE = os.path.join(os.path.dirname(__file__), "pending_tasks.json")
HISTORY_FILE = os.path.join(os.path.dirname(__file__), "word_history.json")

# 本地單字 JSON 目錄（Anki 成功新增後同步寫入）；WORD_ARCHIVE_ENABLED=false 可關閉
_wae = os.environ.get("WORD_ARCHIVE_ENABLED", "true").strip().lower()
WORD_ARCHIVE_ENABLED = _wae not in ("0", "false", "no", "off")
_base_dir = os.path.dirname(__file__)
_wad = os.environ.get("WORD_ARCHIVE_DIR", "").strip()
if _wad:
    WORD_ARCHIVE_DIR = _wad if os.path.isabs(_wad) else os.path.join(_base_dir, _wad)
else:
    WORD_ARCHIVE_DIR = os.path.join(_base_dir, "vocabulary")

# pynput GlobalHotKeys 格式
# - 截圖模式：Cmd+Ctrl+S
# - 反白取詞（剪貼簿攔截）：Ctrl+C
HOTKEY_SCREENSHOT = os.environ.get("HOTKEY_SCREENSHOT", "<cmd>+<ctrl>+s")
HOTKEY_SCREENSHOT_DISPLAY = "⌘+⌃+S"

# 可用逗號分隔多組熱鍵（為了兼容 macOS 上 Option/Alt 的差異）
# 例：HOTKEY_SELECTIONS="<ctrl>+c"
HOTKEY_SELECTIONS = os.environ.get(
    "HOTKEY_SELECTIONS",
    "<ctrl>+c",
)
HOTKEY_SELECTIONS_DISPLAY = os.environ.get("HOTKEY_SELECTIONS_DISPLAY", "⌃+C")

# 成功新增 Anki 卡片後：除通知中心外，預設再播放短音效（多螢幕／Focus 下橫幅可能不出現）
_nss = os.environ.get("NOTIFY_SUCCESS_SOUND", "true").strip().lower()
NOTIFY_SUCCESS_SOUND = _nss not in ("0", "false", "no", "off")
NOTIFY_SUCCESS_SOUND_FILE = os.environ.get(
    "NOTIFY_SUCCESS_SOUND_FILE",
    "/System/Library/Sounds/Glass.aiff",
).strip()
