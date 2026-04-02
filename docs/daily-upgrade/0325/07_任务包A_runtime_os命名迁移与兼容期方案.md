# 07 任务包 A：`runtime_os` 命名迁移与兼容期方案

日期：2026-03-25  
时间标签：0325_0007  
状态：已迁入完成态 / 命名迁移输入冻结

## 结论

### 推荐新名字

推荐把新总名定为：`runtime_os`

不继续保留 `agents_os` 作为总名，也不保留 `multi_agents_os` 作为第二层独立总包名。

原因很直接：

- `agents_os` 现在已经不只是单 agent runtime。
- `multi_agents_os` 现在承载的不是“另一个总控系统”，而是第二层 `process runtime substrate` 的 session/template/factory。
- `runtime_os` 能同时容纳：
  - `agent_runtime`
  - `process_runtime`
- 它不会像 `multi_agents_os` 那样把第二层语义藏在一个“多人协作”特例名里。

本轮不建议再发散第三套总名。

## 审计结果

### `agents_os` 当前真实职责

当前 `butler_main/agents_os/` 同时承载两层语义：

1. 更偏第一层 `Agent Runtime`
   - `contracts/`
   - `context/`
   - `execution/`
   - `factory/`
   - `state/`
   - `skills/`
   - `runtime/` 里与单次 run、request、host、kernel、memory、writeback 相关的大部分导出
2. 已经混入第二层 `Process Runtime`
   - `workflow/`
   - `governance/`
   - `protocol/`
   - `recovery/`
   - `verification/`
   - `runtime/execution_runtime.py`
   - `runtime/__init__.py` 里已经把 `WorkflowCheckpoint`、`WorkflowCursor`、`ExecutionRuntime`、`WorkflowReceipt` 等第二层对象一起暴露出来

### `multi_agents_os` 当前真实职责

当前 `butler_main/multi_agents_os/` 不像一个独立产品层，更像第二层 runtime substrate：

- `session/`：`WorkflowSession`、`SharedState`、`ArtifactRegistry`、`CollaborationSubstrate`
- `templates/`：`WorkflowTemplate`
- `factory/`：`WorkflowFactory`
- `bindings/`：`RoleBinding`

这套东西被 `orchestrator/service.py` 直接消费，说明它已经是第二层正式依赖，不适合继续作为一个语义游离的旁包存在。

### 真实引用面

按当前仓库扫描：

- 命中 `agents_os` 的文件数：`103`
- 命中 `multi_agents_os` 的文件数：`6`

`agents_os` 命中分组：

- `butler_main/chat`：`30`
- `butler_main/orchestrator`：`6`
- `butler_main/butler_bot_code/tests`：`29`
- `docs`：`15`

这说明 `agents_os` 已经不是内核目录名，而是对外 API 名、测试名、文档名、patch 字符串名。

### 当前最硬的命名耦合点

不只是 import：

1. 裸包导入仍大量存在
   - 例如 `from agents_os.contracts import ...`
   - 因为很多测试直接把 `butler_main/` 加进 `sys.path`
2. namespaced 导入也同时存在
   - 例如 `from butler_main.agents_os.runtime import ...`
3. `WorkflowIR` 里把旧名字写进了执行边界字段
   - `execution_owner = "agents_os"`
   - `collaboration_owner = "multi_agents_os"`
4. 测试断言和 `mock.patch` 字符串也写死了旧名字
   - 例如 `agents_os.execution.cli_runner.run_prompt`

所以这轮不适合直接物理 rename 目录后再被动补锅。

## 推荐迁移策略

### 推荐方案

先引入新的兼容命名空间：

- `butler_main/runtime_os/`
- 同时支持：
  - `import runtime_os`
  - `import butler_main.runtime_os`

然后把迁移分成三段：

### Phase 1：先立新壳，不动旧包

本轮已落地：

- 新增 `butler_main/runtime_os/`
- 新增：
  - `runtime_os.agent_runtime`
  - `runtime_os.process_runtime`
- 旧的 `agents_os` / `multi_agents_os` 暂时原样保留

这样做的价值：

- 新代码可以马上停止继续扩散旧名字
- 旧代码和测试暂时不被大面积打断
- codemod 可以开始工作，但不需要一次写完所有目录 rename

### Phase 2：机械替换 import，保留旧壳

优先机械替换：

- `chat/`
- `orchestrator/`
- `butler_bot_code/tests/`

建议新导入方向：

- `agents_os.contracts/context/execution/factory/state/skills/runtime(非 workflow/gate 部分)`
  - 优先迁到 `runtime_os.agent_runtime`
- `agents_os.workflow/governance/protocol/recovery/verification/runtime(流程与 gate 部分)`
  - 优先迁到 `runtime_os.process_runtime`
- `multi_agents_os.*`
  - 优先迁到 `runtime_os.process_runtime`

旧包在这一阶段继续保留为兼容壳，不急着删。

### Phase 3：目录物理迁移

等 import 面和字符串硬编码收缩后，再做真实目录 rename：

| 当前目录 | 未来目录建议 | 处理方式 |
| --- | --- | --- |
| `butler_main/agents_os/contracts` | `butler_main/runtime_os/agent_runtime/contracts` | 后续物理迁移 |
| `butler_main/agents_os/context` | `butler_main/runtime_os/agent_runtime/context` | 后续物理迁移 |
| `butler_main/agents_os/execution` | `butler_main/runtime_os/agent_runtime/execution` | 后续物理迁移 |
| `butler_main/agents_os/factory` | `butler_main/runtime_os/agent_runtime/factory` | 后续物理迁移 |
| `butler_main/agents_os/state` | `butler_main/runtime_os/agent_runtime/state` | 后续物理迁移 |
| `butler_main/agents_os/skills` | `butler_main/runtime_os/agent_runtime/skills` | 后续物理迁移 |
| `butler_main/agents_os/runtime` 中 L1 部分 | `butler_main/runtime_os/agent_runtime/*` | 拆文件后迁移 |
| `butler_main/agents_os/workflow` | `butler_main/runtime_os/process_runtime/workflow` | 后续物理迁移 |
| `butler_main/agents_os/governance` | `butler_main/runtime_os/process_runtime/governance` | 后续物理迁移 |
| `butler_main/agents_os/protocol` | `butler_main/runtime_os/process_runtime/protocol` | 后续物理迁移 |
| `butler_main/agents_os/recovery` | `butler_main/runtime_os/process_runtime/recovery` | 后续物理迁移 |
| `butler_main/agents_os/verification` | `butler_main/runtime_os/process_runtime/verification` | 后续物理迁移 |
| `butler_main/agents_os/runtime/execution_runtime.py` | `butler_main/runtime_os/process_runtime/execution_runtime.py` | 必改语义后迁移 |
| `butler_main/multi_agents_os/session` | `butler_main/runtime_os/process_runtime/session` | 先兼容、后物理迁移 |
| `butler_main/multi_agents_os/templates` | `butler_main/runtime_os/process_runtime/templates` | 先兼容、后物理迁移 |
| `butler_main/multi_agents_os/factory` | `butler_main/runtime_os/process_runtime/factory` | 先兼容、后物理迁移 |
| `butler_main/multi_agents_os/bindings` | `butler_main/runtime_os/process_runtime/bindings` | 先兼容、后物理迁移 |

## 哪些目录本轮直接 rename，哪些先保留壳

### 本轮不建议直接 rename

- `butler_main/agents_os`
- `butler_main/multi_agents_os`

原因：

- 引用面已经跨 `chat / orchestrator / tests / docs`
- 还存在裸包 import 和 patch 字符串
- `WorkflowIR` 里还有旧名字写死在边界字段里

### 本轮建议新增兼容壳

- `butler_main/runtime_os/`
- `runtime_os.agent_runtime`
- `runtime_os.process_runtime`

兼容期内三套名字的关系是：

- `runtime_os`：新总名，后续只增不减
- `agents_os`：旧总名兼容壳
- `multi_agents_os`：旧的第二层兼容壳

## 是否需要脚本

需要。

原因：

- `agents_os` 的影响面太大，纯手改容易漏掉裸包 import、`butler_main.*` import 与测试 patch 字符串的混合情况。
- `runtime/execution_runtime.py` 一带的导入分层并不是简单目录 rename，必须先按 symbol 归类到 `agent_runtime` 或 `process_runtime`。

## 脚本方案

已新增脚本草案：

- `tools/runtime_os_codemod.py`

当前职责：

1. 扫描 Python 文件中的安全 import 形式
2. 把可机械替换的导入改写为：
   - `runtime_os.agent_runtime`
   - `runtime_os.process_runtime`
   - 或 `butler_main.runtime_os.*`
3. 对剩余命中保留人工清理空间

当前刻意不做的事：

- 不直接改 `WorkflowIR` 里的边界字段值
- 不直接改 `mock.patch("agents_os...")` 这类字符串常量
- 不直接物理 rename 目录

建议运行方式：

```powershell
python tools/runtime_os_codemod.py
python tools/runtime_os_codemod.py --write
```

默认优先扫：

- `butler_main/chat`
- `butler_main/orchestrator`
- `butler_main/butler_bot_code/tests`

当前 dry-run 结果：

- 可安全改写文件：`68`
- 可安全改写 import 语句：`104`
- 仍有剩余旧名命中的文件：`7`

这说明这轮确实适合先走“兼容壳 + codemod + 人工补硬编码”的路线，而不是直接物理 rename。

## 本轮已落地的最小代码

1. 新增 `butler_main/runtime_os/` 命名空间
2. 新增：
   - `runtime_os.agent_runtime`
   - `runtime_os.process_runtime`
3. 新增 codemod 草案 `tools/runtime_os_codemod.py`
4. 新增最小测试，确认新 namespace 可导入

## 风险

1. `runtime_os` 现在还是兼容壳，不是真正完成物理迁移
2. `WorkflowIR.execution_boundary()` 仍使用旧字符串：
   - `agents_os`
   - `multi_agents_os`
3. 测试文件名与文档历史名里仍大量保留旧称
4. `agents_os.runtime` 里有少量 L1/L2 混杂导出，后续仍需继续拆

## 首日动作建议

按优先级继续推进：

1. 先跑 `tools/runtime_os_codemod.py` 做 dry-run，确认 import 替换面
2. 第一批先改 `chat/` 与 `orchestrator/` 的 import
3. 第二批改 `tests/`
4. 再回头改 `WorkflowIR.execution_boundary()` 与相关测试断言
5. 最后再做真实目录迁移，而不是反过来
