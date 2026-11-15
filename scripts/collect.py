#!/usr/bin/env python3
"""GitHub 每日情报站。

做一件事：调 GitHub 官方 API，把你关注方向上值得看的仓库挑出来，
生成一个网页（site/index.html）和一份纯文本日报（digest.md）。

用法：
    python scripts/collect.py                 # 正常跑
    python scripts/collect.py --no-history    # 忽略历史，重新建基线

依赖：只用标准库。
"""

import argparse
import html
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config.json"
HISTORY = ROOT / "data" / "history.json"
SITE = ROOT / "site" / "index.html"
DIGEST = ROOT / "digest.md"
TZ = timezone(timedelta(hours=8))
API = "https://api.github.com"
TOKEN = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or ""


# ---------------------------------------------------------------- 取数

def api_get(path, params=None, tries=2):
    url = API + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    headers = {
        "User-Agent": "ai-radar/1.0",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"

    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", "replace")[:300]
            print(f"  ! HTTP {exc.code} {path} {params} -> {body}")
            if exc.code in (403, 429):          # 撞限流，等一会儿再试
                time.sleep(20)
                continue
            if exc.code == 422:                 # 查询语法不合法，换下一个
                return None
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            print(f"  ! 网络错误 {path}: {exc}")
            time.sleep(5)
    return None


def expand(query):
    """把 {7d} 这类占位符换成真实日期。"""
    seven = (date.today() - timedelta(days=7)).isoformat()
    return query.replace("{7d}", seven).replace("{30d}", (date.today() - timedelta(days=30)).isoformat())


def fetch_all(cfg):
    found, labels, failures = {}, [], []
    for i, item in enumerate(cfg["queries"]):
        label = item["label"]
        params = {"q": expand(item["q"]), "sort": item.get("sort", "stars"), "order": "desc", "per_page": cfg["per_query"]}
        print(f"[{i + 1}/{len(cfg['queries'])}] {label} ...")
        data = api_get("/search/repositories", params)
        if not data or "items" not in data:
            failures.append(label)
            continue
        labels.append(label)
        n = 0
        for repo in data["items"]:
            if repo["stargazers_count"] < cfg["min_stars"]:
                continue
            key = repo["full_name"]
            if key in found:
                if label not in found[key]["labels"]:
                    found[key]["labels"].append(label)
                continue
            found[key] = {
                "name": key,
                "url": repo["html_url"],
                "desc": (repo.get("description") or "").strip(),
                "stars": repo["stargazers_count"],
                "forks": repo["forks_count"],
                "lang": repo.get("language") or "—",
                "topics": repo.get("topics") or [],
                "created": (repo.get("created_at") or "")[:10],
                "pushed": (repo.get("pushed_at") or "")[:10],
                "labels": [label],
            }
            n += 1
        print(f"    新增 {n} 个，累计 {len(found)}")
        if i < len(cfg["queries"]) - 1:
            time.sleep(7)                        # 未登录时搜索接口 10 次/分钟
    return found, labels, failures


# ---------------------------------------------------------------- 打分

def load_history(fresh):
    if fresh or not HISTORY.exists():
        return {}
    try:
        return json.loads(HISTORY.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def score(repo, keywords, today):
    text = " ".join([repo["name"], repo["desc"], " ".join(repo["topics"])]).lower()
    hits, channels = 0, []
    for channel, words in keywords.items():
        matched = [w for w in words if w.lower() in text]
        if matched:
            hits += len(matched)
            channels.append((channel, matched))
    repo["hits"] = hits
    repo["channels"] = channels
    try:
        age = (today - date.fromisoformat(repo["created"])).days
    except ValueError:
        age = 9999
    repo["age_days"] = age
    return repo


# ---------------------------------------------------------------- 输出

def human(n):
    if n is None:
        return "—"
    if n >= 1000:
        return f"{n / 1000:.1f}k".replace(".0k", "k")
    return str(n)


def card_html(r, show_new=False, show_delta=False, show_rate=False):
    badges = []
    if show_new:
        badges.append('<span class="bdg bdg-new">新冒头</span>')
    if show_delta and r.get("delta") is not None:
        d = r["delta"]
        if d > 0:
            badges.append(f'<span class="bdg bdg-up">+{d}★</span>')
        elif d < 0:
            badges.append(f'<span class="bdg bdg-down">{d}★</span>')
    if show_rate and r.get("rate"):
        badges.append(f'<span class="bdg bdg-up">日均 +{r["rate"]:g}★</span>')
    topics = "".join(f'<span class="tag">#{html.escape(t)}</span>' for t in r["topics"][:3])
    hits = ""
    if r.get("channels"):
        words = [w for _channel, ws in r["channels"] for w in ws][:4]
        hits = '<div class="hits">命中 ' + " · ".join(html.escape(w) for w in words) + "</div>"
    desc = html.escape(r["desc"]) or '<span class="dim">（这个项目没写简介）</span>'
    meta = f'{html.escape(r["lang"])} · {human(r["stars"])} stars'
    if r["forks"] >= 100:
        meta += f' · {human(r["forks"])} forks'
    return f"""      <a class="card" href="{html.escape(r["url"])}" target="_blank" rel="noopener">
        <div class="row"><span class="name">{html.escape(r["name"])}</span>{"".join(badges)}</div>
        <div class="desc">{desc}</div>
        {hits}
        <div class="meta">{meta}</div>
        <div class="tags">{topics}</div>
      </a>"""


PAGE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>GitHub 情报站 · {{DATE}}</title>
<style>
  :root { color-scheme: light; }
  * { box-sizing: border-box; }
  body { margin: 0; padding: 44px 20px 64px; background: #F7F6F3; color: #2C2C2A;
    font-family: -apple-system, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif; line-height: 1.6; }
  .wrap { max-width: 760px; margin: 0 auto; }
  .top { display: flex; justify-content: space-between; align-items: center; gap: 12px; margin-bottom: 22px; }
  .top a { font-size: 12px; color: #185FA5; text-decoration: none; }
  .top a:hover { text-decoration: underline; }
  .top .find { font-size: 13px; color: #fff; background: #2C2C2A; border-radius: 8px;
    padding: 8px 14px; text-decoration: none; }
  .top .find:hover { background: #444441; text-decoration: none; }
  h1 { font-size: 24px; font-weight: 500; margin: 0 0 6px; letter-spacing: -0.01em; }
  .sub { font-size: 13px; color: #5F5E5A; margin-bottom: 8px; }
  .stat { font-size: 12px; color: #888780; margin-bottom: 36px; }
  h2 { font-size: 15px; font-weight: 500; margin: 40px 0 4px; display: flex; align-items: baseline; gap: 8px; }
  h2 .idx { font-size: 12px; color: #B4B2A9; font-variant-numeric: tabular-nums; }
  .hint { font-size: 12px; color: #888780; margin: 0 0 14px; }
  .card { display: block; text-decoration: none; color: inherit; background: #fff;
    border: 1px solid #E3E1DA; border-radius: 12px; padding: 16px 18px; margin-bottom: 10px;
    transition: border-color .15s; }
  .card:hover { border-color: #B4B2A9; }
  .row { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
  .name { font-size: 14px; font-weight: 500; color: #185FA5; word-break: break-all; }
  .desc { font-size: 13px; color: #444441; margin: 6px 0 8px;
    display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
  .dim { color: #B4B2A9; }
  .meta { font-size: 12px; color: #888780; font-variant-numeric: tabular-nums; }
  .tags { margin-top: 8px; display: flex; gap: 6px; flex-wrap: wrap; }
  .hits { font-size: 11px; color: #BA7517; margin: -2px 0 6px; }
  .tag { font-size: 11px; color: #5F5E5A; background: #F1EFE8; border-radius: 4px; padding: 1px 6px; }
  .bdg { font-size: 11px; border-radius: 4px; padding: 1px 6px; font-variant-numeric: tabular-nums; }
  .bdg-new { background: #FAEEDA; color: #854F0B; }
  .bdg-up { background: #FCEBEB; color: #A32D2D; }
  .bdg-down { background: #EAF3DE; color: #3B6D11; }
  .empty { background: #fff; border: 1px dashed #D3D1C7; border-radius: 12px; padding: 28px;
    text-align: center; color: #5F5E5A; font-size: 13px; }
  footer { margin-top: 48px; padding-top: 20px; border-top: 1px solid #E3E1DA;
    font-size: 12px; color: #888780; }
  footer code { background: #F1EFE8; padding: 1px 5px; border-radius: 4px; font-size: 11px; }
</style>
</head>
<body>
<div class="wrap">
  <div class="top">
    <a href="search.html" class="find">我有想做的事，帮我找工具 →</a>
  </div>
  <h1>GitHub 情报站</h1>
  <div class="sub">{{DATE}} · 每天自动更新</div>
  <div class="stat">{{STAT}}</div>
  {{BODY}}
  <footer>
    数据来自 GitHub 官方 API，按 <code>config.json</code> 里的关键词筛选。
    想调整口味就改那个文件。
  </footer>
</div>
</body>
</html>
"""


def section(title, idx, hint, items, **flags):
    if not items:
        return ""
    cards = "\n".join(card_html(r, **flags) for r in items)
    return f'  <h2><span class="idx">{idx}</span>{title}</h2>\n  <p class="hint">{hint}</p>\n{cards}\n'


def build_digest(sections, today, total, failures):
    lines = [f"# GitHub 情报站 · {today}", "", f"共扫描 {total} 个仓库" + (f"（{len(failures)} 个查询失败）" if failures else ""), ""]
    for title, _idx, hint, items, _flags in sections:
        if not items:
            continue
        lines.append(f"## {title}")
        lines.append(f"_{hint}_")
        lines.append("")
        for r in items:
            star = human(r["stars"])
            if r.get("delta"):
                mark = f"（+{r['delta']}★）"
            elif r.get("rate"):
                mark = f"（日均 +{r['rate']:g}★）"
            else:
                mark = ""
            lines.append(f"- **[{r['name']}]({r['url']})** — {star}★{mark} · {r['lang']}")
            if r["desc"]:
                lines.append(f"  {r['desc']}")
        lines.append("")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-history", action="store_true", help="忽略历史快照，重新建基线")
    args = ap.parse_args()

    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    today = datetime.now(TZ).date()
    print(f"== GitHub 情报站 {today} ==")
    print(f"认证状态：{'已带 token' if TOKEN else '未认证（限流较严）'}")

    repos, labels, failures = fetch_all(cfg)
    if not repos:
        print("没抓到任何数据，退出。")
        return 1

    history = load_history(args.no_history)
    fresh_run = not history

    for key, r in repos.items():
        score(r, cfg["keywords"], today)
        old = history.get(key)
        if old is None:
            r["delta"] = None
            r["is_new"] = True
        elif old.get("date") == today.isoformat():
            r["delta"] = old.get("delta")      # 同一天重复跑，沿用上次的增量
            r["is_new"] = False
        else:
            r["delta"] = r["stars"] - old["stars"]
            r["is_new"] = False

    all_repos = list(repos.values())

    # 榜单里常混着批量注册的仿冒仓库（简介一字不差），整族删掉
    def desc_key(desc):
        return re.sub(r"[^a-z0-9]+", "", desc.lower())[:80]

    counts = {}
    for r in all_repos:
        k = desc_key(r["desc"])
        if k:
            counts[k] = counts.get(k, 0) + 1

    kept, dropped = [], 0
    for r in all_repos:
        k = desc_key(r["desc"])
        if k and counts[k] >= 3:
            dropped += 1
            continue
        kept.append(r)
    if dropped:
        print(f"  过滤掉 {dropped} 个疑似批量仿冒仓库（简介完全相同的成组账号）")
    all_repos = kept

    for r in all_repos:
        r["rate"] = round(r["stars"] / max(r["age_days"], 1), 1)

    # 涨星榜：有历史快照就比真实增量；首次运行没有对照，改按日均涨星折算
    gainers = sorted(
        [r for r in all_repos if r.get("delta")], key=lambda r: r["delta"], reverse=True
    )[: cfg["top_gainers"]]

    if gainers:
        gainer_title = "今日涨星最快"
        gainer_hint = "跟上次扫描相比的 star 增长，涨得越快说明越多人正在关注。"
        gainer_flags = {"show_delta": True}
    else:
        gainers = sorted(
            [r for r in all_repos if r["age_days"] <= 180], key=lambda r: r["rate"], reverse=True
        )[: cfg["top_gainers"]]
        gainer_title = "近期最猛"
        gainer_hint = "还没有历史快照，这一栏先按「上线以来日均涨星」折算；明天起会自动换成真实的 24 小时涨幅。"
        gainer_flags = {"show_rate": True}

    relevant = sorted(
        [r for r in all_repos if r["hits"] > 0], key=lambda r: (r["hits"], r["stars"]), reverse=True
    )[: cfg["top_relevant"]]

    # 新冒头：只看近期创建的，否则会被几十万星的老牌清单霸榜
    newbies = sorted(
        [r for r in all_repos if r["age_days"] <= 120], key=lambda r: r["rate"], reverse=True
    )[: cfg["top_new"]]

    sections = [
        (gainer_title, "01", gainer_hint, gainers, gainer_flags),
        ("与你关注方向相关", "02", "命中你在 config.json 里写的关键词，按匹配度和热度排序。", relevant, {}),
        ("近期新冒头的项目", "03", "近 120 天内创建、按日均涨星排序 —— 这些才是可能改变格局的东西。", newbies, {"show_new": True, "show_rate": True}),
    ]

    body = "\n".join(section(t, i, h, items, **f) for t, i, h, items, f in sections)
    if not body.strip():
        body = '<div class="empty">这次没有符合条件的仓库，试试放宽 config.json 里的 min_stars。</div>'

    stat = f"扫描 {len(all_repos)} 个仓库 · 命中关注方向 {len(relevant)} 个 · 查询 {len(labels)} 条"
    if failures:
        stat += f" · {len(failures)} 条查询失败"

    SITE.parent.mkdir(parents=True, exist_ok=True)
    SITE.write_text(
        PAGE.replace("{{DATE}}", today.isoformat()).replace("{{STAT}}", stat).replace("{{BODY}}", body),
        encoding="utf-8",
    )

    DIGEST.write_text(build_digest(sections, today, len(all_repos), failures), encoding="utf-8")

    snapshot = {}
    for key, r in repos.items():
        old = history.get(key, {})
        snapshot[key] = {
            "stars": r["stars"],
            "date": today.isoformat(),
            "delta": r.get("delta"),
            "first_seen": old.get("first_seen", today.isoformat()),
        }
    HISTORY.parent.mkdir(parents=True, exist_ok=True)
    HISTORY.write_text(json.dumps(snapshot, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"\n完成：{len(all_repos)} 个仓库，涨星榜 {len(gainers)}，相关 {len(relevant)}，新发现 {len(newbies)}")
    print(f"网页  -> {SITE.relative_to(ROOT)}")
    print(f"日报  -> {DIGEST.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
