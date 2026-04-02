# 0403 Butler Flow supervisor 控制画像与 agents-flow 治理升级

日期：2026-04-03  
状态：已落代码 / 当前真源  
所属层级：L1 `Agent Execution Runtime`

## 1. 本轮裁决

本轮把 Butler Flow 的长流治理从“散落在 prompt、默认值和 operator 手工补丁里的经验约束”收口成轻量结构化合同：

- 用 `control_profile` 承载 supervisor / worker 的默认治理画像
- 用 `execution_context` 只表达执行位置，不再偷带 repo contract 语义
- 用 `repo_binding_policy + repo_contract_paths` 单独表达 repo contract 是否显式绑定
- 用 `role_guidance / doctor_policy / supervisor_profile` 提供轻量参考，而不是硬编码 team 制度

当前对外口径是：

1. `project_loop / managed_flow` 默认 `execution_mode=medium + session_strategy=role_bound`
2. `control_profile` 是实例级运行合同，当前 public enum 只保留：
   - `repo_binding_policy=disabled`
   - `repo_binding_policy=explicit`
3. `repo_bound` 只表示“在仓库里执行”，不再默认等于“显式绑定 repo contract”
4. 仓库级 `AGENTS.md` 不是 ambient authority；只有进入 `control_profile.repo_contract_paths` 才算显式 repo contract
5. supervisor 的控制调整不再只是展示字段，而会回写实例态 `flow_state.control_profile`

## 2. 当前治理模型

### 2.1 `control_profile`

当前静态/实例治理画像统一收口为：

- `task_archetype`
- `packet_size`
- `evidence_level`
- `gate_cadence`
- `repo_binding_policy`
- `repo_contract_paths`
- `manager_notes`

其中：

- `packet_size / evidence_level / gate_cadence / repo_binding_policy`
  - 是 supervisor 可调的运行治理项
- `repo_contract_paths`
  - 只由 manager/asset/operator 显式绑定，不由 ambient repo 环境自动注入
- `force_gate_next_turn / force_doctor_next_turn`
  - 仍是实例态 transient flag，用于 operator 或恢复路径

### 2.2 三个概念正式拆开

- `execution_context`
  - Codex 在哪里执行：`repo_bound` 或 `isolated`
- `execution_workspace_root`
  - 本次 runtime request 实际使用的执行根
- `control_profile.repo_binding_policy`
  - 当前 turn 是否显式绑定 repo contract

这三者现在不能再互相代替。

## 3. manager -> supervisor 的交接口径

manager 当前负责的是“把治理默认值设计好，再交给 supervisor 执行”，不是自己扮演重制度审计器。

manager 在 template / flow 设计阶段重点补齐：

- `goal`
- `guard_condition`
- `phase_plan`
- `supervisor_profile`
- `control_profile`
- `role_guidance`
- `doctor_policy`
- `source_bindings`

其中：

- `role_guidance`
  - 只服务两件事：
    1. 给 manager 创建 template / flow 时提供参考
    2. 给 supervisor 在 runtime 中选择临时节点角色时提供参考
- `doctor_policy`
  - 只给出恢复触发和作用域，不引入重治理制度
- `supervisor_profile`
  - 只表达该类任务更适合什么管理风格与质量门槛

manager prompt 当前只保留精选原则，不再把整套治理逻辑硬塞进 prompt。

## 4. supervisor 当前运行语义

### 4.1 默认消费方式

supervisor packet 当前明确要求：

- 把 `role_guidance` 当 advisory only
- 忽略未显式绑定的 ambient repo instructions
- 把 `control_profile` 当成当前 flow 的默认 control envelope
- 在 repeated service fault / resume binding failure / no-rollout 等情况下优先考虑 `doctor`

### 4.2 控制调整现在会真正生效

supervisor 现在可以返回并落地以下控制调整：

- `packet_size`
- `evidence_level`
- `gate_cadence`
- `repo_binding_policy`

这些字段会回写到实例态 `flow_state.control_profile`，因此后续：

- executor prompt
- repo contract appendix
- runtime request
- 后续 supervisor / worker packet

都会看到同一份当前控制画像，而不是“decision 看起来变了，但运行还按旧画像继续”。

### 4.3 实例态优先于资产态

当前 packet/build path 统一改为：

- `flow_board.control_profile`
  - 直接以实例态 `flow_state.control_profile` 为准
- `asset_context.control_profile`
  - 以实例态覆盖资产定义的默认值
- `supervisor_knowledge`
  - 运行时会剥掉旧 compiled knowledge 里的 `[control profile]` 段，再拼接当前实例态控制画像

这样可以避免 operator action 或 supervisor 调整之后，同一 packet 中同时出现“资产旧画像”和“实例新画像”。

## 5. operator 与 doctor

operator 当前已有 typed control actions：

- `shrink_packet`
- `broaden_packet`
- `force_gate`
- `force_doctor`
- `bind_repo_contract`
- `unbind_repo_contract`

当前语义：

- `bind_repo_contract`
  - 显式把合同路径写入 `repo_contract_paths`
- `unbind_repo_contract`
  - 清空显式绑定
- `force_gate / force_doctor`
  - 只影响下一轮 supervisor 决策，再在消费后清掉 transient flag

doctor 当前仍保持 lightweight：

- 优先修当前 flow 的 runtime/session/static assets
- 若确认是 `butler-flow` 框架 bug，则交回 operator / pause
- 不扩展成独立重制度控制层

## 6. 代码落点

- `butler_main/butler_flow/state.py`
  - `control_profile` 默认值、legacy alias 归一化、supervisor knowledge 编译
- `butler_main/butler_flow/runtime.py`
  - supervisor 决策归一化
  - supervisor control adjustment 回写
  - asset/runtime context 以实例态控制画像优先
  - repo contract appendix 只认显式绑定
- `butler_main/butler_flow/compiler.py`
  - `governance_policy`
  - `turn_task_packet` / prompt packet 透传 control fields
- `butler_main/butler_flow/manage_agent.py`
  - manager 只保留精选原则 + skill 化注入
- `butler_main/butler_flow/models.py`
  - typed packet 补齐 `gate_cadence / repo_binding_policy`

## 7. 回归

- `./.venv/bin/python -m pytest -q butler_main/butler_bot_code/tests/test_butler_flow.py`
- `./.venv/bin/python -m pytest -q butler_main/butler_bot_code/tests/test_butler_flow_tui_app.py butler_main/butler_bot_code/tests/test_butler_flow_tui_controller.py`
- `./.venv/bin/python -m pytest -q butler_main/butler_bot_code/tests/test_agents_os_wave1.py butler_main/butler_bot_code/tests/test_chat_cli_runner.py`

本轮新增覆盖重点：

- supervisor control adjustment 会回写实例态
- asset/runtime context 优先使用实例态 `control_profile`
- legacy `inherit_workspace` 归一化到 `disabled`
- operator control action 测试名去重，避免被后定义覆盖

## 8. 下一步技术债

当前方向已对齐，但抽象还没完全收口。下一轮优先：

1. 继续精简 `manage_agent.py`
   - 把阶段推进、确认门控、pending-action 替换保护尽量沉到 persistence / normalize 层
2. 继续拆 `runtime.py`
   - 把 `doctor`、repo contract、supervisor mutation/control helper 从 runtime 巨石中抽离
3. 明确 supervisor knowledge 的 canonical object 与 prompt projection 边界
   - 尽量减少对 `knowledge_text` 的半结构依赖
