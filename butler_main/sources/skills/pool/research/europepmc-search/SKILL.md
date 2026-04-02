---
name: europepmc-search
description: 搜索 Europe PMC 文献，适合生物医药和生命科学文献检索。
category: research
trigger_examples: 查Europe PMC, 生物医药论文, biomedical paper search, pubmed替代
allowed_roles: feishu-workstation-agent, butler-continuation-agent, orchestrator-agent
risk_level: low
automation_safe: true
requires_skill_read: true
status: active
source_candidate_id: europepmc-rest-biomed
upstream_name: Europe PMC RESTful Web Service
upstream_repo_or_entry: https://europepmc.org/RestfulWebService
---

# europepmc-search

这个 skill 是由 incubating 候选 `europepmc-rest-biomed` promotion 出来的真实可执行 skill。

## 上游来源

- upstream name: Europe PMC RESTful Web Service
- repo or entry: https://europepmc.org/RestfulWebService
- docs: https://europepmc.org/RestfulWebService
- original candidate path: ./butler_main/sources/skills/pool/incubating/research/europepmc-rest-biomed

## 运行方式

```powershell
& '.venv\Scripts\python.exe' `
  'butler_main/sources/skills/pool/research/europepmc-search/scripts/run.py' `
  --query 'single cell transformer' --limit 5 --output-dir '工作区/Butler/runtime/skills/europepmc-search'
```

## 输出

- 标准化 JSON
- Markdown 摘要
- 输出目录默认在 `工作区/Butler/runtime/skills/<skill-name>`

## 约束

1. 先读本 `SKILL.md`，再执行脚本
2. 若需要鉴权，优先通过环境变量传入，不把凭据写进仓库
3. 如果当前需求命中的是尚未 active 的上游候选，优先让 `skill_manager_agent` 走 promotion，再复用 active skill

