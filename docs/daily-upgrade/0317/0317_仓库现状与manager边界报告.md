# 0317 仓库现状与 manager 边界报告

> 更新时间：2026-03-17

## 1. 目的

本文不是新方案，而是对 0317 时点 Butler 仓库的真实状态做一次收束性说明，重点回答三个问题：

1. 现在仓库里到底有哪些 “manager / orchestrator”
2. 哪些边界已经收束，哪些仍然混乱
3. 下一步该继续拆哪里，避免再次把职责堆回单个大文件

补充：

- 若要看 0317 当天 heartbeat 停跳与任务池污染的单独问题，请同时参考 `0317_心跳与任务循环现状问题报告.md`

---

## 2. 当前仓库的几个核心入口

按运行层级看，当前最重要的几个文件是：

1. `butler_main/butler_bot_code/manager.ps1`
2. `butler_main/butler_bot_code/butler_bot/butler_bot.py`
3. `butler_main/butler_bot_code/butler_bot/agent.py`
4. `butler_main/butler_bot_code/butler_bot/memory_manager.py`
5. `butler_main/butler_bot_code/butler_bot/heartbeat_orchestration.py`
6. `butler_main/butler_bot_code/butler_bot/memory_pipeline/orchestrator.py`

当前大致体量：

| 文件 | 角色 | 规模感 |
| --- | --- | --- |
| `manager.ps1` | 进程管理脚本 | 466 行 |
| `butler_bot.py` | 飞书主进程入口 | 632 行 |
| `agent.py` | talk prompt / 角色注入 / 能力注入 | 1325 行 |
| `heartbeat_orchestration.py` | heartbeat 规划与执行编排 | 1141 行 |
| `memory_manager.py` | 记忆、心跳、后台维护、状态管理总入口 | 6450 行 |
| `memory_pipeline/orchestrator.py` | memory agent 调度层 | 小而专用 |

---

## 3. 现在有哪些 “manager / orchestrator”

这是当前最容易混乱的点。

### 3.1 `manager.ps1`

它是 **进程生命周期 manager**，职责是：

1. 启动 / 停止 / 重启主进程
2. 检查主进程和 heartbeat sidecar 是否存活
3. 处理 PID、状态文件、日志、registry

它不是业务编排器，也不是记忆治理器。

### 3.2 `memory_manager.py`

它是 **运行期总编排入口**，但仍然偏重。

当前它同时掌握：

1. recent/local/profile 记忆入口
2. heartbeat 启动与单轮执行入口
3. 后台维护触发
4. 部分审批 / 发送 / 状态文件 / 自我系统接线
5. 多个 service 的装配与委托

所以它现在更像：

- “运行中的超大总控类”

而不是理想状态的轻量 memory façade。

### 3.3 `HeartbeatOrchestrator`

它是 **heartbeat 规划执行编排器**。

它的职责是：

1. heartbeat prompt 规划
2. branch 归一化
3. 任务组执行
4. branch result 汇总
5. heartbeat recent snapshot 落地

它已经比过去更聚焦，但文件仍然偏大，说明 heartbeat manager/planner/executor 边界还没完全拉开。

### 3.4 `MemoryPipelineOrchestrator`

它是 **memory agent 调度器**，这轮新引入。

当前职责比较清晰：

1. 组装 agent 输入
2. 调 `post_turn_memory_agent`
3. 调 `compact_memory_agent`
4. 调 `maintenance_memory_agent`
5. 把 agent 结果交给 local/profile writer adapter 应用

它不负责：

1. 记忆分类规则本身
2. dedupe / conflict / compact 细则
3. maintenance 判断细节

这些都仍在各自 agent 内。

---

## 4. 0317 已经收束好的边界

### 4.1 memory agent 架构已从隐式逻辑变成显式模块

现在 `memory_pipeline/` 下已经有：

1. `agents/post_turn_memory_agent.py`
2. `agents/compact_memory_agent.py`
3. `agents/maintenance_memory_agent.py`
4. `adapters/recent_adapter.py`
5. `adapters/local_writer_adapter.py`
6. `adapters/profile_writer.py`
7. `models.py`
8. `policies.py`
9. `feature_flags.py`
10. `prompts/*.md`

这意味着：

1. memory agent 角色没有再被藏进 service
2. profile writer 已从普通 local write 里分离
3. compact 默认不具备写 `user_profile` 的权限

### 4.2 `memory_manager.py` 没有被重写

这轮重构的策略是：

1. 保留 `_upsert_local_memory()`
2. 保留 local index / relations / write journal
3. 用 orchestrator 包装旧底座
4. 通过 feature flag 控制接管范围

这保证了模块可回滚，也避免一次性打断旧链路。

### 4.3 user profile 已形成独立写入口

现在 `user_profile` 不再与普通 local memory 混成同一种 writer。

当前链路是：

1. 主 agent 可通过窄权限入口直写
2. `post_turn_memory_agent` 可通过独立 `profile_writer.py` 治理写
3. `compact_memory_agent` 默认不能写
4. `maintenance_memory_agent` 默认也不直接写

---

## 5. 0317 仍然混乱或过重的地方

### 5.1 `memory_manager.py` 仍然是事实上的“黑洞”

虽然已经开始服务化和 pipeline 化，但它仍然知道太多事情：

1. memory
2. heartbeat
3. self_mind
4. runtime/background services
5. 部分 message delivery / governance / approval 细节

问题不在于“它调用了很多模块”，而在于：

- 它仍然持有太多跨域私有方法和运行事实

这会导致任何新需求都很容易继续加回这里。

### 5.2 “manager” 命名语义仍然混用

当前仓库里至少有四种 manager/orchestrator 含义：

1. 进程 manager：`manager.ps1`
2. 运行总控 manager：`memory_manager.py`
3. heartbeat orchestrator：`heartbeat_orchestration.py`
4. memory orchestrator：`memory_pipeline/orchestrator.py`

如果不明确区分，后续很容易出现两类坏味道：

1. 什么都叫 manager，结果没人知道真边界
2. 为了方便，继续把新能力塞进现有“大 manager”

### 5.3 `HeartbeatOrchestrator` 还没有完成第二轮收束

它虽然独立于 `memory_manager.py`，但自身仍然承载了较多：

1. 规划细节
2. 执行编排
3. 结果汇总
4. recent snapshot 写回

这说明 heartbeat 侧还处在：

- “已从 memory_manager 抽出，但尚未再细分”

### 5.4 文档与代码的时间切片并存

仓库里 0315、0316、0317 有多份现状文档。

这本身不是问题，但如果没有新的总览文档，很容易出现：

1. 旧文档里说 `memory_manager.py` 仍直接做 recent->local 治理
2. 新代码里其实已经切到 `memory_pipeline/`

所以 0317 之后，文档必须把“旧底座仍在 + 新治理模块已接线”的过渡态说清楚。

---

## 6. 对当前架构的一个更准确表述

0317 时点的 Butler，不应再被描述为：

- “飞书入口 + 巨大的 memory_manager + heartbeat”

而应描述为：

1. `manager.ps1`
   - 负责进程生命周期
2. `butler_bot.py` + `agent.py`
   - 负责对话入口、prompt 组装、调用运行时
3. `memory_manager.py`
   - 负责运行期总接线、旧 memory primitives、heartbeat 与后台服务桥接
4. `memory_pipeline/`
   - 负责 memory governance agent 编排
5. `heartbeat_orchestration.py`
   - 负责 heartbeat 规划与执行编排

也就是说，当前真正的状态是：

- **单体正在被分层，但还没有完全完成第二轮纵向收束。**

---

## 7. 下一步应继续拆什么

按风险和收益排序，建议顺序如下。

### 7.1 第一优先级：继续压缩 `memory_manager.py`

不是重写，而是继续让它失去具体实现细节。

优先外提的不是零散 helper，而是整块重职责：

1. heartbeat 运行态与 watchdog 审计
2. self_mind bridge / cognition / context refresh
3. approval / restart / runtime audit

目标不是“拆文件数”，而是让 `memory_manager.py` 从 运行黑洞 收缩成：

- 生命周期协调
- 模块装配
- 跨层桥接

### 7.2 第二优先级：把 `HeartbeatOrchestrator` 再分层

建议后续至少拆成概念上更清楚的三段：

1. planner façade
2. execution coordinator
3. snapshot / persistence bridge

否则 heartbeat 只是在另一个文件里重复“大 orchestrator”。

### 7.3 第三优先级：统一 manager/orchestrator 命名

建议以后在文档里固定这几个词：

1. process manager
2. runtime coordinator
3. heartbeat orchestrator
4. memory pipeline orchestrator

至少在文档层要先统一，不然工程语义会越来越乱。

---

## 8. 结论

0317 的关键进展不是“又多了几个 service”，而是：

1. recent -> long-term memory 治理终于被显式建模成 agent 体系
2. `user_profile` 写入边界被单独拉出
3. `compact` / `maintenance` 权限边界第一次变得清楚
4. `memory_manager.py` 虽然仍大，但没有继续吞并 memory agent 职责

0317 的关键问题也同样明确：

1. `memory_manager.py` 仍然太大
2. heartbeat orchestrator 仍然偏重
3. “manager” 一词在仓库里仍然多义

所以这一天结束时，Butler 的真实状态是：

- **memory pipeline 已经开始模块化成功**
- **但整个仓库仍处在“大总控逐步收束”的中间阶段**
