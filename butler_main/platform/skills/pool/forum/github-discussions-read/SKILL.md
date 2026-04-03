---
name: github-discussions-read
description: 读取 GitHub Discussions 列表或单条讨论，适合开源社区支持区、路线图讨论和 FAQ 整理。
category: forum
trigger_examples: 读GitHub Discussions, repo社区讨论, maintainer faq, discussion线程
allowed_roles: feishu-workstation-agent, butler-continuation-agent, orchestrator-agent
risk_level: medium
automation_safe: false
requires_skill_read: true
status: active
source_candidate_id: github-discussions-graphql
upstream_name: GitHub Discussions GraphQL API
upstream_repo_or_entry: https://docs.github.com/en/graphql/guides/using-the-graphql-api-for-discussions
---

# github-discussions-read

这个 skill 是由 incubating 候选 `github-discussions-graphql` promotion 出来的真实可执行 skill。

## 上游来源

- upstream name: GitHub Discussions GraphQL API
- repo or entry: https://docs.github.com/en/graphql/guides/using-the-graphql-api-for-discussions
- docs: https://docs.github.com/en/graphql/guides/using-the-graphql-api-for-discussions
- original candidate path: ./butler_main/platform/skills/pool/incubating/forum/github-discussions-graphql

## 运行方式

```powershell
& '.venv\Scripts\python.exe' `
  'butler_main/platform/skills/pool/forum/github-discussions-read/scripts/run.py' `
  --owner 'openai' --repo 'openai-python' --limit 5 --github-token-env GITHUB_TOKEN --output-dir '工作区/Butler/runtime/skills/github-discussions-read'
```

## 输出

- 标准化 JSON
- Markdown 摘要
- 输出目录默认在 `工作区/Butler/runtime/skills/<skill-name>`

## 约束

1. 先读本 `SKILL.md`，再执行脚本
2. 若需要鉴权，优先通过环境变量传入，不把凭据写进仓库
3. 如果当前需求命中的是尚未 active 的上游候选，优先让 `skill_manager_agent` 走 promotion，再复用 active skill

