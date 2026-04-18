"""
離線任務佇列
當 Gemini 或 AnkiConnect 連線失敗時，將截圖路徑存入 pending_tasks.json。
下次啟動時自動重試。
"""

import json
import os
from datetime import datetime

import config
import history_logger


def _load() -> list[dict]:
    if not os.path.exists(config.QUEUE_FILE):
        return []
    with open(config.QUEUE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save(tasks: list[dict]) -> None:
    with open(config.QUEUE_FILE, "w", encoding="utf-8") as f:
        json.dump(tasks, f, ensure_ascii=False, indent=2)


def enqueue(image_path: str) -> None:
    """將失敗的截圖路徑加入待重試佇列。"""
    tasks = _load()
    tasks.append({
        "image_path": image_path,
        "queued_at": datetime.now().isoformat(),
    })
    _save(tasks)
    print(f"[佇列] 已加入待重試：{image_path}")


def pending_count() -> int:
    return len(_load())


def process_queue(analyze_fn, add_cards_fn, record_fn) -> int:
    """
    重試佇列中所有待處理的截圖。
    成功後刪除截圖檔案，失敗的留在佇列。
    回傳本次成功處理的數量。
    """
    tasks = _load()
    if not tasks:
        return 0

    remaining: list[dict] = []
    success_count = 0

    for task in tasks:
        path = task["image_path"]

        # 截圖檔案已消失（可能被手動刪除）
        if not os.path.exists(path):
            print(f"[佇列] 截圖已消失，跳過：{path}")
            continue

        try:
            words = analyze_fn(path)
            if words:
                # 佇列重試也必須做歷史去重 + 同批去重
                words = history_logger.filter_new(words)

            if words:
                # add_cards_fn 需回傳逐筆結果（note id / None）
                results = add_cards_fn(words)
                added_words = [w for w, r in zip(words, results) if r is not None]
                if added_words:
                    record_fn(added_words)
                if added_words:
                    print(f"[佇列] 重試成功，新增 {len(added_words)} 張卡片")
                else:
                    print("[佇列] 全部為 duplicate（Anki 已存在），已移除此任務")
            else:
                # 全部都被去重/已收錄，視為已處理完成，直接移除佇列
                print("[佇列] 無新單字（已收錄/重複），已移除此任務")
            os.unlink(path)
            success_count += 1
        except Exception as e:
            print(f"[佇列] 重試失敗，保留至下次：{e}")
            remaining.append(task)

    _save(remaining)
    return success_count
