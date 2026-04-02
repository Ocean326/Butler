# 0402 Hermes Agent 专题：Chat 启发式资料

日期：2026-04-02
对象：`NousResearch/hermes-agent`

---

## 1. 一句话裁决

Hermes 对 Butler Chat 的最好启发是：

> 保持 Butler 当前 `session_scope_id -> chat_session_id` 主权不变，同时把“来源上下文、历史检索、显式恢复动作”做得更产品化。

---

## 2. 现在可吸收的启发

### 2.1 给 Chat 补一个显式历史检索入口

当前 Butler 侧裁决是：

- 默认只在当前 `session_scope_id` 内续接/重开

这条不应改。  
但可新增一个显式动作层：

- 搜索最近会话
- 选择历史主线
- 以用户确认方式恢复

这样能避免把“全局检索”偷偷混进默认续接逻辑。

### 2.2 把来源上下文进一步结构化

Hermes 的 `SessionSource/SessionContext` 提醒 Butler：

- 前门不是只有用户文本
- 还应有入口、线程、平台、回投能力等结构化上下文

这可帮助：

- prompt 更稳
- delivery/query 更稳
- 多入口心智更清晰

### 2.3 把“新话题/续旧线”做得更可见

0402 Butler 已有 router 编译裁决。  
下一步可考虑让用户在歧义场景下更容易理解：

- 为什么继续当前线
- 为什么重开新线
- 当前内部 `chat_session_id` 是否发生变化

---

## 3. 中期启发

### 3.1 Chat 历史标题化/摘要化

Hermes 的 session title 说明：

- 人类理解恢复对象时，不只靠 UUID

Butler 可考虑：

- 对 chat session 自动生成轻标题
- 在恢复/查询时显示最近摘要

### 3.2 跨入口命令一致性

如果 Butler 后续继续扩入口：

- 本地 CLI
- 对外 chat
- 其他 frontdoor

则模式切换、恢复、压缩、技能选择最好有较稳定的统一交互词汇。

### 3.3 session context block 的治理

Hermes 给出一个明确提醒：

- context block 一旦进入 prompt，就要视作正式合同

Butler 若继续扩 `session_selection`、`source context`、`delivery context`，应同步治理其块顺序、字段命名与门控。

---

## 4. 不应吸收的部分

### 4.1 不把历史搜索升级成默认自动跨 scope 续接

Hermes 有 FTS 搜索，不代表 Butler 要把默认续接改成全局检索。  
当前 0402 真源明确要求：

- 当前内部 chat session 优先
- 新话题时才在当前 scope 内重开

### 4.2 不让平台外壳反向定义 Butler chat 真源

Hermes 的 gateway 很强，但 Butler Chat 真源应继续由：

- router compile
- recent/summary
- prompt 层

来定义，而不是由某个平台适配器倒逼。

### 4.3 不把 session DB 当作唯一真源

即使未来引入更强的历史检索，Butler 仍要保留：

- 编译态
- 当前主线
- recent filter
- prompt contract

这套自身真源。

---

## 5. 建议的三步实验

### 实验 A：显式会话搜索命令

目标：

- 增加用户主动触发的历史检索，而不改变默认 router 逻辑

### 实验 B：session 选择解释块

目标：

- 在有需要时外显“继续/重开”的原因标志

### 实验 C：轻标题与最近摘要

目标：

- 让会话恢复不只靠 ID

---

## 6. 结论

Hermes 不是让 Butler Chat 改成“平台化大 gateway”，而是提醒我们：

- 当前主线连续性要继续保持 Butler 自持
- 显式恢复与历史检索可以单独产品化
- 来源上下文应被视作正式 prompt 合同的一部分
