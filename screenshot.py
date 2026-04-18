import os
import subprocess
import time

import config


def take_screenshot() -> str | None:
    """
    開啟 macOS 互動式截圖選框，將截圖存至 captures/ 目錄。
    使用者按下 Esc 或截圖失敗時回傳 None。
    """
    os.makedirs(config.CAPTURES_DIR, exist_ok=True)

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    path = os.path.join(config.CAPTURES_DIR, f"capture_{timestamp}.png")

    result = subprocess.run(
        ["screencapture", "-i", path],
        capture_output=True,
    )

    if result.returncode != 0 or not os.path.exists(path) or os.path.getsize(path) == 0:
        if os.path.exists(path):
            os.unlink(path)
        return None

    return path
