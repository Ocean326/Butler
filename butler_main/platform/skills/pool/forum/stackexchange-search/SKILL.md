---
name: stackexchange-search
description: 搜索 Stack Exchange / Stack Overflow 问答，输出问题标题、答案数和链接，适合技术问题对照检索。
category: forum
trigger_examples: 搜stackoverflow, 查技术问答, stackexchange检索, accepted answer
allowed_roles: feishu-workstation-agent, butler-continuation-agent, orchestrator-agent
risk_level: low
automation_safe: true
requires_skill_read: true
status: active
source_candidate_id: stackexchange-api-ingest
upstream_name: Stack Exchange API
upstream_repo_or_entry: https://api.stackexchange.com/docs
---

# stackexchange-search

这个 skill 是由 incubating 候选 `stackexchange-api-ingest` promotion 出来的真实可执行 skill。

## 上游来源

- upstream name: Stack Exchange API
- repo or entry: https://api.stackexchange.com/docs
- docs: https://api.stackexchange.com/docs
- original candidate path: ./butler_main/platform/skills/pool/incubating/forum/stackexchange-api-ingest

## 运行方式

```powershell
& '.venv\Scripts\python.exe' `
  'butler_main/platform/skills/pool/forum/stackexchange-search/scripts/run.py' `
  --query 'useEffectEvent React' --site stackoverflow --limit 5 --output-dir '工作区/Butler/runtime/skills/stackexchange-search'
```

## 输出

- 标准化 JSON
- Markdown 摘要
- 输出目录默认在 `工作区/Butler/runtime/skills/<skill-name>`

## 约束

1. 先读本 `SKILL.md`，再执行脚本
2. 若需要鉴权，优先通过环境变量传入，不把凭据写进仓库
3. 如果当前需求命中的是尚未 active 的上游候选，优先让 `skill_manager_agent` 走 promotion，再复用 active skill

