# 版本记录

两个版本都保存在这个仓库里，通过 git tag 区分，随时可以取回。

| 版本 | 标签 | 内容 | 怎么打开 |
| --- | --- | --- | --- |
| **V1 网页版** | `v1.1.0` | 每日榜单 + 中文意图搜索（连 README 正文一起搜） | 双击 `site/index.html`，或部署后的网址 |
| **V2 桌面版** | `v2.1.0` | 在 V1 基础上加原生窗口、开机自启、应用图标 | 双击 `app/start.bat`，或开机自动出现 |

```bash
git checkout v1.1.0    # 回到网页版
git checkout v2.1.0    # 回到桌面版
```

---

## v2.1.0 — 2026-11-16

桌面版修好了「开机不弹窗」，网页版的搜索也一并升级。

**修复**

- `app/open_app.py`：`pythonw.exe` 下 `sys.stdout` 是 `None`，原来那句 `print()` 直接抛异常，脚本静默退出——这就是开机后窗口不出现的真正原因。改成写 `app/boot.log` 的 `say()`，并在入口包了 `try/except` 记录异常
- `app/server.py`：同样的 `print` 隐患，改记 `app/server.log`（否则本地服务会无声消失、窗口显示旧页面）
- `scripts/publish.py`：改用 `GIT_CONFIG_COUNT` 环境变量传配置，token 只走 `http.extraheader`，不进 `.git/config`

**新增**

- `app/start.bat`：双击即开窗，优先 `pythonw` 不闪黑框，回退 `python`

## v1.1.0 — 2026-11-16

网页版搜索：不再只靠关键词。

**修复**

- 原来只按关键词搜，会漏掉「简介没写那几个词、但项目确实有用」的仓库

**新增**

- `in:readme` 正文检索：前两个检索词会额外查一次 README 全文，命中的结果标蓝并注明「简介没写 · README 里提到」
- `SYN` 同义词表（约 35 组）：「截图」自动带上 `screen capture`、`ocr`
- 星数分层：不足门槛的结果收进「放宽」栏（最多 6 条），不再混在主结果里
- 多路结果合并去重，`_rank` 标记来源，请求之间错开 350ms 防限流

## v2.0.0 — 2026-11-15

桌面版。

**新增**

- `app/open_app.py`：pywebview 原生窗口（调系统 WebView2，不打包浏览器内核）
  - 默认 430 宽贴屏幕右缘、垂直居中，可拖动可缩放，最小 340×480
  - 窗口关闭后进程退出，后台服务保留，下次打开秒开
- `app/server.py`：本地静态服务（`127.0.0.1:8801`），关掉缓存便于调试
- `app/icon.ico` / `app/icon.png`：深色圆角底 + 三条白杠 + 红点
- 开机自启：注册表 `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`

**踩过的坑**

- Edge 的 `--app=` 模式在这台机器上不弹窗（独立配置目录、默认配置都试过），改用 pywebview
- .lnk 快捷方式创建被安全策略拦截（PowerShell COM / .NET / pywin32 三条路都不通），改用注册表 Run 键
- 调试残留的 `app/.edge-profile`（约 30MB）已删除并加入 `.gitignore`

## v1.0.0 — 2026-11-15

网页版，也是全部核心逻辑所在。

**新增**

- `scripts/collect.py`：纯标准库抓取器
  - 走 GitHub 官方 API（`/search/repositories`），不爬网页
  - 四路查询：近七天新项目 / AI 与智能体 / MCP 与技能生态 / 学习资源
  - 按简介去重（批量注册的仿冒仓库简介一字不差）
  - `data/history.json` 存 star 快照，用于算 24 小时涨幅
  - 首次运行没有快照时，退化为「上线以来日均涨星」，并在页面上标注
- `site/index.html`：三栏榜单（今日涨星最快 / 与你关注方向相关 / 新冒头）
- `site/search.html`：中文意图 → 英文检索词 → GitHub 搜索
  - `DICT` 87 条映射，`COMBOS` 处理「提取 + 表格」这类拆开的组合
  - 页面显示实际使用的检索词，搜不准时能自己纠正
  - 纯前端，无中间服务器
- `config.json`：关键词与抓取范围，唯一需要手动改的文件
- `.github/workflows/daily.yml`：每天 UTC 01:00（北京 9:00）自动抓取、提交、发布 Pages
  - 构建与部署写在同一个文件的两个 job 里：`GITHUB_TOKEN` 产生的提交不会触发其他工作流，拆成两个文件的话定时任务永远触发不到部署
