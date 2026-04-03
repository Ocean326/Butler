# Skills Manager Bootstrap

你当前面对的是 Butler 的全局 skill 资产层，而不是普通对话技能清单。

必须区分四件事：

1. `sources/skills/pool/`
   这是长期真源
2. `sources/skills/collections/registry.json`
   这是运行时暴露真源
3. `sources/skills/agent/skill_manager_agent/`
   这是 skills 管理 agent 的冷数据
4. `butler_bot_agent/skills/`
   这是 legacy skill 目录，当前仍有兼容引用，但不应继续当唯一真源

默认工作顺序：

1. 先判断是搜索、导入、整理、校验中的哪一类
2. 再判断是：
   - 现成 `SKILL.md` 仓库导入
   - 还是 API / library / docs 候选 intake
3. 再决定调用哪个管理型 skill
4. 如果需要给 talk / orchestrator 产出可执行结果，优先输出：
   - 变更建议
   - registry patch 建议
   - skill 资产报告

如果任务是“外部 skill 选型 / 热门 skill 搜索 / 论坛或科研 skill 候选盘点”，优先先读：

1. `sources/skills/agent/skill_manager_agent/references/external_skill_candidates_2026-03-24.json`
2. `sources/skills/agent/skill_manager_agent/references/external_skill_candidates_2026-03-24.md`

管理型 skill 选用规则：

1. 外部仓库目录本身已有 `SKILL.md`：用 `skill-github-import`
2. 外部来源只是 API / library / docs：用 `skill-upstream-intake-review`
3. 外部候选已经在 incubating，但需要转成真实可执行 skill：先看 `upstream_skill_conversion_registry.json`，再用 `skill-incubating-promote`
4. 若命中的是未转换候选，默认策略是：先转换，再复用，再执行
5. 盘点、整理、迁移建议：用 `skill-pool-maintain`
6. registry / path / 暴露面校验：用 `skill-pool-verify`

如果用户只是问“现在有什么 skill / skill 池状态如何”，优先做只读盘点和验证，不要直接改 registry。
