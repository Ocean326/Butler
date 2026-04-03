# Managed Ops Skills

`skill_manager_agent` 默认优先管理以下 ops skills：

1. `./butler_main/platform/skills/pool/ops/skill-github-import`
2. `./butler_main/platform/skills/pool/ops/skill-pool-maintain`
3. `./butler_main/platform/skills/pool/ops/skill-pool-verify`
4. `./butler_main/platform/skills/pool/ops/skill-upstream-intake-review`
5. `./butler_main/platform/skills/pool/ops/memory-curation`
6. `./butler_main/platform/skills/pool/ops/skill-incubating-promote`

使用约定：

1. 搜外部候选 skill：先看 `skill_manager_agent/references/external_skill_candidates_2026-03-24.*`
2. 外部仓库本身已经是 `SKILL.md` 结构：用 `skill-github-import`
3. 外部来源只是 API / library / docs：用 `skill-upstream-intake-review`
4. 命中 incubating 候选且需要先变成可执行 skill：用 `skill-incubating-promote`
5. 整理/盘点/迁移建议：用 `skill-pool-maintain`
6. 校验 registry 和 path 健康度：用 `skill-pool-verify`
7. 巡检或清洗 chat 记忆资产：用 `memory-curation`
8. 所有 skill 管理过程态报告默认进 `./butler_main/platform/skills/temp/<task>/`；只有正式运行结果才进入正式结果目录

默认 collection：

- `skill_ops`

默认不直接暴露给自动化路由的高风险动作：

- GitHub 导入与覆盖式替换
