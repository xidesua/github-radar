"""打包两个可下载版本：纯网页版 / 桌面版。

用 git archive 导出，这样 .gitattributes 里的换行规则会被应用，
.bat 出来是 CRLF。不依赖 .git 目录，也不含 _ca.pem、日志、缓存。
"""

import io
import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent   # 项目根，不是 scripts/
OUT = ROOT / "dist"
OUT.mkdir(exist_ok=True)

WEB_VER = "1.1.0"
DESK_VER = "2.1.0"


def archive(ref):
    """git archive 到内存，返回 {仓库内相对路径: 内容}。不带目录前缀。"""
    raw = subprocess.run(
        ["git", "archive", "--format=zip", ref],
        cwd=ROOT, capture_output=True, check=True,
    ).stdout
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        return {n: z.read(n) for n in z.namelist() if not n.endswith("/")}


def build(path, prefix, files):
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for name, data in sorted(files.items()):
            z.writestr(f"{prefix}/{name}", data)
    return path.stat().st_size


# ---- 网页版：只要 site/ ----
web = {n: d for n, d in archive("v1.1.0").items() if n.startswith("site/")}
web_prefix = f"github-radar-web-{WEB_VER}"
web_size = build(OUT / f"{web_prefix}.zip", web_prefix, web)
print(f"web     : {len(web)} 个文件, {web_size/1024:.1f} KB")

# ---- 桌面版：整份项目，去掉用不上的 ----
SKIP = (".github/", ".gitignore", ".gitattributes", ".workbuddy/")
desk = {n: d for n, d in archive("v2.1.0").items() if not n.startswith(SKIP)}
desk_prefix = f"github-radar-desktop-{DESK_VER}"
desk_size = build(OUT / f"{desk_prefix}.zip", desk_prefix, desk)
print(f"desktop : {len(desk)} 个文件, {desk_size/1024:.1f} KB")

# 校验 bat 换行与关键文件齐全
with zipfile.ZipFile(OUT / f"{desk_prefix}.zip") as z:
    bat = z.read(f"{desk_prefix}/app/start.bat")
    names = z.namelist()
print("start.bat CRLF:", b"\r\n" in bat)
print("关键文件:", [n.split("/", 1)[1] for n in names if n.count("/") == 1][:12])
