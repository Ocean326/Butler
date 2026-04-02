---
name: hackernews-thread-watch
description: 读取 Hacker News 热门或指定线程，输出标题、分数、评论摘要，适合开发工具和 AI 讨论跟踪。
category: forum
trigger_examples: 看HN热帖, Hacker News监控, HN评论抓取, yc新闻
allowed_roles: feishu-workstation-agent, butler-continuation-agent, orchestrator-agent
risk_level: low
automation_safe: true
requires_skill_read: true
status: active
source_candidate_id: hackernews-api-ingest
upstream_name: Hacker News API
upstream_repo_or_entry: https://github.com/HackerNews/API
---

# hackernews-thread-watch

这个 skill 是由 incubating 候选 `hackernews-api-ingest` promotion 出来的真实可执行 skill。

## 上游来源

- upstream name: Hacker News API
- repo or entry: https://github.com/HackerNews/API
- docs: https://github.com/HackerNews/API
- original candidate path: ./butler_main/sources/skills/pool/incubating/forum/hackernews-api-ingest

## 运行方式

```powershell
& '.venv\Scripts\python.exe' `
  'butler_main/sources/skills/pool/forum/hackernews-thread-watch/scripts/run.py' `
  --mode topstories --limit 10 --output-dir '工作区/Butler/runtime/skills/hackernews-thread-watch'
```

## 输出

- 标准化 JSON
- Markdown 摘要
- 输出目录默认在 `工作区/Butler/runtime/skills/<skill-name>`

## 约束

1. 先读本 `SKILL.md`，再执行脚本
2. 若需要鉴权，优先通过环境变量传入，不把凭据写进仓库
3. 如果当前需求命中的是尚未 active 的上游候选，优先让 `skill_manager_agent` 走 promotion，再复用 active skill

