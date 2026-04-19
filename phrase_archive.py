"""
片語 Cloze 成功後 JSON 封存（與 word_archive 分目录）
"""

import json
import logging
import os
import re

import config
import history_logger

log = logging.getLogger(__name__)

_INVALID_FILENAME = re.compile(r'[\0/\\<>:"|?*\n\r\t]')


def _safe_filename(phrase: str) -> str:
    stem = history_logger.normalize_word(phrase).replace(" ", "_")
    if not stem:
        return ""
    s = _INVALID_FILENAME.sub("_", stem)
    return s[:200]


def _payload(p: dict, archived_at: str) -> dict:
    syn = p.get("synonyms")
    if isinstance(syn, list):
        syn_out = [str(x).strip() for x in syn if str(x).strip()]
    else:
        syn_out = [s.strip() for s in str(syn or "").split(",") if s.strip()]
    return {
        "phrase": str(p.get("phrase", "")).strip(),
        "phrase_front": str(p.get("phrase_front", "")).strip(),
        "cloze_text": str(p.get("cloze_text", "")).strip(),
        "semantic_anchor_zh": str(p.get("semantic_anchor_zh", "")).strip(),
        "sentence_zh": str(p.get("sentence_zh", "")).strip(),
        "definition_zh": str(p.get("definition_zh", "")).strip(),
        "usage_note": str(p.get("usage_note", "")).strip(),
        "register_zh": str(p.get("register_zh", "")).strip(),
        "synonyms": syn_out,
        "archived_at": archived_at,
    }


def save(phrases: list[dict]) -> None:
    if not getattr(config, "PHRASE_ARCHIVE_ENABLED", True):
        return
    if not phrases:
        return
    from datetime import datetime, timezone

    root = config.PHRASE_ARCHIVE_DIR
    try:
        os.makedirs(root, exist_ok=True)
    except OSError as e:
        log.warning("無法建立片語庫目錄 %s：%s", root, e)
        return

    archived_at = datetime.now(timezone.utc).isoformat()
    for p in phrases:
        stem = _safe_filename(str(p.get("phrase", "")).strip())
        if not stem:
            continue
        path = os.path.join(root, f"{stem}.json")
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(_payload(p, archived_at), f, ensure_ascii=False, indent=2)
        except OSError as e:
            log.warning("無法寫入片語檔 %s：%s", path, e)
