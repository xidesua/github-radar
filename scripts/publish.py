#!/usr/bin/env python3
"""把情报站发布到你的 GitHub 账号。

用法：
    export GH_TOKEN=ghp_xxxx            # PowerShell: $env:GH_TOKEN="ghp_xxxx"
    python scripts/publish.py ai-radar

做的事：
    1. 用 token 查出你的用户名
    2. 仓库不存在就建一个（默认公开，Pages 免费）
    3. 配上 remote 并推送 main
    4. 打印 Pages 设置链接和部署后的网址

token 只在这一次调用里用到，不写进 .git/config，也不写到磁盘。
只用标准库，Windows 上遇到证书问题会自动降级到 openssl 后端。
"""

from __future__ import annotations

import base64
import json
import os
import ssl
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
API = "https://api.github.com"


# ---------- GitHub API ----------

def api(method: str, path: str, token: str, payload: dict | None = None):
    data = json.dumps(payload).encode() if payload else None
    req = urllib.request.Request(
        API + path,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "ai-radar-publish",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            body = r.read()
            return r.status, (json.loads(body) if body else {})
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:400]
        return e.code, {"message": detail}


# ---------- git ----------

def git(args: list[str], env_extra: dict | None = None, check: bool = True):
    env = os.environ.copy()
    if env_extra:
        env.update(env_extra)
    p = subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, env=env,
        encoding="utf-8", errors="replace",
    )
    if check and p.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} 失败：\n{p.stdout}{p.stderr}")
    return p


def ca_bundle() -> str | None:
    """把系统根证书导出成 PEM，给 git 的 openssl 后端用。"""
    try:
        ctx = ssl.create_default_context()
        certs = ctx.get_ca_certs(binary_form=True)
        if not certs:
            return None
        fd, path = tempfile.mkstemp(suffix=".pem", prefix="ai-radar-ca-")
        with os.fdopen(fd, "wb") as f:
            for c in certs:
                f.write(ssl.DER_cert_to_PEM_cert(c).encode())
        return path
    except Exception:
        return None


def push(remote_url: str, branch: str, token: str) -> None:
    """先按系统默认证书推；失败且是证书问题时，降级到 openssl + 系统 CA。"""
    auth = base64.b64encode(f"x-access-token:{token}".encode()).decode()
    base_cfg = {
        "GIT_CONFIG_COUNT": "3",
        "GIT_CONFIG_KEY_0": "http.extraheader",
        "GIT_CONFIG_VALUE_0": f"AUTHORIZATION: basic {auth}",
        "GIT_CONFIG_KEY_1": "http.postBuffer",
        "GIT_CONFIG_VALUE_1": "52428800",
        "GIT_CONFIG_KEY_2": "credential.helper",
        "GIT_CONFIG_VALUE_2": "",
    }

    p = git(["push", remote_url, f"HEAD:refs/heads/{branch}"], base_cfg, check=False)
    if p.returncode == 0:
        return

    out = p.stdout + p.stderr
    cert_issue = any(k in out for k in ("schannel", "certificate", "CRYPT_E", "SSL"))
    if not cert_issue:
        raise RuntimeError(f"推送失败：\n{out}")

    print("  系统证书校验不通，改用 openssl 后端重试…")
    ca = ca_bundle()
    if not ca:
        raise RuntimeError(f"推送失败，且无法导出系统 CA：\n{out}")

    cfg = dict(base_cfg)
    cfg.update({
        "GIT_CONFIG_COUNT": "5",
        "GIT_CONFIG_KEY_3": "http.sslBackend",
        "GIT_CONFIG_VALUE_3": "openssl",
        "GIT_CONFIG_KEY_4": "http.sslCAInfo",
        "GIT_CONFIG_VALUE_4": ca,
    })
    try:
        git(["push", remote_url, f"HEAD:refs/heads/{branch}"], cfg)
    finally:
        try:
            os.unlink(ca)
        except OSError:
            pass


# ---------- 主流程 ----------

def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    flags = {a for a in sys.argv[1:] if a.startswith("-")}
    repo = args[0] if args else "ai-radar"
    private = "--private" in flags
    dry = "--dry-run" in flags

    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""
    if not token:
        print("缺少 token。\n")
        print("  1. 打开 https://github.com/settings/tokens → Generate new token (classic)")
        print("  2. 勾选 repo 这一项，生成后复制（只显示一次）")
        print("  3. 回来执行：")
        print('       export GH_TOKEN=ghp_xxxx        # PowerShell: $env:GH_TOKEN="ghp_xxxx"')
        print(f"       python scripts/publish.py {repo}")
        return 1

    status, me = api("GET", "/user", token)
    if status != 200:
        print(f"token 无效或没有权限（HTTP {status}）：{me.get('message', '')[:200]}")
        return 1
    login = me["login"]
    print(f"账号：{login}")

    status, info = api("GET", f"/repos/{login}/{repo}", token)
    if status == 200:
        print(f"仓库已存在：{info['html_url']}")
        full = info["full_name"]
        default_branch = info.get("default_branch") or "main"
    elif status == 404:
        print(f"仓库不存在，创建 {login}/{repo}（{'私有' if private else '公开'}）…")
        if dry:
            print("  --dry-run，跳过创建")
            return 0
        status, info = api("POST", "/user/repos", token, {
            "name": repo,
            "description": "每天扫一遍 GitHub，挑出涨得最快的、跟你关注方向相关的、刚冒头的新项目。",
            "private": private,
            "has_issues": True,
            "has_wiki": False,
            "auto_init": False,
        })
        if status not in (200, 201):
            print(f"创建失败（HTTP {status}）：{info.get('message', '')[:300]}")
            return 1
        full, default_branch = info["full_name"], "main"
        print(f"  已创建：{info['html_url']}")
    else:
        print(f"查询仓库失败（HTTP {status}）：{info.get('message', '')[:200]}")
        return 1

    branch = git(["rev-parse", "--abbrev-ref", "HEAD"]).stdout.strip() or "main"
    if git(["status", "--porcelain"]).stdout.strip():
        print("提示：还有未提交的改动，这次不会带上。先 git add -A && git commit。")

    remote_url = f"https://github.com/{full}.git"
    print(f"推送 {branch} → {remote_url}")
    if dry:
        print("  --dry-run，跳过推送")
        return 0
    push(remote_url, branch, token)
    print("  推送完成")

    git(["remote", "remove", "origin"], check=False)
    git(["remote", "add", "origin", remote_url], check=False)

    pages_on = bool(info.get("has_pages"))
    print()
    print("=" * 58)
    print(f"仓库      : {info['html_url']}")
    print(f"Actions   : {info['html_url']}/actions")
    print(f"Pages 设置: {info['html_url']}/settings/pages")
    if pages_on:
        print(f"网址      : https://{login}.github.io/{repo}/")
    else:
        print()
        print("最后一步（必须做）：")
        print("  上面 Pages 设置页 → Source 选「GitHub Actions」→ Save")
        print(f"  然后到 Actions 页手动跑一次，网址就是 https://{login}.github.io/{repo}/")
    print("=" * 58)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except RuntimeError as e:
        print(f"\n出错了：{e}")
        sys.exit(1)
