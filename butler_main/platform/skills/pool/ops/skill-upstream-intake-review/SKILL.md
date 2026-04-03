---
name: skill-upstream-intake-review
description: 将外部 API / library 候选上游导入 Butler 本地 incubating skill 池，生成逐项审阅结果和落库报告，解决“不是现成 SKILL 仓库、但值得转成 Butler skill”的 intake/review 问题。
category: operations
family_id: skill-intake
family_label: Skill 引入族
family_summary: 面向外部 skill 的引入、审阅与本地落库；命中后再区分直接导入还是先做 intake review。
family_trigger_examples: 导入 skill, 上游审阅, 拉到本地
variant_rank: 20
trigger_examples: 导入候选 skill, 审阅外部 skill, 把论坛科研 skill 落到本地, intake upstream skills
allowed_roles: feishu-workstation-agent, butler-continuation-agent, orchestrator-agent
risk_level: low
automation_safe: true
requires_skill_read: true
status: active
---

# Skill Upstream Intake Review

当外部候选不是现成的 `SKILL.md` 仓库，而是 API、SDK、Python library 或官方数据源时，使用本 skill。

## 本 skill 的目标

1. 把候选上游落成 `sources/skills/pool/incubating/` 下的本地草案 skill 资产
2. 为每个候选生成独立的 `SKILL.md`、`UPSTREAM_REVIEW.md`、`UPSTREAM_INTAKE.json`
3. 生成一份总览报告，便于 `skill_manager_agent` 或人工逐项审阅

## 本 skill 的边界

- 这是“导入候选并审阅”，不是“直接可运行生产 skill”
- 不自动把草案 skill 加入任何 collection
- 不自动安装第三方依赖，也不假装已经实现执行脚本
- 如果后续要对外暴露，必须经过实现、测试、verify、registry 审阅

## 入口脚本

- `./butler_main/platform/skills/pool/ops/skill-upstream-intake-review/scripts/intake_upstream_candidates.py`

## 标准用法

```powershell
& '.venv\Scripts\python.exe' `
  'butler_main/platform/skills/pool/ops/skill-upstream-intake-review/scripts/intake_upstream_candidates.py' `
  --workspace '.' `
  --candidates-file 'butler_main/platform/skills/agent/skill_manager_agent/references/external_skill_candidates_2026-03-24.json' `
  --dest-root 'butler_main/platform/skills/pool/incubating' `
  --output-dir 'butler_main/platform/skills/temp/upstream-review'
```

只处理部分候选时：

```powershell
& '.venv\Scripts\python.exe' `
  'butler_main/platform/skills/pool/ops/skill-upstream-intake-review/scripts/intake_upstream_candidates.py' `
  --workspace '.' `
  --ids 'trafilatura-web-extract,praw-reddit-ingest,arxiv-py-paper-retrieval'
```

## 产出

1. `sources/skills/pool/incubating/<domain>/<candidate-id>/SKILL.md`
2. `sources/skills/pool/incubating/<domain>/<candidate-id>/UPSTREAM_REVIEW.md`
3. `sources/skills/pool/incubating/<domain>/<candidate-id>/UPSTREAM_INTAKE.json`
4. `butler_main/platform/skills/temp/upstream-review/skill_upstream_intake_report.md`
5. `butler_main/platform/skills/temp/upstream-review/skill_upstream_intake_report.json`

## 审阅要求

1. 明确标记 `status: incubating`
2. 在 `UPSTREAM_REVIEW.md` 写清：
   - 为什么值得做成 Butler skill
   - 主要风险
   - 是否建议进入第一批实现
3. 不要把 incubating 资产误加入默认 collection

## 注意事项

- 如果候选文件不存在或格式不合法，本 skill 应直接失败
- 如果目标目录已存在，默认保守跳过；需要覆盖时显式加 `--replace`
- `incubating` 资产允许放进 `sources/skills/pool/`，但默认不应进入运行时 catalog 暴露面

