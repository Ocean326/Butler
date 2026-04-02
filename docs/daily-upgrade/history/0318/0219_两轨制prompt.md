我给你的更实际建议：先走“两轨制”
轨 1：Raw turn log

把最近若干轮原文稳定保存下来，作为可检索真源。
用途：

找链接

找路径

找报错

找代码片段

找用户原话措辞

找 assistant 上轮具体承诺

轨 2：Light prompt view

默认 prompt 仍然保持轻量：

recent summaries

recent requirements

local memory hits

task board view

少量 quoted excerpts

这其实和你那份 Codex 计划是兼容的：
它已经明确建议先不要推翻现有 recent，而是把 recent 收回到“近期摘要层”，同时只在需要时通过统一入口引入原文摘录。

如果你现在想走最省工程量的路线，我会怎么改

我不会先上完整 state machine。
我会先做这个顺序：

第一步

保留最近 20–50 轮 raw turns，user 和 assistant 都存。
但不默认注入。

第二步

给 raw turns 抽一个很轻的 artifact index：

URLs

file paths

commands

error blocks

code snippets

explicit user constraints

这样“再打开那个链接”时，不用检索整段原文，只检索对象索引。

第三步

当前轮命中以下指代时，再检索 raw：

那个链接

上次报错

刚才那段代码

你上轮答应的事

按我刚才原话

第四步

heartbeat 继续走 ledger，不要退化成聊天历史驱动。

这条路比“先定义 20 个状态字段”简单得多，而且大概率马上就能见效。

一句最重要的判断

你担心“过度设计”，这个担心是对的。
在你现在这个阶段，最优解很可能不是“立刻全量状态化抽取”，而是：

默认 summary，保留 raw，按需检索，精确对象单独索引，planner 继续信任 ledger。

这比“纯 summary”强，也比“默认整段 raw 回放”稳，还比“先造完整状态操作系统”省工程量。

我会怎么选

如果我是你，我现在会选：

先做 Cursor 风格的“可引用历史 + 轻量常驻规则”，而不是一步到位做全状态化 prompt projection。
但我不会完全放弃 projection，只会把它缩成很薄的一层：

负责默认 prompt 保持干净

负责何时去查 raw history

负责把查回来的内容裁剪后再注入

也就是：

不是取消 projection，而是把 projection 从“大型语义重构工程”降级成“轻量检索门控层”。

这条路线，对 Butler 现在最像“又稳又快”。

下一条我可以直接给你写一个 最小可实现方案：
recent_raw_turns + artifact_index + on_demand_quote_retrieval + thin_projection_gate 的 Butler 版接口设计。