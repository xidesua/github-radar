# GitHub 情报站

每天扫一遍 GitHub，挑出三样东西给你：**今天涨得最快的**、**跟你关注方向相关的**、**最近冒出来的新项目**。生成一个网页 + 一份文本日报。

不用懂代码，只用知道两件事：看哪个文件、改哪个文件。

---

## 现在就能看

双击 `site/index.html`，浏览器打开就是今天的榜单。桌面上有个「GitHub 情报站」快捷方式，直接点它。

想要纯文字版，看 `digest.md`。

## 有个想做的事？搜一下

点首页上方的「我有想做的事，帮我找工具 →」，或者直接开 `site/search.html`。

左边输入中文，比如「把长视频剪成短视频」，它会：

1. 把中文意图翻成英文检索词（`video editor`、`ffmpeg`）
2. 拿去 GitHub 官方搜索接口查
3. 按星标 / 更新时间 / 相关度排序，列出还能用的仓库

页面上会显示它实际用了哪些检索词 —— 搜得不准时，你就知道该换个说法了。

映射表在 `search.html` 里的 `DICT`（87 个中文说法），`COMBOS` 处理「提取+表格」这种拆开的组合。想加词直接往里加。

搜索是**纯前端**的，页面直接调 GitHub 接口，没有中间服务器。代价是未登录时每分钟只能查 10 次，点太密会被拦一下。

## 想每天自动更新，两种方式

### 方式一：留在自己电脑上（最省事）

```
python scripts/collect.py
```

想每天自动跑，告诉我，我给你挂一个每天早上的定时任务。

### 方式二：扔到 GitHub 上跑（电脑关机也照跑）

```bash
cd ai-radar
git init -b main && git add . && git commit -m "init"
git remote add origin https://github.com/<你的用户名>/<仓库名>.git
git push -u origin main
```

然后去仓库 **Settings → Pages → Source 选 `GitHub Actions`**。

之后每天北京时间 9:00，它会自己抓、自己生成、自己发布到
`https://<你的用户名>.github.io/<仓库名>/`。手机上收藏这个链接就能每天看。

## 想调口味，只改一个文件

打开 `config.json`：

```json
"keywords": {
  "AI 与智能体": ["agent", "llm", "mcp", "rag"],
  "能力提升": ["awesome", "roadmap", "tutorial"]
}
```

- 觉得太少 → 加词
- 觉得跑偏 → 删词
- 想加个新方向 → 照格式加一行

`queries` 那段决定「去哪儿捞」，不是必须动的。

## 三件事你需要知道

1. **今天这一栏是折算值。** 第一次跑没有历史数据可比，所以「近期最猛」用的是「上线以来日均涨星」。从明天起会变成真实的 24 小时涨幅 —— 那才是真的有人在投票。
2. **简介是英文的。** 我没有在这里接翻译，因为多一层就多一个会挂的地方。看不懂名字就先点进去，GitHub 页面右上角有自动翻译。
3. **GitHub 只是一个信号源。** 它反映的是「程序员正在关注什么」，不等于「什么对你有用」。真要提升能力，看完还得动手用一个。

## 技术说明（可以跳过）

- 只用 Python 标准库，不需要 `pip install`。
- 走 GitHub 官方 API（`/search/repositories`），不爬网页。网页那份在国内经常连不上，API 稳定得多。
- 未登录时搜索接口限 10 次/分钟，脚本内置了间隔；在 Actions 里带 token 是 30 次/分钟。
- 历史快照存在 `data/history.json`，用来算涨幅。

| 文件 | 作用 |
| --- | --- |
| `config.json` | 你唯一需要改的：关键词、抓取范围 |
| `scripts/collect.py` | 抓取 + 打分 + 生成页面 |
| `data/history.json` | 每天的 star 快照，算涨幅用 |
| `site/index.html` | 网页版日报（自动生成） |
| `site/search.html` | 搜索页：中文描述 → 找对应仓库 |
| `digest.md` | 文字版日报（自动生成） |
| `.github/workflows/daily.yml` | 每天定时跑的配置 |
