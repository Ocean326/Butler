# User Bootstrap

读取用户长期偏好时，优先来源：
1. `./butler_main/butler_bot_agent/agents/local_memory/Current_User_Profile.private.md`
2. 若不存在，回退到模板。

默认策略：
1. 用用户偏好的语气与密度回答。
2. 与当前用户明确表达冲突时，以当前明确表达为准。
