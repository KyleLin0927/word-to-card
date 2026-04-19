"""
片語去重歷史（與單字 history_logger 分檔）
"""

import json
import os

import config
import history_logger

# 與單字使用相同正規化邏輯（多字片語同樣適用）


def _load() -> set[str]:
    p = config.PHRASE_HISTORY_FILE
    if os.path.isfile(p):
        with open(p, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()


def _save(h: set[str]) -> None:
    path = config.PHRASE_HISTORY_FILE
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(sorted(h), f, ensure_ascii=False, indent=2)


def filter_new(phrases: list[dict]) -> list[dict]:
    history = _load()
    seen: set[str] = set()
    out: list[dict] = []
    for p in phrases:
        if not isinstance(p, dict):
            continue
        key = history_logger.normalize_word(str(p.get("phrase", "")).strip())
        if not key:
            continue
        if key in history or key in seen:
            continue
        seen.add(key)
        out.append(p)
    return out


def record(phrases: list[dict]) -> None:
    h = _load()
    for p in phrases:
        if not isinstance(p, dict):
            continue
        k = history_logger.normalize_word(str(p.get("phrase", "")).strip())
        if k:
            h.add(k)
    _save(h)
