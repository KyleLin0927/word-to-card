"""
片語截圖失敗離線佇列（與 queue_manager / pending_tasks.json 分離）
"""

import json
import os
from datetime import datetime

import config
import phrase_history


def _load() -> list[dict]:
    if not os.path.exists(config.QUEUE_FILE_PHRASE):
        return []
    with open(config.QUEUE_FILE_PHRASE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save(tasks: list[dict]) -> None:
    with open(config.QUEUE_FILE_PHRASE, "w", encoding="utf-8") as f:
        json.dump(tasks, f, ensure_ascii=False, indent=2)


def enqueue(image_path: str) -> None:
    tasks = _load()
    tasks.append({"image_path": image_path, "queued_at": datetime.now().isoformat()})
    _save(tasks)
    print(f"[片語佇列] 已加入待重試：{image_path}")


def pending_count() -> int:
    return len(_load())


def process_queue(
    analyze_fn,
    add_phrases_fn,
    record_phrases_fn,
    *,
    add_words_fn=None,
    record_words_fn=None,
) -> int:
    tasks = _load()
    if not tasks:
        return 0

    remaining: list[dict] = []
    success_count = 0

    for task in tasks:
        path = task["image_path"]
        if not os.path.exists(path):
            print(f"[片語佇列] 截圖已消失，跳過：{path}")
            continue

        try:
            analysis = analyze_fn(path)
            collocations = getattr(analysis, "collocations", None)
            chunks = getattr(analysis, "chunks", None)
            if collocations is None and chunks is None:
                collocations = analysis or []
                chunks = []

            collocations = phrase_history.filter_new(collocations or [])
            if add_words_fn and record_words_fn and chunks:
                from history_logger import filter_new as filter_new_words

                chunks = filter_new_words(chunks)

            did_any = False
            if chunks and add_words_fn and record_words_fn:
                results = add_words_fn(chunks)
                added = [w for w, r in zip(chunks, results) if r is not None]
                if added:
                    record_words_fn(added)
                    print(f"[片語佇列] chunk 重試成功，新增 {len(added)} 張單字卡")
                    did_any = True

            if collocations:
                results = add_phrases_fn(collocations)
                added = [p for p, r in zip(collocations, results) if r is not None]
                if added:
                    record_phrases_fn(added)
                    print(f"[片語佇列] collocation 重試成功，新增 {len(added)} 張片語卡")
                    did_any = True

            if did_any:
                print("[片語佇列] 重試成功，已移除此任務")
            else:
                print("[片語佇列] 無新內容（已收錄／無合格），已移除此任務")
            os.unlink(path)
            success_count += 1
        except Exception as e:
            print(f"[片語佇列] 重試失敗，保留至下次：{e}")
            remaining.append(task)

    _save(remaining)
    return success_count
