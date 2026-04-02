# 0402 Butler Flow Doctor 恢复角色与实例级静态资产修复

## 目标

- 给 `butler-flow` 增加一个轻量 `doctor` 临时角色。
- 让 supervisor 在长流出现重复 `service_fault`、`resume/no-rollout`、session 绑定异常时，优先把问题导向当前 flow 实例内部修复。
- 若 `doctor` 判断问题属于 `butler-flow` 框架代码，而不是当前 flow 资产，则自动暂停并把诊断交回 operator。

## 当前裁决

- `doctor` 是 **ephemeral specialist**，不是固定 team 成员。
- `role_guidance` 仍然只是 manager 创建 template/flow 时的参考；`doctor_policy` 也只是 supervisor 的恢复提示，不引入新的重制度。
- 实例级静态资产现在允许并鼓励物化到当前 flow 下：
  - `flow_definition.json`
  - `bundle/manager.md`
  - `bundle/supervisor.md`
  - `bundle/doctor.md`
  - `bundle/skills/doctor/SKILL.md`
- 当前 KDD flow `flow_20260402111642_01929624` 已升级到 `execution_mode=medium`、`session_strategy=role_bound`，并写入 `doctor_policy + role_guidance + bundle_manifest`。

## 行为口径

- heuristic supervisor 与 llm supervisor 都允许拉起 `doctor`。
- `doctor` 触发条件以实例 `doctor_policy` 为准，默认至少覆盖：
  - `repeated_service_fault`
  - `same_resume_failure`
  - `session_binding_invalid`
- 一旦进入 `doctor`：
  - executor 强制冷启动，不复用坏掉的旧 thread
  - supervisor 会先隔离当前坏掉的 role session 绑定
  - prompt 会注入实例 bundle 中的 `doctor.md + SKILL.md`
- 若 `doctor` 输出以 `DOCTOR_FRAMEWORK_BUG:` 开头：
  - flow 自动进入 `paused`
  - `approval_state=operator_required`
  - 诊断文本写回 `pending_codex_prompt`

## 代码落点

- `butler_main/butler_flow/runtime.py`
- `butler_main/butler_flow/compiler.py`
- `butler_main/butler_flow/manage_agent.py`
- `butler_main/butler_flow/state.py`
- `butler_main/butler_flow/app.py`
- `butler_main/butler_flow/role_runtime.py`
- `butler_main/agents_os/execution/cli_runner.py`

## 验收

- `doctor` 可由 heuristic supervisor 触发。
- 重复 `thread/resume failed: no rollout found` 时，不再继续盲目 `resume` 旧 thread。
- `doctor` 框架级报错会自动 pause，而不是继续进入 judge/retry。
- 新建/保存 flow 实例会物化实例级 bundle 与 `flow_definition.json`。
