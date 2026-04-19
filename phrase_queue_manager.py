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


def process_queue(analyze_fn, add_cards_fn, record_fn) -> int:
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
            phrases = analyze_fn(path)
            if phrases:
                phrases = phrase_history.filter_new(phrases)

            if phrases:
                results = add_cards_fn(phrases)
                added = [p for p, r in zip(phrases, results) if r is not None]
                if added:
                    record_fn(added)
                    print(f"[片語佇列] 重試成功，新增 {len(added)} 張卡片")
                else:
                    print("[片語佇列] 全部為 duplicate，已移除此任務")
            else:
                print("[片語佇列] 無新片語（已收錄／無合格），已移除此任務")
            os.unlink(path)
            success_count += 1
        except Exception as e:
            print(f"[片語佇列] 重試失敗，保留至下次：{e}")
            remaining.append(task)

    _save(remaining)
    return success_count
