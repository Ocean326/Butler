---
name: skill-incubating-promote
description: 将 `sources/skills/pool/incubating/` 下的候选 skill 提升为真实可执行的 active skill；若命中未转换候选，先做转换，再供后续复用。
category: operations
trigger_examples: 转换未实现 skill, promote incubating skill, 把候选变成真 skill, 命中未转换skill先转换
allowed_roles: feishu-workstation-agent, butler-continuation-agent, orchestrator-agent
risk_level: medium
automation_safe: false
requires_skill_read: true
status: active
---

# Skill Incubating Promote

当某个候选 skill 已经在 `sources/skills/pool/incubating/` 中落库，但还没有真实执行脚本时，使用本 skill 把它转换为可执行的 active skill。

## 目标

1. 读取 incubating 候选的 intake 数据
2. 生成 active skill 目录、`SKILL.md`、`references/`、`scripts/run.py`
3. 产出 promotion 报告与转换 registry
4. 后续若再次命中该能力，优先复用已转换 skill，而不是重复造轮子

## 当前边界

- 支持一批预定义的上游能力模板
- 对未支持自动转换的候选，会明确报出仍需人工实现
- promotion 不自动把新 skill 暴露到默认 collection，collection 暴露由 registry 独立治理

## 入口脚本

- `./butler_main/platform/skills/pool/ops/skill-incubating-promote/scripts/promote_incubating_skills.py`

## 标准用法

```powershell
& '.venv\Scripts\python.exe' `
  'butler_main/platform/skills/pool/ops/skill-incubating-promote/scripts/promote_incubating_skills.py' `
  --workspace '.' `
  --ids 'feedparser-rss-ingest,hackernews-api-ingest,stackexchange-api-ingest,arxiv-py-paper-retrieval'
```

全部支持项重建：

```powershell
& '.venv\Scripts\python.exe' `
  'butler_main/platform/skills/pool/ops/skill-incubating-promote/scripts/promote_incubating_skills.py' `
  --workspace '.' `
  --all-supported `
  --replace
```

## 输出

1. `sources/skills/pool/<domain>/<skill-name>/`
2. `butler_main/platform/skills/temp/promote/skill_promotion_report.json`
3. `butler_main/platform/skills/temp/promote/skill_promotion_report.md`
4. `sources/skills/agent/skill_manager_agent/references/upstream_skill_conversion_registry.json`

## 使用约定

1. 如果能力已经是 active skill，优先复用
2. 如果命中的是 incubating 候选且支持自动 promotion，先 promotion，再使用
3. 如果不支持自动 promotion，明确说明需要人工实现，不要假装已可执行

