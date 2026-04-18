import logging
import subprocess

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
