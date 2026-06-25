"""跨平台小工具：複製修飾鍵、權限提示等。"""

import sys

from pynput.keyboard import Key


def copy_modifier_key() -> Key:
    """模擬「複製」時使用的修飾鍵：macOS 為 Cmd，其餘為 Ctrl。"""
    return Key.cmd if sys.platform == "darwin" else Key.ctrl


def input_permission_hint() -> str:
    """無法模擬按鍵／攔截熱鍵時的通知內文。"""
    if sys.platform == "darwin":
        return "請到 系統設定→隱私權與安全性→輔助使用 開啟權限"
    if sys.platform == "win32":
        return "請以系統管理員執行終端機，或允許程式使用鍵盤 hook"
    return "請確認已授予鍵盤／輔助權限"
