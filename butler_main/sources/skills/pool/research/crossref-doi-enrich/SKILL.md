---
name: crossref-doi-enrich
description: 按 DOI 或 bibliographic query 获取 Crossref 元数据，适合 DOI 补全和参考文献规范化。
category: research
trigger_examples: 补DOI信息, Crossref元数据, reference normalize, 论文元数据补全
allowed_roles: feishu-workstation-agent, butler-continuation-agent, orchestrator-agent
risk_level: low
automation_safe: true
requires_skill_read: true
status: active
source_candidate_id: crossref-rest-metadata
upstream_name: Crossref REST API
upstream_repo_or_entry: https://www.crossref.org/documentation/retrieve-metadata/rest-api/
---

# crossref-doi-enrich

这个 skill 是由 incubating 候选 `crossref-rest-metadata` promotion 出来的真实可执行 skill。

## 上游来源

- upstream name: Crossref REST API
- repo or entry: https://www.crossref.org/documentation/retrieve-metadata/rest-api/
- docs: https://www.crossref.org/documentation/retrieve-metadata/rest-api/
- original candidate path: ./butler_main/sources/skills/pool/incubating/research/crossref-rest-metadata

## 运行方式

```powershell
& '.venv\Scripts\python.exe' `
  'butler_main/sources/skills/pool/research/crossref-doi-enrich/scripts/run.py' `
  --query 'attention is all you need' --limit 5 --output-dir '工作区/Butler/runtime/skills/crossref-doi-enrich'
```

## 输出

- 标准化 JSON
- Markdown 摘要
- 输出目录默认在 `工作区/Butler/runtime/skills/<skill-name>`

## 约束

1. 先读本 `SKILL.md`，再执行脚本
2. 若需要鉴权，优先通过环境变量传入，不把凭据写进仓库
3. 如果当前需求命中的是尚未 active 的上游候选，优先让 `skill_manager_agent` 走 promotion，再复用 active skill

