---
name: skill-pool-verify
description: 校验 Butler skill 池与 collection registry 的完整性，识别坏路径、重复 skill 名、缺少 `SKILL.md`、缺 frontmatter、未命中的 collection 暴露项。
category: operations
family_id: skill-governance
family_label: Skill 治理族
family_summary: 面向 skill 池盘点、校验与治理；命中后再区分维护建议还是一致性验证。
family_trigger_examples: 整理 skill 池, 校验 registry, 治理 skill
variant_rank: 20
trigger_examples: 验证 skill 池, 校验 skill registry, 检查 collection, verify skills
allowed_roles: feishu-workstation-agent, butler-continuation-agent, orchestrator-agent
risk_level: low
automation_safe: true
requires_skill_read: true
---

# Skill Pool Verify

当你需要确认 `sources/skills` 以及 collection registry 当前是否健康可用时，使用本 skill。

## 入口脚本

- `./butler_main/platform/skills/pool/ops/skill-pool-verify/scripts/verify_skill_pool.py`

## 标准用法

```powershell
& '.venv\Scripts\python.exe' `
  'butler_main/platform/skills/pool/ops/skill-pool-verify/scripts/verify_skill_pool.py' `
  --workspace '.' `
  --output-dir 'butler_main/platform/skills/temp/verify'
```

## 校验内容

1. registry 文件是否存在且可解析
2. collection 中每个 skill 路径是否真实存在
3. 每个 skill 是否包含 `SKILL.md`
4. 是否缺失关键 frontmatter 字段
5. 是否有重复 skill 名
6. 是否存在引用了非法根目录的 skill 路径

## 产出

- `skill_pool_verify.json`
- `skill_pool_verify_report.md`

## 注意事项

- 本 skill 默认只读，不自动修复。
- 如发现问题，应把修复动作写成明确变更，而不是只停留在口头告警。

