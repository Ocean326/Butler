---
name: reddit-thread-read
description: 读取 Reddit 主题帖或 subreddit 列表，输出标题、分数、评论摘要，适合做社区舆情和帖子梳理。
category: forum
trigger_examples: 看Reddit热帖, 抓reddit评论, subreddit监控, reddit thread
allowed_roles: feishu-workstation-agent, butler-continuation-agent, orchestrator-agent
risk_level: medium
automation_safe: false
requires_skill_read: true
status: active
source_candidate_id: praw-reddit-ingest
upstream_name: PRAW
upstream_repo_or_entry: https://github.com/praw-dev/praw
---

# reddit-thread-read

这个 skill 是由 incubating 候选 `praw-reddit-ingest` promotion 出来的真实可执行 skill。

## 上游来源

- upstream name: PRAW
- repo or entry: https://github.com/praw-dev/praw
- docs: https://praw.readthedocs.io/en/stable/
- original candidate path: ./butler_main/platform/skills/pool/incubating/forum/praw-reddit-ingest

## 运行方式

```powershell
& '.venv\Scripts\python.exe' `
  'butler_main/platform/skills/pool/forum/reddit-thread-read/scripts/run.py' `
  --subreddit 'LocalLLaMA' --sort hot --limit 5 --output-dir '工作区/Butler/runtime/skills/reddit-thread-read'
```

## 输出

- 标准化 JSON
- Markdown 摘要
- 输出目录默认在 `工作区/Butler/runtime/skills/<skill-name>`

## 约束

1. 先读本 `SKILL.md`，再执行脚本
2. 若需要鉴权，优先通过环境变量传入，不把凭据写进仓库
3. 如果当前需求命中的是尚未 active 的上游候选，优先让 `skill_manager_agent` 走 promotion，再复用 active skill

