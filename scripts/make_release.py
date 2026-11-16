"""把 dist/ 里的两个 zip 发到 GitHub Release。

token 从环境变量 GH_TOKEN/GITHUB_TOKEN 或 ~/.gh_token 读，只在内存里用。
证书走 _ca.pem（schannel 在本机报 CRYPT_E_NO_REVOCATION_CHECK）。
"""

import json
import os
import ssl
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OWNER, REPO = "xidesua", "github-radar"
API = "https://api.github.com"
UPLOADS = "https://uploads.github.com"


def token():
    t = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if t:
        return t.strip()
    p = Path.home() / ".gh_token"
    if p.exists():
        return p.read_text(encoding="utf-8").strip()
    sys.exit("找不到 token：设 GH_TOKEN 或写入 ~/.gh_token")


TOKEN = token()
CTX = ssl.create_default_context()
CA = ROOT / "_ca.pem"
if CA.exists():
    CTX.load_verify_locations(str(CA))


def call(method, url, payload=None, ctype="application/json", raw=None):
    body = raw if raw is not None else (
        json.dumps(payload).encode() if payload is not None else None)
    req = urllib.request.Request(url, data=body, method=method, headers={
        "Authorization": "Bearer " + TOKEN,
        "Accept": "application/vnd.github+json",
        "User-Agent": "github-radar",
        "Content-Type": ctype,
    })
    try:
        with urllib.request.urlopen(req, timeout=120, context=CTX) as r:
            return json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        detail = e.read().decode()[:400]
        print(f"  ! {method} {url} -> {e.code} {detail}")
        return None


def get_release(tag):
    req = urllib.request.Request(
        f"{API}/repos/{OWNER}/{REPO}/releases/tags/{tag}",
        headers={"Authorization": "Bearer " + TOKEN,
                 "User-Agent": "github-radar"})
    try:
        with urllib.request.urlopen(req, timeout=30, context=CTX) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise


def upsert(tag, name, body, asset):
    rel = get_release(tag)
    if rel is None:
        rel = call("POST", f"{API}/repos/{OWNER}/{REPO}/releases",
                   {"tag_name": tag, "name": name, "body": body,
                    "draft": False, "prerelease": False})
        if not rel:
            sys.exit(f"创建 Release {tag} 失败")
        print(f"  创建 Release {tag}")
    else:
        print(f"  Release {tag} 已存在，复用")

    existing = {a["name"]: a["id"] for a in rel.get("assets", [])}
    path = ROOT / "dist" / asset
    if asset in existing:
        call("DELETE", f"{API}/repos/{OWNER}/{REPO}/releases/assets/{existing[asset]}")
        print(f"  覆盖旧资产 {asset}")

    up = call("POST",
              f"{UPLOADS}/repos/{OWNER}/{REPO}/releases/{rel['id']}/assets"
              f"?name={asset}&label={asset}",
              ctype="application/zip", raw=path.read_bytes())
    if up:
        print(f"  上传 {asset} ({up.get('size', 0)/1024:.1f} KB)")
    else:
        print(f"  ! 上传 {asset} 失败")
    return rel.get("html_url")


WEB_BODY = """网页版：每日榜单 + 中文意图搜索。

## 这次改了什么

原来只按关键词搜，会漏掉「简介没写那几个词、但项目确实有用」的仓库。

- **`in:readme` 正文检索**：前两个检索词额外查一次 README 全文，命中的结果标蓝并注明「简介没写 · README 里提到」
- **`SYN` 同义词表**（约 35 组）：「截图」自动带上 `screen capture`、`ocr`
- **星数分层**：不足门槛的结果收进「放宽」栏（最多 6 条），不再混在主结果里
- **多路合并去重**，请求之间错开 350ms 防限流

## 怎么用

下载 `github-radar-web-1.1.0.zip`，解压，双击 `site/index.html`。零依赖，不用装 Python。

线上版：https://xidesua.github.io/github-radar/
"""

DESK_BODY = """桌面版：原生窗口 + 开机自启 + 应用图标。

## 修好了「开机不弹窗」

这是上个版本最影响使用的问题，原因很具体：

- `app/open_app.py`：`pythonw.exe` 下 `sys.stdout` 是 `None`，原来那句 `print()` 直接抛异常，脚本静默退出，所以开机后什么都看不到。改成写 `app/boot.log` 的 `say()`，并在入口包了 `try/except` 记录异常
- `app/server.py`：同样的 `print` 隐患，改记 `app/server.log`（否则本地服务会无声消失、窗口显示旧页面）
- `scripts/publish.py`：改走环境变量传 git 配置，token 不进 `.git/config`

## 新增

- `app/start.bat`：双击即开窗，优先 `pythonw` 不闪黑框，没有就回退 `python`

## 怎么用

1. 下载 `github-radar-desktop-2.1.0.zip`，解压
2. 装依赖：`pip install pywebview`
3. 双击 `app/start.bat`

窗口默认贴屏幕右侧，可拖动缩放。开机自启要手动加一次注册表 Run 项（README 里有）。
"""

if __name__ == "__main__":
    print("发 Release：")
    upsert("v1.1.0", "v1.1.0 网页版 — 搜索升级", WEB_BODY, "github-radar-web-1.1.0.zip")
    time.sleep(1)
    upsert("v2.1.0", "v2.1.0 桌面版 — 修复开机不弹窗", DESK_BODY, "github-radar-desktop-2.1.0.zip")
    print("完成")
