# post_turn_memory_agent

职责：
- 接收主 agent 产出的 candidate_memory
- 结合 recent / local / profile 做 recent -> long-term 治理
- 执行 classify / add / update / merge / delete / ignore / dedupe / conflict handling

权限边界：
- 可以写 local memory
- 可以通过独立 profile writer 写 user_profile
- 不直接改 recent 原始对话记录
