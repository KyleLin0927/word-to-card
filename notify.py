import logging
import os
import subprocess

import config

log = logging.getLogger(__name__)

# macOS 通知內文過長可能異常；略截斷即可
_MAX_LEN = 240


def _applescript_literal(s: str) -> str:
    """供包在 AppleScript 雙引號字串內；避免換行、反斜線、雙引號弄壞腳本。"""
    t = (s or "").replace("\r\n", "\n").replace("\r", "\n")
    t = " ".join(t.split())
    t = t.replace("\\", "\\\\").replace('"', '\\"')
    if len(t) > _MAX_LEN:
        t = t[: _MAX_LEN - 1] + "…"
    return t


def notify(title: str, message: str) -> None:
    """透過 macOS 通知中心顯示通知。"""
    t = _applescript_literal(title) or "Word to Card"
    m = _applescript_literal(message) or " "
    script = f'display notification "{m}" with title "{t}"'
    try:
        cp = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if cp.returncode != 0:
            log.warning(
                "osascript 通知失敗 returncode=%s stderr=%r stdout=%r",
                cp.returncode,
                (cp.stderr or "").strip(),
                (cp.stdout or "").strip(),
            )
    except Exception as e:
        log.warning("通知執行失敗：%s", e)


def _play_success_sound() -> None:
    if not config.NOTIFY_SUCCESS_SOUND:
        return
    path = config.NOTIFY_SUCCESS_SOUND_FILE or "/System/Library/Sounds/Glass.aiff"
    if not os.path.isfile(path):
        log.warning("成功音效檔不存在，略過：%s", path)
        return
    try:
        subprocess.Popen(
            ["afplay", path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception as e:
        log.warning("播放成功音效失敗：%s", e)


def notify_success(title: str, message: str) -> None:
    """
    實際新增卡片後使用：仍送通知中心，並加上不依賴橫幅顯示的備援（預設短音效）。
    """
    notify(title, message)
    _play_success_sound()
