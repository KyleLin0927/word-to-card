import os
import subprocess
import sys
import time

import config

_MIN_SELECTION_PX = 5


def _output_path() -> str:
    os.makedirs(config.CAPTURES_DIR, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    return os.path.join(config.CAPTURES_DIR, f"capture_{timestamp}.png")


def _take_screenshot_macos(path: str) -> bool:
    result = subprocess.run(
        ["screencapture", "-i", path],
        capture_output=True,
    )
    return (
        result.returncode == 0
        and os.path.exists(path)
        and os.path.getsize(path) > 0
    )


def _interactive_region_capture(path: str) -> bool:
    """
    全螢幕 overlay 框選區域並存成 PNG。
    須在獨立行程／主執行緒呼叫（tkinter 限制）。
    """
    import tkinter as tk
    from PIL import ImageGrab

    state: dict[str, object] = {"bbox": None, "cancelled": False}
    start_screen = [0, 0]
    start_local = [0, 0]
    rect_id: list[object] = [None]

    root = tk.Tk()
    root.withdraw()

    overlay = tk.Toplevel(root)
    overlay.attributes("-fullscreen", True)
    overlay.attributes("-alpha", 0.3)
    overlay.attributes("-topmost", True)
    overlay.configure(bg="black", cursor="crosshair")

    canvas = tk.Canvas(overlay, highlightthickness=0, bg="black")
    canvas.pack(fill=tk.BOTH, expand=True)

    def _finish() -> None:
        overlay.destroy()
        root.quit()

    def on_press(event: tk.Event) -> None:
        start_screen[0], start_screen[1] = event.x_root, event.y_root
        start_local[0], start_local[1] = event.x, event.y
        if rect_id[0] is not None:
            canvas.delete(rect_id[0])
        rect_id[0] = canvas.create_rectangle(
            event.x,
            event.y,
            event.x,
            event.y,
            outline="red",
            width=2,
        )

    def on_drag(event: tk.Event) -> None:
        if rect_id[0] is None:
            return
        canvas.coords(rect_id[0], start_local[0], start_local[1], event.x, event.y)

    def on_release(event: tk.Event) -> None:
        x1, y1 = min(start_screen[0], event.x_root), min(start_screen[1], event.y_root)
        x2, y2 = max(start_screen[0], event.x_root), max(start_screen[1], event.y_root)
        if (x2 - x1) < _MIN_SELECTION_PX or (y2 - y1) < _MIN_SELECTION_PX:
            return
        state["bbox"] = (x1, y1, x2, y2)
        _finish()

    def on_escape(_event: tk.Event | None = None) -> None:
        state["cancelled"] = True
        _finish()

    canvas.bind("<ButtonPress-1>", on_press)
    canvas.bind("<B1-Motion>", on_drag)
    canvas.bind("<ButtonRelease-1>", on_release)
    overlay.bind("<Escape>", on_escape)
    root.bind("<Escape>", on_escape)

    root.mainloop()
    root.destroy()

    if state["cancelled"] or not state["bbox"]:
        return False

    bbox = state["bbox"]
    assert isinstance(bbox, tuple)
    img = ImageGrab.grab(bbox=bbox)
    img.save(path, "PNG")
    return os.path.exists(path) and os.path.getsize(path) > 0


def _take_screenshot_interactive_subprocess(path: str) -> bool:
    """在子行程執行 tkinter 框選（供背景執行緒的熱鍵 callback 使用）。"""
    result = subprocess.run(
        [sys.executable, __file__, "--capture", path],
        capture_output=True,
    )
    return result.returncode == 0


def take_screenshot() -> str | None:
    """
    互動式區域截圖，存至 captures/ 目錄。
    macOS 使用 screencapture；Windows 等使用 overlay 框選。
    使用者取消或失敗時回傳 None。
    """
    path = _output_path()

    try:
        if sys.platform == "darwin":
            ok = _take_screenshot_macos(path)
        else:
            ok = _take_screenshot_interactive_subprocess(path)
    except Exception:
        ok = False

    if not ok:
        if os.path.exists(path):
            os.unlink(path)
        return None

    return path


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "--capture":
        dest = sys.argv[2]
        sys.exit(0 if _interactive_region_capture(dest) else 1)
    print("用法: python screenshot.py --capture <輸出路徑>", file=sys.stderr)
    sys.exit(2)
