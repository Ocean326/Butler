技能：修改 template

适用场景：
- 用户已经指向一个 template
- 或者用户正在围绕 builtin 派生 template
- 或者你已经确定“问题应该先在 template 层修”

你要做的事：
- 说清楚哪些改动属于 template 层，哪些应留给具体 flow 层
- 检查该 template 的 `supervisor.md` 是否也需要同步修改
- 若目标是 builtin，必须把 `clone` / `edit` 两条路径的差别说清楚

你此时不要做的事：
- 不要一边改 template 一边顺手创建 flow，除非用户已经单独确认 flow 层

阶段建议：
- 提案时用 `template_prepare`
- 等待拍板时用 `template_confirm`

动作建议：
- `action=manage_flow` 只对应 template 本身的 mutation
- `action_ready=true` 只在 template 层已被明确确认后出现
