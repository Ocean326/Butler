技能：选择或创建 template

适用场景：
- 新需求应该先沉淀到可复用层
- 用户想做一类长期会重复的工作
- 当前还不该直接建 flow

你要做的事：
- 判断三条路径里哪条最对：
  - 直接复用现有 template
  - 轻改现有 template
  - 新建 template
- 解释为什么 template 层才是当前该先处理的层级
- 明确在创建 flow 之前，哪些 template 字段必须先补齐：
  - `goal`
  - `guard_condition`
  - `phase_plan`
  - `supervisor` 方向说明
  - `control_profile` 的工作包大小、证据强度、gate 节奏
- 只有确实需要 repo 级合同约束时，才显式绑定 `control_profile.repo_contract_paths`
- 用面向用户的话总结“我准备如何整理 template”

你此时不要做的事：
- 不要创建 flow
- 不要把 template 确认和 flow 确认混成一次

阶段建议：
- 先用 `template_prepare`
- 当 template 方案已经清晰且等待用户拍板时，切到 `template_confirm`

动作建议：
- 准备阶段保持 `action=none`
- 只有当用户明确确认 template 层 mutation 时，才设置：
  - `action=manage_flow`
  - `action_manage_target=template:new` 或 `template:<id>`
  - `action_ready=true`
