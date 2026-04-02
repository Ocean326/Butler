---
name: openalex-search
description: 搜索 OpenAlex works / authors 等实体，适合研究图谱、机构作者和主题全景检索。
category: research
trigger_examples: 查OpenAlex, 研究图谱, 作者机构检索, 学术全景
allowed_roles: feishu-workstation-agent, butler-continuation-agent, orchestrator-agent
risk_level: medium
automation_safe: false
requires_skill_read: true
status: active
source_candidate_id: openalex-pyalex
upstream_name: OpenAlex plus PyAlex
upstream_repo_or_entry: https://github.com/J535D165/pyalex
---

# openalex-search

这个 skill 是由 incubating 候选 `openalex-pyalex` promotion 出来的真实可执行 skill。

## 上游来源

- upstream name: OpenAlex plus PyAlex
- repo or entry: https://github.com/J535D165/pyalex
- docs: https://docs.openalex.org/
- original candidate path: ./butler_main/sources/skills/pool/incubating/research/openalex-pyalex

## 运行方式

```powershell
& '.venv\Scripts\python.exe' `
  'butler_main/sources/skills/pool/research/openalex-search/scripts/run.py' `
  --query 'large language model agents' --entity-type works --limit 5 --output-dir '工作区/Butler/runtime/skills/openalex-search'
```

## 输出

- 标准化 JSON
- Markdown 摘要
- 输出目录默认在 `工作区/Butler/runtime/skills/<skill-name>`

## 约束

1. 先读本 `SKILL.md`，再执行脚本
2. 若需要鉴权，优先通过环境变量传入，不把凭据写进仓库
3. 如果当前需求命中的是尚未 active 的上游候选，优先让 `skill_manager_agent` 走 promotion，再复用 active skill

