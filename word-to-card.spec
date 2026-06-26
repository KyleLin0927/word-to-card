# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller 打包設定（onefile、console）。

本機打包：
    pyinstaller word-to-card.spec
產物：
    dist/word-to-card        （macOS / Linux）
    dist/word-to-card.exe    （Windows）

對容易被靜態分析漏掉的套件使用 collect_all，確保子模組與資料檔一併打包：
- google.genai：Gemini SDK
- edge_tts    ：發音 TTS
- pynput      ：全域熱鍵
- certifi     ：TLS 憑證（google.genai / edge_tts 連線需要）

pynput 會「動態」import 各平台的鍵盤／滑鼠後端，PyInstaller 靜態分析抓不到，
必須依 build 平台明確補上，否則打包後執行會出現 ImportError：
- Linux  ：Xlib（python-xlib）
- macOS  ：pyobjc 的 Quartz / AppKit 等
- Windows：純 ctypes，無需額外套件

tkinter / PIL 由 PyInstaller 內建 hook 自動納入（非 macOS 的框選截圖會用到）。
"""

import sys

from PyInstaller.utils.hooks import collect_all


def _safe_collect_all(pkg):
    """collect_all，但套件不存在時不讓打包中斷（用於平台限定的後端套件）。"""
    try:
        return collect_all(pkg)
    except Exception:
        return ([], [], [])


datas = []
binaries = []
hiddenimports = []

_packages = ["google.genai", "edge_tts", "pynput", "certifi"]
if sys.platform.startswith("linux"):
    _packages.append("Xlib")
elif sys.platform == "darwin":
    _packages += ["Quartz", "AppKit", "Foundation", "objc", "CoreFoundation", "ApplicationServices"]

for _pkg in _packages:
    _d, _b, _h = _safe_collect_all(_pkg)
    datas += _d
    binaries += _b
    hiddenimports += _h

# 非 macOS 的框選截圖在函式內 import tkinter 與 PIL.ImageGrab；
# 明確列為 hidden import，確保被打包。
# 前提：build 環境本身要有 tkinter（CI 的 setup-python 已內含；
# 若在 Linux 自行打包，需先安裝系統的 python3-tk）。
hiddenimports += ["tkinter", "PIL.ImageGrab"]

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="word-to-card",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # 不用 UPX：避免 Windows 防毒誤判與壓縮相容性問題
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # 背景 CLI 工具，需 stdout 輸出 log
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,  # 跟隨 build 主機架構（macos-13=x86_64、macos-latest=arm64）
    codesign_identity=None,
    entitlements_file=None,
)
