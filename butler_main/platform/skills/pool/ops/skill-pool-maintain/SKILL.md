---
name: skill-pool-maintain
description: 盘点、整理并生成 Butler 全局 skill 池的维护报告，重点检查目录布局、frontmatter 完整度、可迁移建议与 collection 暴露建议。
category: operations
family_id: skill-governance
family_label: Skill 治理族
family_summary: 面向 skill 池盘点、校验与治理；命中后再区分维护建议还是一致性验证。
family_trigger_examples: 整理 skill 池, 校验 registry, 治理 skill
variant_rank: 10
trigger_examples: 整理 skill 池, 维护 skill 资产, skill 盘点, skill organize
allowed_roles: feishu-workstation-agent, butler-continuation-agent, orchestrator-agent
risk_level: low
automation_safe: true
requires_skill_read: true
---

# Skill Pool Maintain

当需要对 Butler 当前 skill 池做资产盘点、整理建议、暴露建议时，使用本 skill。

## 入口脚本

- `./butler_main/platform/skills/pool/ops/skill-pool-maintain/scripts/maintain_skill_pool.py`

## 标准用法

```powershell
& '.venv\Scripts\python.exe' `
  'butler_main/platform/skills/pool/ops/skill-pool-maintain/scripts/maintain_skill_pool.py' `
  --workspace '.' `
  --output-dir 'butler_main/platform/skills/temp/maintain'
```

## 产出

- `skill_pool_inventory.json`
- `skill_pool_maintenance_report.md`

## 检查重点

1. `sources/skills/pool/` 内有哪些 skill
2. 哪些仍然只在 legacy `butler_bot_agent/skills/` 下
3. 哪些 skill frontmatter 缺少关键字段
4. 哪些 skill 还没有进入任何 collection
5. 哪些 skill 名称、分类、路径存在整理建议

## 注意事项

- 本 skill 只生成维护建议，不直接批量改写 skill。
- 如果要实际调整 registry 或目录，需基于报告再执行修改。

