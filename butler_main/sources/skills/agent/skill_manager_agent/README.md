# skill_manager_agent

这里存放 skills 体系的综合管理 agent 冷数据。

定位：

- 不直接承担 chat 主链人格
- 不直接承担 orchestrator 主控制面
- 作为 `sources/skills` 的统一管理入口，在 talk / orchestrator 明确需要时，由 `agents_os` 载入

典型职责：

- skill 池盘点与整理建议
- GitHub / 外部仓库 skill 导入与落库
- API / library / 官方 docs 候选转 incubating skill 草案
- incubating 候选转 active 可执行 skill
- collection 暴露建议
- skill registry / frontmatter / path 校验
- skill 资产治理报告

边界：

- 冷数据放这里
- 热状态不放这里
- 运行期决策和执行仍由 talk / orchestrator / agents_os runtime 承接

路径纪律：

- skill 管理过程态中间产物默认写入 `./butler_main/sources/skills/temp/`
- skill 正式运行结果按正式结果目录落盘；当前统一 runtime 结果默认写入 `./工作区/Butler/runtime/skills/`
- `skill_manager_agent` 在创建/维护 skills 时必须先判断产物性质，不能把中间产物和结果产物混放
