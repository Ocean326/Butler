# 0403 Butler Flow Codex 执行根隔离与 `repo_bound` 裁决

日期：2026-04-03  
状态：已落代码 / 当前真源  
所属层级：L1 `Agent Execution Runtime`

## 问题

Butler 之前虽然给每条 flow 准备了独立 `codex_home/`，但 `cli_runner` 仍会用仓库 `workspace_root` 执行 `codex exec -C <workspace>`。  
结果是：即使任务本身与当前仓库无关，Codex 也会先读到仓库根 `AGENTS.md`。

## 当前裁决

引入两层根目录语义：

- `workspace_root`：Butler 控制面、资产和 flow sidecars 所在根目录
- `execution_workspace_root`：Codex CLI 实际 `-C` / `cwd` 的执行根目录

并引入 `execution_context`：

- `repo_bound`
  - 适用于 `coding_flow`
  - Codex 直接在 `workspace_root` 执行
- `isolated`
  - 适用于非 `coding_flow`，当前重点是 `research_flow`
  - Codex 在 `~/.butler/codex_exec_roots/<workflow_id>/` 下执行
  - 默认不再借 Butler 仓库根的 `AGENTS.md`

## 代码落点

### 1. Flow 默认值与持久化

- `butler_flow/constants.py`
  - 新增 `execution_context` 常量与默认/归一化函数
- `butler_flow/state.py`
  - `workflow_state.json`、`flow_definition.json`、`runtime_plan.json` 新增 `execution_context`
- `butler_flow/app.py`
  - `prepare_new_flow`、模板实例化、asset definition、exec receipt 全部带上 `execution_context`

### 2. Runtime request 贯通

- `butler_flow/runtime.py`
  - supervisor 和 codex executor 的 runtime request 都带 `execution_context`
  - 旧 flow 缺字段时，按当前 `role_pack_id` 补默认

### 3. CLI 真正执行根切换

- `agents_os/execution/cli_runner.py`
  - `resolve_runtime_request()` 归一化 `execution_context`
  - `run_prompt_receipt()` 计算真实 `execution_workspace_root`
  - `_run_codex_detailed()` 继续复用传入 workspace，但现在这个 workspace 已经是“真实执行根”
  - receipt metadata 新增：
    - `requested_workspace`
    - `execution_workspace_root`
    - `execution_context`

## 对外可见结果

1. 本项目内 `coding_flow` 仍按仓库工作，不影响正常 coding flow
2. `research_flow` 等非 repo-bound flow 不再自动吃到 Butler 仓库根 `AGENTS.md`
3. `flow_exec_receipt` 与 `ExecutionReceipt.metadata` 现在都能直接看出：
   - 用户请求的 workspace
   - 实际执行根
   - 当前执行上下文

## 回归

- `test_butler_flow.py`
  - 覆盖 `coding_flow -> repo_bound`
  - 覆盖 `research_flow -> isolated`
  - 覆盖 exec receipt / resume runtime request
- `test_agents_os_wave1.py`
  - 覆盖 receipt metadata 的新字段
  - 覆盖 isolated execution root 的实际生效
- `test_chat_cli_runner.py`
  - 复验共享 `cli_runner` 链路未回归
