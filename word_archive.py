"""
將 Anki 成功新增的單字 JSON 另存於本地目錄（與 Anki 並行）。
"""

import json
import logging
import os
import re
from datetime import datetime, timezone

import config
import history_logger

log = logging.getLogger(__name__)

_INVALID_FILENAME = re.compile(r'[\0/\\<>:"|?*\n\r\t]')


def _safe_stem(word: str) -> str:
    stem = history_logger.normalize_word(word)
    if not stem:
        return ""
    s = stem.replace(" ", "_")
    s = _INVALID_FILENAME.sub("_", s)
    if len(s) > 200:
        s = s[:200]
    return s


def _archive_payload(word: dict, archived_at: str) -> dict:
    """
    寫入 vocabulary/ 的精簡格式：不重複根層與 senses[0] 相同的欄位。
    執行中記憶體內的 word 物件仍可有 part_of_speech 等（供通知／Anki），僅封存時省略。
    """
    senses = word.get("senses")
    if not isinstance(senses, list):
        senses = []
    return {
        "word": word.get("word", ""),
        "phonetic": word.get("phonetic", ""),
        "difficulty": word.get("difficulty", ""),
        "roots_memory": str(word.get("roots_memory", "") or "").strip(),
        "senses": senses,
        "archived_at": archived_at,
    }


def save(words: list[dict]) -> None:
    """
    每個單字寫入一個 JSON；失敗僅 log，不拋出例外。
    """
    if not getattr(config, "WORD_ARCHIVE_ENABLED", True):
        return
    if not words:
        return
    root = config.WORD_ARCHIVE_DIR
    try:
        os.makedirs(root, exist_ok=True)
    except OSError as e:
        log.warning("無法建立單字庫目錄 %s：%s", root, e)
        return

    archived_at = datetime.now(timezone.utc).isoformat()
    for w in words:
        stem = _safe_stem(str(w.get("word", "")).strip())
        if not stem:
            continue
        path = os.path.join(root, f"{stem}.json")
        payload = _archive_payload(w, archived_at)
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
        except OSError as e:
            log.warning("無法寫入單字檔 %s：%s", path, e)
