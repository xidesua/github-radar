#!/usr/bin/env python3
"""「GitHub 情报站」桌面窗口。

1. 确保本地服务在跑（127.0.0.1:8801，没跑就悄悄起一个）
2. 用 pywebview 开一个原生窗口，默认摆在屏幕右侧，可拖动、可缩放
3. 窗口关掉后进程退出；后台服务留着，下次秒开

用 pythonw.exe 跑就没有黑色命令行窗口。
加 --check 只打印诊断信息，不开窗。
"""

import ctypes
import ctypes.wintypes
import socket
import subprocess
import sys
import time
from pathlib import Path

PORT = 8801
HERE = Path(__file__).resolve().parent
URL = f"http://127.0.0.1:{PORT}/index.html"


def port_open(port=PORT, timeout=0.3):
    with socket.socket() as s:
        s.settimeout(timeout)
        return s.connect_ex(("127.0.0.1", port)) == 0


def screen_size():
    """工作区尺寸（不含任务栏）。不设 DPI 感知，让系统按 DIP 缩放。"""
    try:
        rect = ctypes.wintypes.RECT()
        ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(rect), 0)
        return rect.right - rect.left, rect.bottom - rect.top
    except Exception:
        return 1920, 1040


def ensure_server(dry=False):
    if port_open():
        return "已在运行"
    if dry:
        return "需要启动（dry-run 未启动）"
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    exe = pythonw if pythonw.exists() else Path(sys.executable)
    subprocess.Popen(
        [str(exe), str(HERE / "server.py")],
        cwd=str(HERE),
        creationflags=0x00000008 | 0x08000000,  # DETACHED_PROCESS | CREATE_NO_WINDOW
        close_fds=True,
    )
    for _ in range(50):
        time.sleep(0.1)
        if port_open():
            return "已启动"
    return "启动失败"


def geometry():
    w, h = screen_size()
    width = 430
    height = max(600, min(940, h - 80))
    return width, height, max(0, w - width - 16), max(0, (h - height) // 2)


def main():
    dry = "--check" in sys.argv
    width, height, x, y = geometry()
    status = ensure_server(dry)

    print(f"屏幕工作区 : {screen_size()[0]} x {screen_size()[1]}")
    print(f"窗口       : 位置 {x},{y}  尺寸 {width}x{height}")
    print(f"本地服务   : {status}")

    if dry:
        return 0
    if "启动失败" in status:
        print("本地服务没能启动，退出。")
        return 1

    import webview

    webview.create_window(
        "GitHub 情报站",
        URL,
        width=width,
        height=height,
        x=x,
        y=y,
        min_size=(340, 480),
    )
    webview.start()
    return 0


if __name__ == "__main__":
    sys.exit(main())
