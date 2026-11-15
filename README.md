# GitHub 情报站

每天扫一遍 GitHub，挑出三样东西：**今天涨得最快的**、**跟你关注方向相关的**、**最近冒出来的新项目**。生成一个网页 + 一份文本日报。

- 打开就用：`site/index.html`
- 有个想做的事？`site/search.html` 里用中文描述，它去找对应的开源库
- 想每天自动更新、电脑关机也照跑？推到 GitHub，用 Actions + Pages（下面有步骤）

---

## 两个版本

| 版本 | git 标签 | 多出来的东西 | 怎么打开 |
| --- | --- | --- | --- |
| **V1 网页版** | `v1.0.0` | 每日榜单 + 中文搜索页 | 双击 `site/index.html` |
| **V2 桌面版** | `v2.0.0` | 原生窗口、开机自启、应用图标 | 开机自动出现 |

```bash
git checkout v1.0.0    # 回到纯网页版
git checkout v2.0.0    # 回到桌面版
```

细节见 [`CHANGELOG.md`](CHANGELOG.md)。

## 目录

```
ai-radar/
├─ config.json               # 你唯一需要改的：关键词、抓取范围
├─ scripts/collect.py        # 抓取 + 打分 + 生成页面（纯标准库）
├─ scripts/publish.py        # 一条命令发布到你的 GitHub
├─ data/history.json         # star 快照，算涨幅用
├─ site/index.html           # 网页版日报（自动生成）
├─ site/search.html          # 搜索页：中文描述 → 找对应仓库
├─ digest.md                 # 文字版日报（自动生成）
├─ app/open_app.py           # V2：pywebview 原生窗口
├─ app/server.py             # V2：本地静态服务 127.0.0.1:8801
└─ .github/workflows/daily.yml   # 每天定时跑
```

## 本地跑

```bash
python scripts/collect.py      # 抓一次，更新页面和日报
python app/open_app.py         # V2：开桌面窗口（会自动拉起本地服务）
python app/open_app.py --check # 只打印窗口位置和服务状态，不开窗
```

不需要 `pip install`，只用 Python 标准库。桌面窗口额外需要 `pywebview`。

## 发布到 GitHub

### 一条命令

```bash
export GH_TOKEN=ghp_你的token          # PowerShell: $env:GH_TOKEN="ghp_..."
python scripts/publish.py ai-radar     # 最后一个是仓库名
```

脚本会：建仓库（已存在就复用）→ 配好 remote → 推送 → 给你 Pages 设置链接。token 只在内存里用一次，不写进 `.git/config`。

token 去 [Settings → Tokens](https://github.com/settings/tokens) 建，勾 `repo` 就行。

### 或者手动

```bash
git remote add origin https://github.com/<你的用户名>/<仓库名>.git
git push -u origin main
```

推完**必须**做这一步，否则部署会失败（第一次用的人一半栽在这）：

> 仓库 → **Settings → Pages → Source 选 `GitHub Actions`** → Save

之后每天北京时间 9:00，它自己抓、自己生成、自己发布到
`https://<你的用户名>.github.io/<仓库名>/`。手机上收藏就能每天看。

**注意**：Pages 对公开仓库免费，私有仓库要 Pro。这个仓库的内容都是公开的 GitHub 数据，设成公开没风险，只是 `config.json` 里的关注词会被人看到。

## 调口味

打开 `config.json`：

```json
"keywords": {
  "AI 与智能体": ["agent", "llm", "mcp", "rag"],
  "能力提升": ["awesome", "roadmap", "tutorial"]
}
```

- 太少 → 加词
- 跑偏 → 删词
- 新方向 → 照格式加一行

`queries` 那段决定「去哪儿捞」，一般不用动。

## 三件需要知道的事

1. **第一次跑没有涨幅数据。** 没有历史快照时，「今日涨星最快」用的是「上线以来日均涨星」，页面上会写明。第二天起才是真实的 24 小时涨幅。
2. **简介是英文的。** 没接翻译——多一层就多一个会挂的地方。看不懂就先点进去，GitHub 页面右上角有自动翻译。
3. **GitHub 只是一个信号源。** 它反映「程序员在关注什么」，不等于「什么对你有用」。

## 技术说明

- 走 GitHub 官方 API，不爬网页。网页版在国内经常连不上，API 稳定得多。
- 未登录搜索接口限 10 次/分钟，脚本内置间隔；Actions 里带 token 是 30 次/分钟。
- 抓到的榜单里混着批量注册的仿冒仓库（简介一字不差），按简介指纹去重。
- 构建与部署写在同一个 workflow 文件的两个 job 里：`GITHUB_TOKEN` 产生的提交不会触发其他工作流，拆成两个文件的话定时任务永远触发不到部署。
- 仓库 60 天没有活动，定时任务会被 GitHub 自动暂停——偶尔推一次东西就能续上。
