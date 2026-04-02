# Memory Policy Bootstrap

记忆装载策略：
1. talk：默认只读相关长期偏好和最小 recent，不把整段 recent 规则直接拼进用户消息。
2. self_mind：只读 self_mind 上下文、陪伴记忆、listener history、续思痕迹。

噪音控制：
1. 旧流程播报样式不作为行为真源。
2. 临时排障记录不直接进入主 prompt。
3. 已退役机制如 `guardian`、`restart_guardian_agent`、旧后台 sidecar、旧 chat 自定义 `sub-agent/team execution` 等，只作历史参考，不作为当前 prompt 认知真源。
