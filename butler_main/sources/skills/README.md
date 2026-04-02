# Butler Global Skills Source

这里是 Butler 未来的全局 skill 池与管理真源。

当前阶段：

1. `collections/registry.json` 是运行时暴露清单真源
2. `collections/prompt_policy.json` 是统一 skill 注入词 / shortlist 文案 / runtime 补充词真源
3. 实际 skill 内容仍可临时引用 legacy 目录 `./butler_main/butler_bot_agent/skills/`
4. 后续可逐步把 skill 正文迁入 `sources/skills/pool/`
5. 统一解析/注入入口在 `./butler_main/agents_os/skills/`
6. 统一 tool API 入口是 `butler_main.agents_os.skills.skill_tool`
7. `agent/skill_manager_agent/` 是 skills 体系的冷数据管理 agent 入口，供 talk / orchestrator 按需通过 `agents_os` 装载

原则：

1. skill 真源、运行时可见 collection、执行注入方式三者分离
2. chat / codex / orchestrator / 其他第四层入口不直接暴露全量 skill 池
3. DNA 核心能力不进入 skill 池
4. 相似 leaf skills 优先通过 `family_id/family_label/family_summary` 折叠到暴露层，不默认物理合并成大 skill
5. agent 侧注入词优先复用 skill 池侧 `prompt_policy`，避免每个 agent 各自维护一套 skill 口径
6. skill 管理过程态中间产物默认写到 `./butler_main/sources/skills/temp/`，不默认写 `工作区/`
7. skill 正式运行结果按正式结果目录写出；当前通用 runtime 结果默认写到 `./工作区/Butler/runtime/skills/`
8. manager 在创建/维护 skills 时必须先区分中间产物与结果产物，禁止混放
