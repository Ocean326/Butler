# 0324 `butler_bot_agent/agents/` 引用彻查

## 结论

当前仓库里对 `butler_bot_agent/agents/` 的引用不是单一原因造成的，而是三层叠加：

1. 运行时真依赖仍然在这里
2. chat 新前台已经迁出了一部分 role/bootstrap，但仍继续读取 `agents/` 下的记忆、子 agent、team、public library
3. 大量 docs / local_memory / 历史兼容文件仍把 `agents/` 视为“脑子侧真源”

所以现在不能把 `butler_bot_agent/agents/` 简单当成“纯历史目录”直接删掉。

---

## 一、运行时硬依赖

这些引用会直接影响 chat / heartbeat / memory / subagent 运行。

### 1. 路径常量层

- `butler_main/chat/pathing.py`
  - `AGENT_HOME_REL = butler_main/butler_bot_agent/agents`
  - chat 侧所有 recent/local_memory/sub-agents/teams/public-library 路径都从这里展开
- `butler_main/butler_bot_code/butler_bot/butler_paths.py`
  - body/legacy 侧仍维护同一套路径常量

### 2. chat 前台仍直接读 `agents/` 下数据

- `butler_main/chat/memory_runtime/recent_turn_store.py`
  - chat pending turn 与 recent_turn 仍写到 `agents/recent_memory/recent_memory.json`
- `butler_main/chat/providers/butler_prompt_support_provider.py`
  - 本地长期记忆命中仍从 `agents/local_memory/` 检索
- `butler_main/chat/prompt_support/agent_capabilities.py`
  - sub-agent catalog 仍扫描 `agents/sub-agents/`
  - team catalog 仍扫描 `agents/teams/`
  - public capability 仍扫描 `agents/public-library/agent_public_library.json`
- `butler_main/chat/providers/butler_runtime_executor.py`
  - 内部协作请求执行时，sub-agent 角色文件仍从 `agents/sub-agents/*.md` 读取
  - team 定义仍从 `agents/teams/*.json` 读取
  - workspace hint 仍从 `agents/heartbeat-executor-workspace-hint.md` 读取
- `butler_main/chat/prompting.py`
  - Soul 仍取 `agents/local_memory/Butler_SOUL.md`
  - User profile 仍取 `agents/local_memory/Current_User_Profile.private.md`
  - maintenance 入口仍引用 `agents/sub-agents/update-agent.md`
  - `decide` 示例里仍包含 `./butler_bot_agent/agents/local_memory/xxx.md`

### 3. body / legacy 主链路仍直接依赖 `agents/`

- `butler_main/butler_bot_code/butler_bot/memory_manager.py`
  - talk/beat recent、local memory、profile、Soul、heartbeat task board 都还在 `agents/` 下
- `butler_main/butler_bot_code/butler_bot/heartbeat_orchestration.py`
  - heartbeat 任务相关读写仍围绕 `agents/local_memory`、`agents/state`
- `butler_main/butler_bot_code/butler_bot/services/memory_backend.py`
  - memory backend 暴露 recent/local 路径仍是 `agents/`
- `butler_main/butler_bot_code/butler_bot/memory_pipeline/adapters/profile_writer.py`
  - profile 写回仍写 `agents/local_memory/Current_User_Profile.private.md`
- `butler_main/butler_bot_code/butler_bot/execution/agent_team_executor.py`
  - legacy 执行器仍从 `agents/sub-agents/` 解析角色
- `butler_main/butler_bot_code/butler_bot/registry/agent_capability_registry.py`
  - legacy registry 仍扫描 `agents/sub-agents/`、`agents/teams/`
- `butler_main/butler_bot_code/butler_bot/governor.py`
  - governor 对 `AGENT_HOME_REL` 有专门治理判断

### 4. 兼容 fallback 仍然存在

- `butler_main/butler_bot_code/butler_bot/services/bootstrap_loader_service.py`
  - chat/talk bootstrap 现在优先读 `butler_main/chat/assets/bootstrap/*.md`
  - 但仍保留 fallback 到 `butler_main/butler_bot_agent/bootstrap/*.md`

这意味着：`butler_bot_agent/bootstrap/` 虽然已不是首选真源，但也还没彻底退场。

---

## 二、已迁出但仍回指 `agents/`

这类文件“壳已经迁走，但内容仍把 `agents/` 当知识真源”。

### 1. chat 角色文件

- `butler_main/chat/assets/roles/chat-feishu-bot-agent.md`
  - 已经是 chat 当前 role 真源
  - 但内部仍显式指向：
    - `agents/local_memory/Butler_SOUL.md`
    - `agents/local_memory/Current_User_Profile.private.md`
    - `agents/sub-agents/`
    - `agents/docs/`
    - `agents/sub-agents/update-agent.md`

### 2. chat bootstrap 文件

- `butler_main/chat/assets/bootstrap/USER.md`
  - 仍显式指向 `agents/local_memory/Current_User_Profile.private.md`

这类文件说明：前台产品壳迁到 `chat/assets/` 了，但“知识与运行事实层”没有一起迁走。

---

## 三、重复副本 / 双真源风险

### 1. role 重复

两个文件内容基本同构：

- `butler_main/chat/assets/roles/chat-feishu-bot-agent.md`
- `butler_main/butler_bot_agent/agents/chat-feishu-bot-agent.md`

从 `docs/daily-upgrade/0322/02_Talk+AgentOS主链接线收口.md` 的表述看，chat 应优先使用前者。

因此这里已经形成“新真源 + 旧镜像/旧副本”并存状态。

### 2. bootstrap 重复

两个目录都存在 bootstrap：

- `butler_main/chat/assets/bootstrap/`
- `butler_main/butler_bot_agent/bootstrap/`

而 body 侧 loader 又保留 fallback，所以目前是：

- chat 新链路优先读前者
- 兼容层仍可能回退到后者

这是典型的“未完全迁移完成”的状态。

---

## 四、文档/知识层大面积把 `agents/` 当真源

这类不一定影响代码运行，但会强烈影响维护者判断。

### 1. agents/docs 自身

以下文件都把 `./butler_bot_agent/agents` 作为默认记忆根或默认工作流根：

- `butler_main/butler_bot_agent/agents/docs/MEMORY_MECHANISM.md`
- `butler_main/butler_bot_agent/agents/docs/MEMORY_READ_PROMPTS.md`
- `butler_main/butler_bot_agent/agents/docs/AGENTS_ARCHITECTURE.md`
- `butler_main/butler_bot_agent/agents/docs/AGENT_ROLE_DOC_LIMITS.md`
- `butler_main/butler_bot_agent/agents/docs/心跳机制与外部任务组织说明.md`

### 2. local_memory 自我描述

以下长期记忆文件也在把 `agents/` 认作运行时根：

- `butler_main/butler_bot_agent/agents/local_memory/人格与自我认知.md`
- `butler_main/butler_bot_agent/agents/local_memory/heartbeat_tasks.md`
- `butler_main/butler_bot_agent/agents/local_memory/提示词与人格变更防护机制.md`

### 3. skill / reference

- `butler_main/butler_bot_agent/skills/daily-inspection/SKILL.md`
- `butler_main/butler_bot_agent/skills/daily-inspection/reference.md`
- `butler_main/butler_bot_agent/skills/feishu-doc-sync/SKILL.md`

这些 skill 也会回指 `agents/docs` 或 `agents/local_memory`

### 4. daily-upgrade 文档

至少在以下升级文档里，已经明确承认“chat 外壳迁走了，但脑子/记忆/skills/工作流事实仍在 `butler_bot_agent`”：

- `docs/daily-upgrade/0322/02_Talk+AgentOS主链接线收口.md`

---

## 五、为什么现在还会保留这些引用

根因不是单点遗漏，而是架构上做了“前台迁移，脑子未迁”：

1. `chat` 迁走的是接口层、prompt 外壳、bootstrap 外壳
2. `butler_bot_agent/agents/` 仍承载：
   - recent memory
   - local memory
   - sub-agent role definitions
   - team definitions
   - public capability registry
   - heartbeat task/state 相关文档口径
   - 大量知识型 docs
3. `butler_bot_code` 旧链路没有完全退役，仍直接消费这套目录

换句话说：

- `chat/assets/*` 已经是“前台产品层真源”
- `butler_bot_agent/agents/*` 仍然是“知识/记忆/协作能力/状态口径层真源”

因此今天看到大量 `agents/` 引用，不是纯脏链路，而是“迁了一半”的真实状态。

---

## 六、对决策最关键的分界

### 可以相对安全舍弃或镜像化的部分

- `butler_main/butler_bot_agent/agents/chat-feishu-bot-agent.md`
  - 若确认 `chat/assets/roles/chat-feishu-bot-agent.md` 为唯一真源，可降为镜像或删除
- `butler_main/butler_bot_agent/bootstrap/*.md`
  - 但前提是先移除 body 侧 fallback
- 历史说明类 md / daily-upgrade 中的路径描述

### 不能直接舍弃的部分

- `agents/recent_memory/`
- `agents/local_memory/`
- `agents/sub-agents/`
- `agents/teams/`
- `agents/public-library/`
- `agents/state/`
- `agents/docs/` 中仍被 role/skill/流程引用的机制文档

这些现在仍是运行时或运行时近邻真源。

---

## 七、可选决策路径

### 方案 A：舍弃旧壳，保留 `agents/` 作为知识与运行事实层

含义：

- 删除/冻结 `agents/` 下重复 role 与旧 bootstrap
- 保留 `agents/recent_memory`、`local_memory`、`sub-agents`、`teams`、`state`、`docs`
- chat 继续引用这些目录作为知识与能力层

优点：

- 改动面小
- 最符合当前实际状态

缺点：

- `butler_bot_agent/agents/` 仍继续作为大根目录存在
- 语义上还是会让人误以为“chat 没迁干净”

### 方案 B：完全迁移到 `chat/` / `agents_os/`

含义：

- 把 recent/local memory、sub-agent/team registry、protocol/docs、state 逐步迁出 `agents/`
- `butler_bot_agent/agents/` 最终只留历史归档或完全移除

优点：

- 真源更统一
- 目录语义更清楚

缺点：

- 这是实质性重构，不是简单改路径
- 需要同时修改 chat、butler_bot_code、memory pipeline、heartbeat、skills、docs

---

## 八、我建议你决策时只回答一个问题

你想把 `butler_bot_agent/agents/` 定义成哪一种：

1. **保留为 Butler 的脑子侧知识/记忆/协作根目录**
2. **只保留历史资料，运行时彻底迁出**

当前代码更接近选项 1。

