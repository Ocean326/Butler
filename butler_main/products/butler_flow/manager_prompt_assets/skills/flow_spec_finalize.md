技能：定稿本次 flow 规格

适用场景：
- template 路径已经定了
- 用户现在要落到“本次 run 的具体 flow”

你要做的事：
- 重述这次 flow 依托的是哪个 template
- 细化本次 run 特有的：
  - `goal`
  - `guard_condition`
  - 本次特化的 supervisor 强调点
  - 本次需要的 `control_profile` 调整，例如缩小工作包、提高证据标准、强制 gate
- 明确说清楚：
  - 哪些内容继承自 template
  - 哪些内容只属于这次 flow
- 用一句清晰的话总结“接下来要创建的 flow 是什么”

你此时不要做的事：
- 在用户没明确确认 flow 摘要前，不要创建 flow

阶段建议：
- 细化时用 `flow_prepare`
- 等待用户拍板时用 `flow_confirm`

动作建议：
- 默认 `action=none`
- 只有当用户明确确认本次 flow 规格后，才能进入真正的 flow mutation
