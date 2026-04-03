---
name: semantic-scholar-search
description: 搜索 Semantic Scholar 文献或指定 paper id，输出摘要、引用数和链接，适合 citation 扩展。
category: research
trigger_examples: 查Semantic Scholar, citation扩展, related papers, 论文引用图
allowed_roles: feishu-workstation-agent, butler-continuation-agent, orchestrator-agent
risk_level: medium
automation_safe: false
requires_skill_read: true
status: active
source_candidate_id: semantic-scholar-api
upstream_name: Semantic Scholar API
upstream_repo_or_entry: https://www.semanticscholar.org/product/api
---

# semantic-scholar-search

这个 skill 是由 incubating 候选 `semantic-scholar-api` promotion 出来的真实可执行 skill。

## 上游来源

- upstream name: Semantic Scholar API
- repo or entry: https://www.semanticscholar.org/product/api
- docs: https://www.semanticscholar.org/product/api
- original candidate path: ./butler_main/platform/skills/pool/incubating/research/semantic-scholar-api

## 运行方式

```powershell
& '.venv\Scripts\python.exe' `
  'butler_main/platform/skills/pool/research/semantic-scholar-search/scripts/run.py' `
  --query 'chain of thought prompting' --limit 5 --output-dir '工作区/Butler/runtime/skills/semantic-scholar-search'
```

## 输出

- 标准化 JSON
- Markdown 摘要
- 输出目录默认在 `工作区/Butler/runtime/skills/<skill-name>`

## 约束

1. 先读本 `SKILL.md`，再执行脚本
2. 若需要鉴权，优先通过环境变量传入，不把凭据写进仓库
3. 如果当前需求命中的是尚未 active 的上游候选，优先让 `skill_manager_agent` 走 promotion，再复用 active skill

