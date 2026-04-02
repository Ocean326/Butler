# 0316 Bootstrap 升级方案和计划

## 1. 目标

本方案的目标不是继续修某一条 prompt，而是彻底解决 Butler 当前长期存在的这类问题：

1. prompt 组成混杂，稳定规则、动态上下文、能力目录、历史补丁写法混在一起。
2. talk / heartbeat / self_mind 彼此边界不清，常常互相污染。
3. 功能问题经常不是能力本身坏了，而是 prompt 装载错误，把模型带偏。
4. 每修一次问题就多加一条规则，最后形成“哪里漏了补哪里”的规则怪谈。

这次升级要把 prompt 从“运行时拼装文本堆”升级为“bootstrap 真源 + 最小动态上下文”的体系。

---

## 2. 当前问题判断

### 2.1 不是单条 prompt 写得差，而是 prompt 架构有问题

现在 Butler 的 prompt 主要问题不是“少写了一句约束”，而是以下四类内容长期混在一起：

1. 人格和价值观
   - 例如 SOUL、人设、表达基调。
2. 会话协议
   - 例如 talk 怎么回、heartbeat 怎么规划、self_mind 怎么说话。
3. 动态上下文
   - recent、任务板、短期状态、当前输入。
4. 能力目录
   - skills、sub-agents、teams、公用库、运行时路由。

这些内容一旦没有分层，模型就会出现典型退化：

1. 把能力目录当成“现在已经执行过的事实”。
2. 把最近的错误处理方式学成默认行为。
3. 把 role / protocol / recent 叠成一锅，开始播报自己的处理流程。
4. 把本来应该只在 heartbeat 里使用的调度意识带到主 talk。
5. 把 self_mind 的认知语言带进主对话，或者反过来把主执行语言带进 self_mind。

### 2.2 当前已出现的功能问题，本质都和 prompt 混杂有关

已暴露过的典型问题：

1. 主 talk 遇到链接、素材、转发时，不直接理解和处理，而是先“我先去读一圈 / 我先接链路 / 你去跑 PowerShell”。
2. heartbeat 因为模板与代码双重注入，prompt 越来越厚，调度和执行边界越来越模糊。
3. self_mind 明明要做陪伴型独立机器人，却会被任务、心跳、talk recent 污染成第二个调度器。
4. 每次修一个风格问题，最后都落成代码里再加一句“不要 xxx”，而不是回到单一真源。

这些不是孤立 bug，而是同一个架构问题的不同表面。

---

## 3. 升级原则

这次 bootstrap 升级必须坚持 6 条原则。

### 3.1 稳定层和动态层彻底分开

稳定层只定义：

1. 身份
2. 边界
3. 协议
4. 价值观

动态层只承载：

1. 当前输入
2. 少量相关上下文
3. 当前轮真正可用的能力

### 3.2 会话类型决定装载，不再默认全开

不同会话只加载自己需要的 bootstrap：

1. talk
2. heartbeat planner
3. heartbeat executor
4. self_mind cycle
5. self_mind chat
6. sub-agent / team

### 3.3 模板文件是真源，代码只供数

代码负责：

1. 提供上下文数据
2. 裁剪可见块
3. 注入用户输入

代码不负责：

1. 在运行时不断补新的行为规则
2. 临时往 prompt 末尾再贴一段“如果用户 xxx 就不要 yyy”

### 3.4 能力目录不是默认背景

skills、sub-agent、team、公用能力库只在满足条件时注入：

1. 用户明确提到
2. 当前任务显式需要
3. 当前 runtime 真的允许执行

否则不进 prompt。

### 3.5 记忆进入 prompt 必须受 policy 控制

不是所有 memory 都可以直接进主 prompt。

必须建立明确 policy：

1. talk 默认读什么
2. heartbeat 默认读什么
3. self_mind 明确不能读什么
4. 什么属于长期偏好
5. 什么只是近期噪音

### 3.6 风格问题不能靠继续加禁令

“不要播报流程”“不要甩命令”“不要先说我去看”这类约束可以保留，但必须归并进会话协议真源，而不是继续散落在：

1. 代码字符串
2. role 文件
3. local memory
4. 修 bug 时临时补丁

---

## 4. Bootstrap 真源架构设计

建议新建目录：

- `butler_main/butler_bot_agent/bootstrap/`

在该目录下建立一套统一真源。

## 4.1 文件清单

### A. `SOUL.md`

职责：

1. 定义 Butler 的稳定人格
2. 定义价值观与红线
3. 定义长期表达底色

禁止写入：

1. 具体任务协议
2. 技能目录
3. 最近发生了什么
4. 临时 workaround

### B. `TALK.md`

职责：

1. 定义主 talk 的行为协议
2. 定义主 talk 的默认回答顺序
3. 定义什么时候允许提工具 / 命令 / 协作链

必须覆盖的问题：

1. 用户只丢链接时如何处理
2. 用户给素材时先理解还是先播报
3. 什么时候可以要求用户配合
4. 什么时候允许提 skills / sub-agent

### C. `HEARTBEAT.md`

职责：

1. 定义 heartbeat planner 的角色和边界
2. 定义调度原则、汇报原则、任务治理原则
3. 定义 planner 与 executor 的关系

必须明确：

1. planner 是 manager，不是执行器
2. `user_message` 和 `tell_user_candidate` 的分工
3. 不允许把主 talk 风格直接塞进 heartbeat

### D. `EXECUTOR.md`

职责：

1. 定义 heartbeat executor / branch executor 的通用执行契约
2. 定义结果、证据、风险、下一步的输出结构
3. 定义 executor 的边界：诊断、换路、复试、回执

这样 executor 协议不再散落在 role 文档和 heartbeat 代码里。

### E. `SELF_MIND.md`

职责：

1. 定义 self_mind 的身份
2. 定义 self_mind 的陪伴定位
3. 定义 self_mind 与主 talk / heartbeat 的边界

必须明确：

1. 不读主 talk recent
2. 不读 heartbeat recent
3. 不指挥 talk-heartbeat
4. 可以陪伴、解释、表达、续思

### F. `USER.md`

职责：

1. 作为用户长期偏好的 bootstrap 入口
2. 统一 talk / self_mind 对用户偏好的读取方式

来源可由当前：

- `Current_User_Profile.private.md`

映射生成或引用。

### G. `TOOLS.md`

职责：

1. 定义能力边界
2. 定义可见能力目录的装载规则
3. 定义“只有真的执行过才允许说已经用了”

它不应该是全量技能说明书，而应是能力协议和引用入口。

### H. `MEMORY_POLICY.md`

职责：

1. 明确不同会话允许读哪些记忆
2. 明确 recent / local memory / cognition / listener history 的装载规则
3. 明确哪些 memory 是噪音，不可直入 prompt

这是 Butler 当前最缺的一层。

---

## 5. 不同会话的 bootstrap 装载方案

## 5.1 Talk

### 默认装载

1. `SOUL.md`
2. `TALK.md`
3. `USER.md`
4. `TOOLS.md`
5. `MEMORY_POLICY.md` 的 talk 摘要

### 按需装载

1. 相关长期记忆命中
2. 少量 recent
3. skills 目录
4. agent capabilities

### 默认不装载

1. `HEARTBEAT.md`
2. `SELF_MIND.md`
3. heartbeat recent
4. self_mind cognition 全文

## 5.2 Heartbeat Planner

### 默认装载

1. `HEARTBEAT.md`
2. `TOOLS.md` 的 heartbeat 摘要
3. `MEMORY_POLICY.md` 的 heartbeat 摘要

### 动态注入

1. 任务看板
2. unified heartbeat recent
3. 长期记忆命中
4. 任务工作区
5. 可复用能力目录

### 默认不装载

1. 主 talk 协议
2. self_mind 陪伴协议
3. 主 talk 风格修辞规则

## 5.3 Heartbeat Executor

### 默认装载

1. `EXECUTOR.md`
2. 对应 branch role 摘录
3. workspace hint

### 动态注入

1. 当前 branch prompt
2. 当前 branch runtime profile
3. 当前 branch skill block（仅在显式要求时）

### 默认不装载

1. 整个 planner 逻辑
2. talk 风格约束
3. self_mind 协议

## 5.4 Self-Mind

### self_mind cycle

默认装载：

1. `SOUL.md` 的 self_mind 可继承部分
2. `SELF_MIND.md`
3. `USER.md`
4. `MEMORY_POLICY.md` 的 self_mind 摘要

动态注入：

1. self_mind current_context
2. companion memory
3. raw thoughts

### self_mind chat

默认装载：

1. `SOUL.md`
2. `SELF_MIND.md`
3. `USER.md`

动态注入：

1. self_mind listener history
2. cognition excerpt
3. self_mind 当前上下文
4. 用户给 self_mind 的当前输入

默认不装载：

1. 主 talk recent
2. heartbeat recent
3. planner / executor 能力目录

---

## 6. 代码架构调整方案

## 6.1 新增 Bootstrap Loader

建议新增服务：

- `butler_main/butler_bot_code/butler_bot/services/bootstrap_loader_service.py`

职责：

1. 按 session type 读取 bootstrap 文件
2. 做字符上限和裁剪
3. 输出结构化 bootstrap payload

接口建议：

1. `load(session_type="talk")`
2. `load(session_type="heartbeat_planner")`
3. `load(session_type="heartbeat_executor")`
4. `load(session_type="self_mind_cycle")`
5. `load(session_type="self_mind_chat")`

## 6.2 新增 Prompt Compose Service

建议新增：

- `butler_main/butler_bot_code/butler_bot/services/prompt_compose_service.py`

职责：

1. 接收 bootstrap payload
2. 接收动态上下文
3. 用统一结构组装 prompt

统一形态应为：

1. bootstrap 层
2. dynamic context 层
3. user input / branch task 层

而不是在业务代码里不断 `blocks.append()`。

## 6.3 将现有字符串 prompt 拆出代码

需要迁移的现役代码真源包括：

1. `agent.py` 中的主 talk 固定文案
2. `self_mind_prompt_service.py` 中的固定协议文案
3. `memory_manager.py` 中的 `DEFAULT_HEARTBEAT_PROMPT_TEMPLATE`
4. `heartbeat_orchestration.py` 中与 planner/executor 高耦合的固定说明块

代码中只保留：

1. 数据
2. 条件选择
3. 少量 fallback

## 6.4 将 recent 注入从“文本拼接”升级为“结构化 context”

当前最大噪音源之一是：

1. `prepare_user_prompt_with_recent()` 直接在 `user_prompt` 字符串里拼一大段解释性文本。

升级后应改为：

1. recent 作为单独 context block
2. 由 compose service 决定是否注入
3. 禁止把 recent 解释规则和用户消息混写在一起

这一步对 talk 的效果影响最大。

---

## 7. 分阶段升级计划

## Phase 0：冻结旧 prompt 补丁入口

目标：

1. 停止继续往 `agent.py` / `memory_manager.py` 里加新的风格禁令
2. 以后所有 prompt 行为修正都优先落 bootstrap 真源

动作：

1. 约定 `agent.py` 中新增规则需标注“待迁移到 bootstrap”
2. 对现有散落规则做盘点表

## Phase 1：建立 bootstrap 目录与真源文件

目标：

1. 创建 `bootstrap/`
2. 写出 7-8 个真源文件初版

产物：

1. `SOUL.md`
2. `TALK.md`
3. `HEARTBEAT.md`
4. `EXECUTOR.md`
5. `SELF_MIND.md`
6. `USER.md`
7. `TOOLS.md`
8. `MEMORY_POLICY.md`

验收：

1. 每个文件职责单一
2. 没有明显跨层内容
3. 行为规则从现有代码与 role 中迁出后仍可对应回来

## Phase 2：先切主 Talk

目标：

1. 让主 talk 最先吃 bootstrap 真源
2. 停止当前主链路的补丁式 prompt 拼接

动作：

1. 引入 bootstrap loader
2. 引入 talk compose service
3. `build_feishu_agent_prompt()` 改为基于 bootstrap 组装
4. recent 改为结构化 context block

重点解决：

1. 链接/素材分享时的流程播报问题
2. 技能目录幻觉问题
3. “告诉用户自己去跑命令”的默认退化

## Phase 3：切 Self-Mind

目标：

1. self_mind 完全摆脱 talk / heartbeat 的 prompt 污染

动作：

1. `self_mind_prompt_service.py` 改为读取 `SELF_MIND.md`
2. cycle / chat 分别配置自己的 dynamic context schema
3. 统一 listener history / cognition / companion memory 的装载规则

重点解决：

1. self_mind 变成任务调度器的问题
2. self_mind 不能稳定陪伴的问题

## Phase 4：切 Heartbeat Planner / Executor

目标：

1. planner 与 executor 都改成 bootstrap 驱动
2. planner 模板不再由代码自动补充行为块

动作：

1. planner 读取 `HEARTBEAT.md`
2. executor 读取 `EXECUTOR.md`
3. branch role 摘录只作为附加层，而不是协议真源

重点解决：

1. planner prompt 越来越厚的问题
2. executor 角色与调度协议混杂的问题

## Phase 5：清理旧 prompt 真源

目标：

1. 清退旧散落规则
2. 确保单一真源成立

动作：

1. 清理 `agent.py` 中已迁出的硬编码说明
2. 清理 role 文件中不该承担的 prompt 协议
3. 对 local memory 中“假真源”性质的规则做迁移或归档

---

## 8. 风险与控制

## 8.1 最大风险

最大的风险不是“迁不动”，而是：

1. 迁了一半，新旧体系并存
2. bootstrap 和旧 role / prompt 互相打架
3. 文档写了新真源，代码还在偷偷拼老块

## 8.2 控制措施

1. 每切一条链，都要明确：
   - 现役真源是谁
   - 旧入口是否停用
2. 给每条链做 prompt 组成快照测试
3. 给每条链写一份“装载矩阵”
   - 哪些文件会被加载
   - 哪些动态块会被加载
   - 哪些绝不应被加载

## 8.3 回归测试建议

必须覆盖这些场景：

1. 主 talk 收到普通任务
2. 主 talk 收到链接/素材分享
3. 主 talk 收到短追问
4. self_mind 独立聊天
5. self_mind 解释机制问题
6. heartbeat planner 空任务
7. heartbeat planner 多任务并行
8. heartbeat executor 执行维护类 branch

---

## 9. 本次升级后的预期结果

如果 bootstrap 升级做完，Butler 应该达到这些状态：

1. 主 talk 不再因为 recent 和能力目录污染，动不动播报流程。
2. heartbeat 的规划与执行 prompt 变薄，角色边界清楚。
3. self_mind 回到独立陪伴型人格，而不是第二个 planner。
4. prompt 调整变成“改真源文件 + 跑测试”，而不是继续改散落代码字符串。
5. 新问题出现时，可以明确回答：
   - 是 bootstrap 真源的问题
   - 是动态上下文 policy 的问题
   - 还是能力层装载条件的问题

也就是说，后续问题会从“玄学 prompt 漂移”变成“可定位的 prompt 架构问题”。

---

## 10. 建议的立即执行顺序

按收益和风险比，建议立即这样推进：

1. 先建立 `bootstrap/` 真源目录和 8 个文件初版。
2. 第一批只切 `talk`。
3. talk 稳定后，再切 `self_mind`。
4. 最后切 `heartbeat planner / executor`。
5. 等三条链全部跑通后，再统一清理旧 prompt 入口。

当前不建议一口气重构三条链，否则定位问题会重新失控。

---

## 11. 本文结论

Butler 当前的 prompt 功能问题，本质不是单轮回答风格跑偏，而是 prompt 架构长期混杂。

因此解决方案不能再是：

1. 再补一句不要 xxx
2. 再加一个 mode
3. 再往 role 文件塞一段说明

真正的解法是：

1. 建立 bootstrap 真源
2. 分离稳定层、动态层、能力层
3. 让不同会话只加载自己该加载的内容
4. 让模板文件成为行为真源，代码只负责供数和裁剪

这不是一次“优化 prompt”，而是一次 Butler prompt 操作系统的重构。
