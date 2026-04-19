"""
word-to-card — 快捷鍵截圖 → Gemini 分析 → Anki 單字卡

使用方式：
  python main.py          # 啟動背景監聽（快捷鍵模式）
  python main.py --test   # 立即觸發一次截圖（測試用）
"""

import logging
import os
import re
import sys
import threading
import time

from pynput import keyboard
from pynput.keyboard import Controller, Key

import pyperclip

import config
import history_logger
import phrase_archive
import phrase_history
import phrase_queue_manager
import queue_manager
import word_archive
from anki import add_cards_to_anki_results, add_phrases_to_anki_results
from llm import (
    analyze_image,
    analyze_image_phrases,
    analyze_text,
    analyze_text_phrases,
    get_effective_model_name,
)
from notify import notify, notify_success
from screenshot import take_screenshot


def _record_added(words: list[dict]) -> None:
    """Anki 成功新增後：更新歷史去重，並寫入本地單字庫目錄。"""
    if not words:
        return
    history_logger.record(words)
    word_archive.save(words)


def _record_phrases_added(phrases: list[dict]) -> None:
    """Anki 成功新增片語卡後：片語歷史 + 封存。"""
    if not phrases:
        return
    phrase_history.record(phrases)
    phrase_archive.save(phrases)


# ── Logging 設定 ──────────────────────────────────────────
_LOG_FILE = os.path.join(os.path.dirname(__file__), "word_to_card.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(_LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)

_kb = Controller()


def _pos_abbrev(pos: str) -> str:
    raw = (pos or "").strip().lower()
    # verb (vt) / verb (vi) / verb (vi/vt)；phrasal verb (…)
    m = re.search(
        r"(?:(phrasal)\s+)?verb\s*\(\s*(vi|vt)(?:\s*/\s*(vi|vt))?\s*\)",
        raw,
        re.I,
    )
    if m:
        phr = " phr." if m.group(1) else ""
        a, b = m.group(2).lower(), m.group(3)
        if b:
            b = b.lower()
            core = "vi./vt." if {a, b} == {"vi", "vt"} else f"{a}./{b}."
        else:
            core = "vi." if a == "vi" else "vt."
        return core + phr
    mapping = {
        "proper noun": "prop. n.",
        "noun": "n.",
        "verb": "v.",
        "adjective": "adj.",
        "adverb": "adv.",
        "preposition": "prep.",
        "conjunction": "conj.",
        "pronoun": "pron.",
        "interjection": "interj.",
    }
    if raw in mapping:
        return mapping[raw]
    # 支援類似 "noun/verb"、"phrasal verb"
    for k, v in mapping.items():
        if k in raw:
            return v
    return ""


def _format_word_preview(words: list[dict], limit: int = 3) -> str:
    """
    通知預覽文字：word (pos.) 中文.
    """
    previews: list[str] = []
    for w in words[:limit]:
        word = str(w.get("word", "")).strip()
        pos = _pos_abbrev(str(w.get("part_of_speech", "")))
        zh = str(w.get("definition_zh", "")).strip()
        chunks = [word]
        if pos:
            chunks.append(f"({pos})")
        if zh:
            chunks.append(zh)
        previews.append(" ".join(c for c in chunks if c))
    text = "、".join(p for p in previews if p)
    if len(words) > limit:
        text += f" … 共 {len(words)} 字"
    return text


def _phrase_names(phrases: list[dict]) -> str:
    names = []
    for p in phrases:
        if isinstance(p, dict):
            n = str(p.get("phrase", "")).strip()
            if n:
                names.append(n)
    return ", ".join(names)


def _format_phrase_preview(phrases: list[dict], limit: int = 4) -> str:
    parts: list[str] = []
    for p in phrases[:limit]:
        ph = str(p.get("phrase", "")).strip()
        zh = str(p.get("definition_zh", "")).strip()
        if ph and zh:
            parts.append(f"{ph} — {zh}")
        elif ph:
            parts.append(ph)
    text = "、".join(parts)
    if len(phrases) > limit:
        text += f" … 共 {len(phrases)} 筆"
    return text


def _word_names(words: list[dict]) -> str:
    names = []
    for w in words:
        if isinstance(w, dict):
            name = str(w.get("word", "")).strip()
            if name:
                names.append(name)
    return ", ".join(names)


def _copy_selection_to_clipboard(wait_ms: int = 120) -> tuple[str, str]:
    """
    用剪貼簿攔截法取得反白文字。
    回傳 (previous_clipboard, current_clipboard)。
    """
    previous = pyperclip.paste()

    # 模擬 Cmd+C
    _kb.press(Key.cmd)
    _kb.press("c")
    _kb.release("c")
    _kb.release(Key.cmd)

    # 等待剪貼簿更新（並做簡單輪詢避免讀到舊值）
    deadline = time.time() + (wait_ms / 1000.0)
    current = pyperclip.paste()
    while current == previous and time.time() < deadline:
        time.sleep(0.05)
        current = pyperclip.paste()

    return previous, current


def process_selection() -> None:
    """反白取詞 → Gemini Text → 歷史過濾 → 寫入 Anki。"""
    log.info("── 開始反白取詞流程 ───────────────────────")
    notify("Word to Card", "請先反白單字，再按 Ctrl+C")

    try:
        previous, selected = _copy_selection_to_clipboard()
    except Exception as e:
        log.error("無法模擬拷貝或讀取剪貼簿：%s", e)
        notify("取詞失敗", "請到 系統設定→隱私權與安全性→輔助使用 開啟權限")
        return

    try:
        selected_text = (selected or "").strip()
        if not selected_text:
            log.info("剪貼簿內容為空（可能未反白或複製失敗）")
            notify("未取得反白文字", "請先反白一個單字再按 Ctrl+C")
            return

        notify("Word to Card", "Gemini 解析單字中，請稍候…")
        log.info("送出剪貼簿文字至 Gemini（模型：%s）", config.GEMINI_MODEL)
        words = analyze_text(selected_text)
        if not words:
            log.info("Gemini 判定非單字或無結果：%r", selected_text[:80])
            notify("不是單字", "請反白單一英文單字再試一次")
            return

        new_words = history_logger.filter_new(words)
        skipped = len(words) - len(new_words)
        if not new_words:
            notify("已收錄", f"{skipped} 個單字已在歷史記錄中")
            return

        log.info("寫入 Anki：%s", _word_names(new_words))
        results = add_cards_to_anki_results(new_words)
        added_words = [w for w, r in zip(new_words, results) if r is not None]
        _record_added(added_words)
        added = len(added_words)

        word_preview = _format_word_preview(added_words)
        if added == 0:
            names = _word_names(new_words)
            notify(
                "未新增卡片",
                (f"Anki 可能皆為重複：{names}" if names else "Anki 未新增任何筆記（可能皆為重複）"),
            )
        else:
            notify_success(f"已新增 {added} 張卡片", word_preview or "（無預覽文字）")
        log.info("完成：新增 %d 張卡片（%s）", added, word_preview)
    except Exception as e:
        log.error("反白取詞流程失敗：%s", e)
        notify("取詞流程失敗", str(e))
    finally:
        # 還原剪貼簿
        try:
            pyperclip.copy(previous)
        except Exception:
            pass

def process_screenshot() -> None:
    """截圖 → Gemini 分析 → 歷史過濾 → 寫入 Anki 的完整流程。"""
    log.info("── 開始截圖流程 ──────────────────────────")
    notify("Word to Card", "請框選包含英文單字的區域")

    image_path = take_screenshot()
    if not image_path:
        log.info("截圖取消（使用者按下 Esc 或未選取區域）")
        return

    log.info("截圖完成：%s", image_path)
    notify("Word to Card", "Gemini 分析中，請稍候…")

    # ── 1. LLM 分析截圖 ──────────────────────────────────
    log.info("送出截圖至 Gemini（模型：%s）", config.GEMINI_MODEL)
    try:
        words = analyze_image(image_path)
    except Exception as e:
        log.error("Gemini 分析失敗：%s", e)
        notify("分析失敗，已加入重試佇列", str(e))
        queue_manager.enqueue(image_path)
        return

    if not words:
        log.warning("Gemini 未回傳任何單字（圖片不清晰或無英文文字）")
        notify("未找到單字", "圖片不清晰或無英文文字")
        os.unlink(image_path)
        return

    log.info("Gemini 辨識到 %d 個單字：%s", len(words), _word_names(words))

    # ── 2. 過濾已記錄的單字 ───────────────────────────────
    new_words = history_logger.filter_new(words)
    skipped = len(words) - len(new_words)

    if skipped:
        log.info("過濾舊字 %d 個，剩餘新字 %d 個", skipped, len(new_words))

    if not new_words:
        log.info("所有單字皆已收錄，略過寫入 Anki")
        notify("全部已收錄", f"{skipped} 個單字皆已在歷史記錄中")
        os.unlink(image_path)
        return

    # ── 3. 寫入 Anki ──────────────────────────────────────
    log.info("寫入 Anki：%s", _word_names(new_words))
    try:
        results = add_cards_to_anki_results(new_words)
    except Exception as e:
        log.error("Anki 寫入失敗：%s", e)
        notify("Anki 寫入失敗，已加入重試佇列", str(e))
        queue_manager.enqueue(image_path)
        return

    # ── 4. 記錄歷史、刪除截圖 ─────────────────────────────
    added_words = [w for w, r in zip(new_words, results) if r is not None]
    _record_added(added_words)
    os.unlink(image_path)

    word_preview = _format_word_preview(added_words)
    if skipped:
        word_preview += f"（跳過 {skipped} 個舊字）"

    added = len(added_words)
    log.info("完成：新增 %d 張卡片（%s）", added, word_preview)
    if added == 0:
        names = _word_names(new_words)
        notify(
            "未新增卡片",
            (f"Anki 可能皆為重複：{names}" if names else "Anki 未新增任何筆記（可能皆為重複）"),
        )
    else:
        notify_success(f"已新增 {added} 張卡片", word_preview or "（無預覽文字）")


def process_screenshot_phrase() -> None:
    """截圖 → Gemini 片語 Cloze → 片語歷史 → Anki 片語牌組。"""
    log.info("── 開始片語截圖流程 ───────────────────────")
    notify("Word to Card 片語", "請框選含英文搭配或句子的區域")

    image_path = take_screenshot()
    if not image_path:
        log.info("片語截圖取消")
        return

    log.info("片語截圖完成：%s", image_path)
    notify("Word to Card 片語", "Gemini 解析片語中…")

    log.info("送出片語截圖至 Gemini（模型：%s）", config.GEMINI_MODEL)
    try:
        phrases = analyze_image_phrases(image_path)
    except Exception as e:
        log.error("片語 Gemini 分析失敗：%s", e)
        notify("片語分析失敗，已加入片語重試佇列", str(e))
        phrase_queue_manager.enqueue(image_path)
        return

    if not phrases:
        log.warning("片語：無合格搭配（或圖片不清晰）")
        notify("未收錄片語", "未辨識到值得收錄的搭配")
        os.unlink(image_path)
        return

    log.info("Gemini 片語 %d 筆：%s", len(phrases), _phrase_names(phrases))

    new_phrases = phrase_history.filter_new(phrases)
    skipped = len(phrases) - len(new_phrases)
    if skipped:
        log.info("片語過濾已收錄 %d 筆，剩餘 %d 筆", skipped, len(new_phrases))

    if not new_phrases:
        notify("片語皆已收錄", f"{skipped} 筆已在片語歷史中")
        os.unlink(image_path)
        return

    log.info("寫入 Anki（片語牌組）：%s", _phrase_names(new_phrases))
    try:
        results = add_phrases_to_anki_results(new_phrases)
    except Exception as e:
        log.error("片語 Anki 寫入失敗：%s", e)
        notify("片語 Anki 失敗，已加入片語重試佇列", str(e))
        phrase_queue_manager.enqueue(image_path)
        return

    added_phrases = [p for p, r in zip(new_phrases, results) if r is not None]
    _record_phrases_added(added_phrases)
    os.unlink(image_path)

    preview = _format_phrase_preview(added_phrases)
    added = len(added_phrases)
    log.info("片語完成：新增 %d 張（%s）", added, preview)
    if skipped:
        preview = (preview + f"（跳過歷史 {skipped}）") if preview else f"跳過歷史 {skipped}"
    if added == 0:
        notify(
            "片語未新增",
            (f"可能皆重複：{_phrase_names(new_phrases)}" if new_phrases else "Anki 未新增"),
        )
    else:
        notify_success(f"已新增 {added} 張片語卡", preview or "（無預覽）")


def process_selection_phrase() -> None:
    """反白 → Cmd+C 讀取選取 → Gemini 片語 → Anki。"""
    log.info("── 開始片語反白流程 ───────────────────────")
    notify("Word to Card 片語", "請反白英文片語或段落，再按快捷鍵（預設 ⌃V）")

    try:
        previous, selected = _copy_selection_to_clipboard()
    except Exception as e:
        log.error("片語：無法讀取剪貼簿：%s", e)
        notify("取詞失敗", "請到 系統設定→隱私權與安全性→輔助使用 開啟權限")
        return

    try:
        text = (selected or "").strip()
        if not text:
            log.info("片語：剪貼簿為空")
            notify("未取得文字", "請反白英文內容後再試")
            return

        notify("Word to Card 片語", "Gemini 解析片語中…")
        log.info("送出片語剪貼簿文字至 Gemini（模型：%s）", config.GEMINI_MODEL)
        phrases = analyze_text_phrases(text)
        if not phrases:
            log.info("片語：無合格搭配")
            notify("未收錄片語", "未找到值得收錄的搭配")
            return

        new_phrases = phrase_history.filter_new(phrases)
        skipped = len(phrases) - len(new_phrases)
        if not new_phrases:
            notify("片語已收錄", f"{skipped} 筆已在片語歷史中")
            return

        log.info("寫入 Anki（片語牌組）：%s", _phrase_names(new_phrases))
        results = add_phrases_to_anki_results(new_phrases)
        added_phrases = [p for p, r in zip(new_phrases, results) if r is not None]
        _record_phrases_added(added_phrases)
        added = len(added_phrases)
        preview = _format_phrase_preview(added_phrases)

        if added == 0:
            notify("片語未新增", "Anki 可能皆為重複")
        else:
            notify_success(f"已新增 {added} 張片語卡", preview or "（無預覽）")
        log.info("片語完成：新增 %d 張（%s）", added, preview)
    except Exception as e:
        log.error("片語反白流程失敗：%s", e)
        notify("片語流程失敗", str(e))
    finally:
        try:
            pyperclip.copy(previous)
        except Exception:
            pass


def retry_queue() -> None:
    """啟動時重試離線佇列。"""
    count = queue_manager.pending_count()
    if count == 0:
        return
    log.info("佇列：發現 %d 個待重試任務，開始重試…", count)
    done = queue_manager.process_queue(
        analyze_fn=analyze_image,
        add_cards_fn=add_cards_to_anki_results,
        record_fn=_record_added,
    )
    log.info("佇列：重試完成 %d/%d 成功", done, count)


def retry_queue_phrase() -> None:
    count = phrase_queue_manager.pending_count()
    if count == 0:
        return
    log.info("片語佇列：發現 %d 個待重試任務…", count)
    done = phrase_queue_manager.process_queue(
        analyze_fn=analyze_image_phrases,
        add_cards_fn=add_phrases_to_anki_results,
        record_fn=_record_phrases_added,
    )
    log.info("片語佇列：重試完成 %d/%d", done, count)


def on_activate() -> None:
    thread = threading.Thread(target=process_screenshot, daemon=True)
    thread.start()


def on_activate_selection() -> None:
    thread = threading.Thread(target=process_selection, daemon=True)
    thread.start()


def on_activate_screenshot_phrase() -> None:
    thread = threading.Thread(target=process_screenshot_phrase, daemon=True)
    thread.start()


def on_activate_phrase_selection() -> None:
    thread = threading.Thread(target=process_selection_phrase, daemon=True)
    thread.start()


def _build_hotkey_handlers() -> list[keyboard.HotKey]:
    handlers: list[keyboard.HotKey] = []

    try:
        handlers.append(keyboard.HotKey(keyboard.HotKey.parse(config.HOTKEY_SCREENSHOT), on_activate))
    except Exception as e:
        log.error("截圖熱鍵格式錯誤：%s (%s)", config.HOTKEY_SCREENSHOT, e)

    selection_hotkeys = [h.strip() for h in config.HOTKEY_SELECTIONS.split(",") if h.strip()]
    for hotkey in selection_hotkeys:
        try:
            handlers.append(keyboard.HotKey(keyboard.HotKey.parse(hotkey), on_activate_selection))
        except Exception as e:
            log.error("反白取詞熱鍵格式錯誤：%s (%s)", hotkey, e)

    try:
        handlers.append(
            keyboard.HotKey(
                keyboard.HotKey.parse(config.HOTKEY_SCREENSHOT_PHRASE),
                on_activate_screenshot_phrase,
            )
        )
    except Exception as e:
        log.error("片語截圖熱鍵格式錯誤：%s (%s)", config.HOTKEY_SCREENSHOT_PHRASE, e)

    phrase_hotkeys = [h.strip() for h in config.HOTKEY_PHRASE_SELECTIONS.split(",") if h.strip()]
    for hotkey in phrase_hotkeys:
        try:
            handlers.append(keyboard.HotKey(keyboard.HotKey.parse(hotkey), on_activate_phrase_selection))
        except Exception as e:
            log.error("片語反白熱鍵格式錯誤：%s (%s)", hotkey, e)

    return handlers


def _run_hotkey_listener(hotkeys: list[keyboard.HotKey]) -> None:
    """
    使用 Listener + HotKey 以提升與不同 pynput 版本的相容性。
    """
    if not hotkeys:
        raise RuntimeError("沒有可用的熱鍵註冊，請檢查 HOTKEY 設定")

    listener: keyboard.Listener | None = None

    def _canonicalize(key: object) -> object:
        if listener is None:
            return key
        return listener.canonical(key)

    def on_press(key: object) -> None:
        k = _canonicalize(key)
        for hk in hotkeys:
            hk.press(k)

    def on_release(key: object) -> None:
        k = _canonicalize(key)
        for hk in hotkeys:
            hk.release(k)

    listener = keyboard.Listener(on_press=on_press, on_release=on_release)
    listener.start()
    listener.join()


def main() -> None:
    if "--test" in sys.argv:
        print("[測試模式] 立即觸發一次截圖")
        process_screenshot()
        return

    if not config.GEMINI_API_KEY:
        print("錯誤：請先設定 GEMINI_API_KEY 環境變數（或在 .env 填入）", file=sys.stderr)
        sys.exit(1)

    # 啟動時先重試離線佇列
    retry_queue()
    retry_queue_phrase()

    log.info("=== Word to Card 已啟動 ===")
    log.info("快捷鍵（截圖）：%s", config.HOTKEY_SCREENSHOT_DISPLAY)
    log.info("快捷鍵（截圖—片語）：%s", config.HOTKEY_SCREENSHOT_PHRASE_DISPLAY)
    log.info("快捷鍵（反白取詞）：%s", config.HOTKEY_SELECTIONS_DISPLAY)
    log.info("快捷鍵（反白—片語）：%s", config.HOTKEY_PHRASE_SELECTIONS_DISPLAY)
    try:
        log.info("模型：%s（env=%s）", get_effective_model_name(), config.GEMINI_MODEL)
    except Exception:
        log.info("模型：%s", config.GEMINI_MODEL)
    log.info("Anki 牌組（單字）：%s", config.ANKI_DECK_NAME)
    log.info("Anki 牌組（片語 Cloze）：%s", config.ANKI_PHRASE_DECK_NAME)
    log.info(
        "單字 slug：%s（庫：%s；歷史：%s）",
        config.DECK_SLUG,
        config.WORD_ARCHIVE_DIR,
        config.HISTORY_FILE,
    )
    log.info(
        "片語 slug：%s（庫：%s；歷史：%s；佇列檔：%s）",
        config.PHRASE_DECK_SLUG,
        config.PHRASE_ARCHIVE_DIR,
        config.PHRASE_HISTORY_FILE,
        config.QUEUE_FILE_PHRASE,
    )
    log.info("Log 檔案：%s", _LOG_FILE)
    log.info("按下 Ctrl+C 停止")

    selection_hotkeys = [h.strip() for h in config.HOTKEY_SELECTIONS.split(",") if h.strip()]
    log.info("已註冊反白取詞熱鍵：%s", ", ".join(selection_hotkeys))
    phrase_sel = [h.strip() for h in config.HOTKEY_PHRASE_SELECTIONS.split(",") if h.strip()]
    log.info("已註冊片語反白熱鍵：%s", ", ".join(phrase_sel))
    hotkeys = _build_hotkey_handlers()
    _run_hotkey_listener(hotkeys)


if __name__ == "__main__":
    main()
