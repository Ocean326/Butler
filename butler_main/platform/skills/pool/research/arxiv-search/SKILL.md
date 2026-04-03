---
name: arxiv-search
description: 搜索 arXiv 论文并输出标题、作者、摘要和链接，适合研究主题跟踪和论文初筛。
category: research
trigger_examples: 查arxiv, 搜论文, arxiv主题跟踪, 研究论文检索
allowed_roles: feishu-workstation-agent, butler-continuation-agent, orchestrator-agent
risk_level: low
automation_safe: true
requires_skill_read: true
status: active
source_candidate_id: arxiv-py-paper-retrieval
upstream_name: arxiv.py
upstream_repo_or_entry: https://github.com/lukasschwab/arxiv.py
---

# arxiv-search

这个 skill 是由 incubating 候选 `arxiv-py-paper-retrieval` promotion 出来的真实可执行 skill。

## 上游来源

- upstream name: arxiv.py
- repo or entry: https://github.com/lukasschwab/arxiv.py
- docs: https://lukasschwab.me/arxiv.py/
- original candidate path: ./butler_main/platform/skills/pool/incubating/research/arxiv-py-paper-retrieval

## 运行方式

```powershell
& '.venv\Scripts\python.exe' `
  'butler_main/platform/skills/pool/research/arxiv-search/scripts/run.py' `
  --query 'reasoning models' --limit 5 --output-dir '工作区/Butler/runtime/skills/arxiv-search'
```

## 输出

- 标准化 JSON
- Markdown 摘要
- 输出目录默认在 `工作区/Butler/runtime/skills/<skill-name>`

## 约束

1. 先读本 `SKILL.md`，再执行脚本
2. 若需要鉴权，优先通过环境变量传入，不把凭据写进仓库
3. 如果当前需求命中的是尚未 active 的上游候选，优先让 `skill_manager_agent` 走 promotion，再复用 active skill

