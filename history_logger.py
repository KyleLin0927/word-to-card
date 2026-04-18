"""
本地單字歷史記錄
防止同一個單字被重複分析、重複送進 Anki。
"""

import json
import os

import config


def normalize_word(word: str) -> str:
    """
    用於去重/歷史比對的正規化：
    - 去除前後空白
    - 轉小寫
    - 連續空白視為一個空白
    """
    if word is None:
        return ""
    return " ".join(str(word).strip().lower().split())


def _load() -> set[str]:
    if not os.path.exists(config.HISTORY_FILE):
        return set()
    with open(config.HISTORY_FILE, "r", encoding="utf-8") as f:
        return set(json.load(f))


def _save(history: set[str]) -> None:
    with open(config.HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted(history), f, ensure_ascii=False, indent=2)


def is_new(word: str) -> bool:
    """回傳 True 表示這個單字尚未記錄過。"""
    return normalize_word(word) not in _load()


def filter_new(words: list[dict]) -> list[dict]:
    """從清單中過濾掉已記錄過的單字，只回傳新單字。"""
    history = _load()
    seen_in_batch: set[str] = set()
    filtered: list[dict] = []
    for w in words:
        key = normalize_word(w.get("word", ""))
        if not key:
            continue
        if key in history:
            continue
        if key in seen_in_batch:
            continue
        seen_in_batch.add(key)
        filtered.append(w)
    return filtered


def record(words: list[dict]) -> None:
    """將成功加入 Anki 的單字寫入歷史記錄。"""
    history = _load()
    for w in words:
        key = normalize_word(w.get("word", ""))
        if key:
            history.add(key)
    _save(history)
