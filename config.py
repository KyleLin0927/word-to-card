import os
import re
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
ANKI_CONNECT_URL = os.environ.get("ANKI_CONNECT_URL", "http://localhost:8765")
ANKI_DECK_NAME = os.environ.get("ANKI_DECK_NAME", "Vocabulary::WordToCard")

_base_dir = os.path.dirname(__file__)


def _deck_slug(anki_deck_name: str) -> str:
    """
    將 ANKI_DECK_NAME 轉為檔名／目錄名安全 slug。
    Anki 牌組階層（::）轉為雙底線 __，其餘不允許字元替為單一底線。
    """
    raw = (anki_deck_name or "").strip()
    if not raw:
        raw = "Vocabulary::WordToCard"
    parts = raw.split("::")
    safe_parts: list[str] = []
    for part in parts:
        p = part.strip()
        for ch in '\0/\\<>:"|?*\n\r\t':
            p = p.replace(ch, "_")
        p = re.sub(r"_+", "_", p).strip("_")
        if p:
            safe_parts.append(p)
    slug = "__".join(safe_parts) if safe_parts else "deck"
    return slug[:180]


# 與 ANKI_DECK_NAME 對應，供 vocabulary 子目錄、word_history 分檔使用
DECK_SLUG = _deck_slug(ANKI_DECK_NAME)
ANKI_MODEL_NAME = os.environ.get("ANKI_MODEL_NAME", "Basic")
ANKI_AUDIO_FIELD = os.environ.get("ANKI_AUDIO_FIELD", "Audio")

# 預設使用穩定且目前可用的新模型；仍可用 .env 的 GEMINI_MODEL 覆寫
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

TTS_VOICE = os.environ.get("TTS_VOICE", "en-US-JennyNeural")

CAPTURES_DIR = os.path.join(_base_dir, "captures")
QUEUE_FILE = os.path.join(_base_dir, "pending_tasks.json")

# 本地去重歷史：依牌組分檔 word_history/<DECK_SLUG>.json（舊版根目錄 word_history.json 仍相容讀取）
HISTORY_DIR = os.path.join(_base_dir, "word_history")
HISTORY_FILE = os.path.join(HISTORY_DIR, f"{DECK_SLUG}.json")
HISTORY_LEGACY_FILE = os.path.join(_base_dir, "word_history.json")

# 本地單字 JSON：基底目錄 + <DECK_SLUG> 子目錄（與 ANKI_DECK_NAME 對應）；WORD_ARCHIVE_ENABLED=false 可關閉
_wae = os.environ.get("WORD_ARCHIVE_ENABLED", "true").strip().lower()
WORD_ARCHIVE_ENABLED = _wae not in ("0", "false", "no", "off")
_wad = os.environ.get("WORD_ARCHIVE_DIR", "").strip()
if _wad:
    WORD_ARCHIVE_BASE = _wad if os.path.isabs(_wad) else os.path.join(_base_dir, _wad)
else:
    WORD_ARCHIVE_BASE = os.path.join(_base_dir, "vocabulary")
WORD_ARCHIVE_DIR = os.path.join(WORD_ARCHIVE_BASE, DECK_SLUG)

# ── 片語 Cloze 牌組（與單字獨立）──────────────────────────────
ANKI_PHRASE_DECK_NAME = os.environ.get("ANKI_PHRASE_DECK_NAME", "Vocabulary::Phrases")
PHRASE_DECK_SLUG = _deck_slug(ANKI_PHRASE_DECK_NAME)
ANKI_PHRASE_MODEL_NAME = os.environ.get("ANKI_PHRASE_MODEL_NAME", "Cloze")
ANKI_PHRASE_FIELD_TEXT = os.environ.get("ANKI_PHRASE_FIELD_TEXT", "Text")
ANKI_PHRASE_FIELD_EXTRA = os.environ.get("ANKI_PHRASE_FIELD_EXTRA", "Back Extra")

MAX_PHRASES_PER_RESPONSE = max(1, min(12, int(os.environ.get("MAX_PHRASES_PER_RESPONSE", "1"))))

# 片語：去重歷史（獨立 phrase_history/<slug>.json，與單字 word_history 分離）
PHRASE_HISTORY_DIR = os.path.join(_base_dir, "phrase_history")
PHRASE_HISTORY_FILE = os.path.join(PHRASE_HISTORY_DIR, f"{PHRASE_DECK_SLUG}.json")

# 片語：封存 vocabulary_phrases/<slug>/
_pae = os.environ.get("PHRASE_ARCHIVE_ENABLED", "true").strip().lower()
PHRASE_ARCHIVE_ENABLED = _pae not in ("0", "false", "no", "off")
_phab = os.environ.get("PHRASE_ARCHIVE_DIR", "").strip()
if _phab:
    PHRASE_ARCHIVE_BASE = _phab if os.path.isabs(_phab) else os.path.join(_base_dir, _phab)
else:
    PHRASE_ARCHIVE_BASE = os.path.join(_base_dir, "vocabulary_phrases")
PHRASE_ARCHIVE_DIR = os.path.join(PHRASE_ARCHIVE_BASE, PHRASE_DECK_SLUG)

# 片語截圖失敗佇列（與單字 pending_tasks.json 分離）
QUEUE_FILE_PHRASE = os.path.join(_base_dir, "pending_tasks_phrases.json")

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

# 片語模式：截圖 / 反白（反白仍用 Cmd+C 讀取選取範圍）
HOTKEY_SCREENSHOT_PHRASE = os.environ.get("HOTKEY_SCREENSHOT_PHRASE", "<cmd>+<ctrl>+d")
HOTKEY_SCREENSHOT_PHRASE_DISPLAY = os.environ.get("HOTKEY_SCREENSHOT_PHRASE_DISPLAY", "⌘+⌃+D")
HOTKEY_PHRASE_SELECTIONS = os.environ.get("HOTKEY_PHRASE_SELECTIONS", "<ctrl>+v")
HOTKEY_PHRASE_SELECTIONS_DISPLAY = os.environ.get("HOTKEY_PHRASE_SELECTIONS_DISPLAY", "⌃+V")

# 成功新增 Anki 卡片後：除通知中心外，預設再播放短音效（多螢幕／Focus 下橫幅可能不出現）
_nss = os.environ.get("NOTIFY_SUCCESS_SOUND", "true").strip().lower()
NOTIFY_SUCCESS_SOUND = _nss not in ("0", "false", "no", "off")
NOTIFY_SUCCESS_SOUND_FILE = os.environ.get(
    "NOTIFY_SUCCESS_SOUND_FILE",
    "/System/Library/Sounds/Glass.aiff",
).strip()
