#!/usr/bin/env python3
"""本地静态服务：把 site/ 目录挂在 127.0.0.1:8801。

只在后台跑，不弹窗口。桌面窗口关掉它也不会死，下次打开秒开。
想彻底关掉：任务管理器里结束 pythonw，或者重启电脑。
"""

import os
import sys
import threading
import time
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PORT = 8801
SITE = Path(__file__).resolve().parent.parent / "site"
LOG = Path(__file__).resolve().parent / "server.log"


def say(msg):
    """pythonw 下 sys.stdout 是 None，直接 print 会崩，所以统一走这里。"""
    line = f"{time.strftime('%m-%d %H:%M:%S')} {msg}"
    try:
        if sys.stdout is not None:
            print(line, flush=True)
    except Exception:
        pass
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


class Quiet(SimpleHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def end_headers(self):
        # 关掉缓存，改了页面刷新就能看到
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


def already_running():
    import socket

    with socket.socket() as s:
        s.settimeout(0.3)
        return s.connect_ex(("127.0.0.1", PORT)) == 0


def main():
    if not SITE.is_dir():
        say(f"找不到目录：{SITE}")
        return 1
    if already_running():
        say(f"端口 {PORT} 已在服务，跳过")
        return 0

    handler = partial(Quiet, directory=str(SITE))
    httpd = ThreadingHTTPServer(("127.0.0.1", PORT), handler)
    say(f"serving {SITE} on http://127.0.0.1:{PORT}")
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        thread.join()
    except KeyboardInterrupt:
        httpd.shutdown()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception:
        import traceback

        say("服务异常:\n" + traceback.format_exc())
