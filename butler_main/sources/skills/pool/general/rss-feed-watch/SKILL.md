---
name: rss-feed-watch
description: 拉取 RSS / Atom feed，输出最近条目摘要，适合做订阅监控、更新跟踪和摘要生成。
category: general
trigger_examples: 订阅RSS, 监控feed, 抓博客更新, 拉取Atom
allowed_roles: feishu-workstation-agent, butler-continuation-agent, orchestrator-agent
risk_level: low
automation_safe: true
requires_skill_read: true
status: active
source_candidate_id: feedparser-rss-ingest
upstream_name: feedparser
upstream_repo_or_entry: https://github.com/kurtmckee/feedparser
---

# rss-feed-watch

这个 skill 是由 incubating 候选 `feedparser-rss-ingest` promotion 出来的真实可执行 skill。

## 上游来源

- upstream name: feedparser
- repo or entry: https://github.com/kurtmckee/feedparser
- docs: https://feedparser.readthedocs.io/en/latest/
- original candidate path: ./butler_main/sources/skills/pool/incubating/general/feedparser-rss-ingest

## 运行方式

```powershell
& '.venv\Scripts\python.exe' `
  'butler_main/sources/skills/pool/general/rss-feed-watch/scripts/run.py' `
  --feed 'https://example.com/feed.xml' --limit 5 --output-dir '工作区/Butler/runtime/skills/rss-feed-watch'
```

## 输出

- 标准化 JSON
- Markdown 摘要
- 输出目录默认在 `工作区/Butler/runtime/skills/<skill-name>`

## 约束

1. 先读本 `SKILL.md`，再执行脚本
2. 若需要鉴权，优先通过环境变量传入，不把凭据写进仓库
3. 如果当前需求命中的是尚未 active 的上游候选，优先让 `skill_manager_agent` 走 promotion，再复用 active skill

