# heartbeat_branch_contract

> **用途**：这是“运行真源”的长期记忆实现层规范，用于约束心跳 planner 输出的 `task_groups.branches` 在进入执行器之前必须满足的最小 contract。  
> 目标是：**缺字段即失败/降级，让问题可见**，避免执行器悄悄补默认值导致规范漂移。

---

## 0. 约定一句话

心跳 planner 输出的每条 `task_groups.branches[*]` 在执行前必须通过校验：**必须包含 `agent_role`**，且 branch 的 `prompt` 头部必须显式出现 `role=...` 与 `output_dir=...`（或同时提供结构化字段 `role`/`output_dir`，但仍需在 prompt 头部显式两行用于可读性与执行侧一致性）。

---

## 1. 必须字段（planner 输出）

- **`agent_role`**：执行角色（对应 `agents/sub-agents/` 下的角色名或等价执行角色名）。
- **`prompt`**：执行指令正文。

> 说明：`HeartbeatOrchestrator.normalize_plan_task_groups()` 当前会对缺失字段做默认值兜底（例如 `agent_role` 缺失时补 `executor`）。这类“悄悄补齐”会掩盖 planner 输出不合规，本规范要求升级后改为**执行前严格校验**。

---

## 2. prompt 头部硬约束（执行前校验）

在 branch 的 `prompt` 文本中，必须满足：

- 在 **前 12 行** 内出现 `role=...`
- 在 **前 12 行** 内出现 `output_dir=...`

并且：

- `output_dir` 必须是 `./工作区` 或 `./工作区/<子目录>`（不允许写到根目录或身体目录）
- 建议 `role` 与 `agent_role` 对齐，但两者语义不同：
  - `agent_role`：执行角色（选用哪个 sub-agent）
  - `role=`：逻辑角色/本分支身份（用于输出归档与对外表述）

---

## 3. 结构化字段（推荐，便于沉淀）

建议 planner 在 branch 对象中同时输出：

- `role`: 逻辑角色（如 `literature` / `secretary` / `research-ops` / `agent_upgrade` / `heartbeat-executor`）
- `output_dir`: `./工作区/...` 路径

执行器与台账在持久化快照/任务 ledger 中应优先使用结构化字段沉淀；若只提供 prompt 两行，则可以解析两行补齐结构化字段，但当解析失败时应明确报错。

---

## 4. 校验失败时的处理策略

- **优先策略（planner 侧兜底补齐）**：若 planner 已给 `role` 但缺 `output_dir`，执行器可尝试用 role→output_dir 映射推断（如 `role=secretary` → `./工作区/secretary`）。
- **无法推断时明确失败**：不能推断则该 branch 不执行（或标记失败），并输出清晰报错，包含：
  - 缺失字段列表（如 `agent_role` / `role=` / `output_dir=`）
  - 建议修复方式：在 branch prompt 头部补齐两行，并在 branch JSON 中显式携带 `agent_role`

---

## 5. 与 `heartbeat_tasks.md` 的读口同步

`heartbeat_tasks.md` 的「Branch contract」段落是 planner 的读口；本文件是长期记忆实现层真源。两者内容需保持一致。

