---
type: "note"
---
# 01 Chat Problem

日期：2026-03-23\
时间标签：0323_0002\
状态：待审阅

## 最新结论（2026-03-23 04:18）

### 1. 本次补充问题

围绕 `chat` 还剩下的几块 compat bridge，需要进一步回答：

1. 这些切片各自到底在做什么。
2. 哪些是真正应该留在 `chat` 的前台能力。
3. 哪些应该上收到 `agents_os` 或 `orchestrator`，而不是继续以“chat memory”名义存在。

### 2. 补充结论

结论先行：

**`chat` 长期应彻底固定为 `Product Entry / Interface Surface`，而不是 runtime source。**

也就是说：

- `chat` 负责前台交互、展示、交付、验收
- `agents_os` 负责执行内核与运行时 contract
- `orchestrator` 负责 mission/control plane

当前还挂在 compat bridge 上的四块遗留切片，应拆开看：

#### 2.1 `runtime request override`

它不是“聊天功能”，而是：

- 单轮执行时对 `cli/model/runtime_request` 的临时覆写
- 运行时上下文注入
- execution-side request shaping

因此更适合归：

- `agents_os / Execution Kernel Plane`

`chat` 只应读取覆写后的结果，不应长期拥有这套机制。

#### 2.2 `reply persistence`

它不是单纯“记忆功能”，而是：

- 回复发出后的 recent turn 收尾
- 异步写回
- 记忆抽取与持久化
- 某些回复后的治理/后处理动作

因此应拆成两部分：

- 通用 writeback / persistence contract -> `agents_os`
- 审计/回执/治理相关结果 -> `Governance / Observability Plane`
- 对话前台特有的展示投影 -> `chat`

#### 2.3 `background services`

它现在承接的主要是：

- 启动期维护线程
- heartbeat / sidecar / watchdog
- self_mind loop 等“保持运行态”的后台链路

这类能力长期显然不属于前台 `chat`，而应分流为：

- 控制与调度归 `orchestrator`
- 执行、恢复、runtime sidecar 归 `agents_os`

`chat` 最多保留：

- 入口启动
- 状态展示
- 用户侧控制入口

#### 2.4 `runtime control / self_mind / upgrade control surface`

这里最容易混层。

当前它同时混了三件事：

- 前台口令识别
- 升级批准/重启/恢复控制
- self_mind 前台聊天入口

长期应改成：

- 前台口令理解与用户交互留在 `chat`
- 批准/恢复/执行协议上收 `orchestrator + agents_os`
- `self_mind` 若继续存在，其 prompt/persona 可由 `chat` 拥有，但 loop/runtime/recovery 不应再由 `chat` 暗藏承接

### 3. 对当前迁移主线的直接约束

因此，后续“chat 完全迁出旧体系”不能再理解为：

- 把旧 `talk` 全量搬到 `chat`

而应理解为：

- 把前台交互真源收口到 `chat`
- 把执行真源收口到 `agents_os`
- 把后台控制真源收口到 `orchestrator`
- 把旧 `butler_bot_code/agent` 中只服务历史结构的过渡粘合层继续清空

### 4. 审阅建议

建议后续审阅 `chat` 相关改动时，统一按下面这个口径判定是否放对层：

1. 这是前台展示/交付/入口吗。是的话优先留 `chat`。
2. 这是执行 contract / runtime binding / writeback 吗。是的话优先进 `agents_os`。
3. 这是后台控制、调度、审批、恢复吗。是的话优先进 `orchestrator`，执行落点再由 `agents_os` 承接。
4. 如果它既依赖产品前台语义，又依赖后台运行态，那就继续切片，不允许再回到一个新的大总管类。

## 最新结论（2026-03-23 03:22）

### 1. 本次问题

围绕 `skill` 这一套，当前需要明确三件事：

1. 长期应该放在哪一层。
2. `agents_os` 是否应直接承接现在的 `skill_registry` 形态。
3. 若不直接承接，`agents_os` 还缺哪些与 skill/capability 相关的正式契约。

### 2. 当前判断

结论先行：

**`skill` 真源长期不适合直接放进 `agents_os`。**

它更适合放在长期规划文档中的：

**`Package / Framework Definition Plane`**

也就是：

- 静态定义层
- 冷知识/可编译包层
- package/catalog/mapping spec 所在层

而不是：

- `Execution Kernel Plane`
- `agents_os/runtime`
- 产品前台 `chat`

### 3. 判断依据

#### 3.1 从长期规划文档看

`docs/concepts/外部多Agent框架调研与Butler长期架构规划_20260323.md` 已明确：

- `agents_os` 长期角色是 `Runtime Core`
- 重点承接的是：
  - workflow VM
  - checkpoint / resume
  - runtime binding
  - capability runtime 装载
  - step execution
  - retry / repair / recovery

而定义型对象应归：

- `Package / Framework Definition Plane`
- `framework_profile`
- `capability_package`
- `workflow_package`
- `governance_policy_package`

所以从层次上讲：

- `skill` 更像 package / 方法包 / 定义对象
- `agents_os` 更像 capability runtime / binding / invocation kernel

#### 3.2 从当前代码看

当前 `skill_registry` 的真实行为仍是：

- 扫描 `skills/` 目录
- 读取 `SKILL.md`
- 解析 frontmatter
- 生成给 prompt 注入的 shortlist 文本

参考：

- [skill_registry.py](/C:/Users/Lenovo/Desktop/Butler/butler_main/butler_bot_code/butler_bot/registry/skill_registry.py)

这说明它本质上更接近：

- 定义目录 loader
- prompt 展示适配器

而不是：

- runtime kernel
- capability invocation engine

#### 3.3 从当前 `agents_os` 已有对象看

`agents_os` 现在已经有的是：

- `SubworkflowCapability`
- `CapabilityBinding`
- `CapabilityRegistry`
- `AgentSpec.capability_ids`

参考：

- [subworkflow_interface.py](/C:/Users/Lenovo/Desktop/Butler/butler_main/agents_os/runtime/subworkflow_interface.py)
- [capability_registry.py](/C:/Users/Lenovo/Desktop/Butler/butler_main/agents_os/runtime/capability_registry.py)
- [agent_spec.py](/C:/Users/Lenovo/Desktop/Butler/butler_main/agents_os/factory/agent_spec.py)

这套东西适合承接：

- 运行期 capability 解析
- binding
- route / policy / workflow kind 选择

但还不是：

- skill/package 定义模型
- skill invocation contract
- package 到 runtime 的编译器

### 4. 归位建议

建议把 skill/capability 分成三层看：

#### 4.1 Tool

最低层原子执行能力。

例如：

- shell
- browser
- OCR
- 抓取器
- file IO

长期应归：

- execution/runtime binding
- governance/tool policy

#### 4.2 Skill

基于 tool 的可复用方法包。

它的本质是：

- 如何调用若干 tool
- 适用场景是什么
- 输入输出约定是什么
- 风险级别是什么

长期应归：

- `Package / Framework Definition Plane`

#### 4.3 Capability

给运行时消费的调度对象。

它是 skill/package 编译后的执行视图。

长期应归：

- `agents_os`

也就是长期链路应该是：

`SKILL.md / package definition`
-> `CapabilityPackage`
-> `CapabilityBinding`
-> `agents_os runtime invocation`

而不是：

`agents_os` 直接扫描目录并向 chat prompt 拼 skills shortlist

### 5. 对当前目录的建议

短期内，`skill` 真源可以继续放在：

- `butler_main/butler_bot_agent/skills/`

但语义上应改成：

- 这是“定义层暂存区”
- 不是 body/runtime 代码目录

长期建议独立为正式定义目录，例如：

- `butler_main/packages/skills/`
- `butler_main/capability_packages/`
- `butler_main/framework_catalog/skills/`

三者取其一即可，关键不在名称，而在层次语义必须独立于：

- `chat`
- `agents_os/runtime`
- `butler_bot_code`

### 6. `agents_os` 里应该保留什么

`agents_os` 不应承接 `skill` 真源本体，但应该承接 skill 的运行时侧。

建议长期保留：

1. capability runtime contract
2. capability binding
3. capability invocation request/result/receipt
4. policy / approval / guardrail integration
5. tracing / observability
6. runtime host / executor binding

也就是说，`agents_os` 负责：

- “怎么执行 capability”

而不是负责：

- “有哪些 SKILL.md”
- “怎么给 chat 注入 skills 提示词”

### 7. 当前最需要完善的缺口

#### 7.1 缺正式 `CapabilityPackage` / `SkillPackage` 对象

现在只有 `SkillMetadata` 一类 prompt 侧扫描结构，不够形成长期对象模型。

建议后续至少补：

- `package_id`
- `version`
- `kind`
- `entry_contract`
- `expected_outputs`
- `required_tools`
- `required_policies`
- `risk_level`
- `executor_ref`
- `host_kind`

#### 7.2 缺“定义层 -> runtime”编译器

现在是：

- 目录扫描结果直接转 prompt 文本

长期应变成：

- skill/package 定义
-> compile
-> capability package / capability binding
-> runtime invocation

#### 7.3 缺 capability invocation 契约

`agents_os` 目前有 capability binding，但没有完整的：

- invocation request
- invocation result
- invocation receipt

这会导致 capability 还只是“能匹配”，没有成为真正可执行的第一类对象。

#### 7.4 缺 policy 映射

当前 skill 里的：

- `risk_level`
- `heartbeat_safe`
- `allowed_roles`

还只是 metadata。

长期应进入：

- `ToolPolicy`
- `Governance / Approval`
- `Bash/Side-effect policy`

#### 7.5 缺 tracing / observability

skill 被调用后，应该进入统一：

- receipt
- trace
- audit

而不是仅停在 prompt 里“口头说用了 skill”。

#### 7.6 缺 tool / skill / capability 三层分界

当前这三者仍偏混用。

长期必须明确：

- tool = 原子执行器
- skill = 方法包
- capability = runtime 调度单元

### 8. 对当前 `agents_os` 的一个直接修正建议

当前：

- [provider_interfaces.py](/C:/Users/Lenovo/Desktop/Butler/butler_main/agents_os/runtime/provider_interfaces.py)

里还有：

- `PromptRuntimeProvider.render_skills_prompt()`

这个接口说明 `agents_os` 现在仍承担了“给产品 prompt 注入 skills shortlist”的语义。

这条边界长期不对。

更合理的是：

- `agents_os` 只认 capability ids / bindings / policies / invocation
- `chat` 自己决定是否把某些 capability shortlist 渲染进 prompt

也就是：

- “prompt 展示”留在产品层
- “capability 执行”留在 runtime 层

### 9. 最终建议

最终建议收口如下：

1. `skill` 真源不放 `agents_os`
2. `skill` 长期归定义层 / package plane
3. `agents_os` 只承接 skill/package 的 runtime contract、binding、invocation、policy、receipt
4. `chat` 只保留“如何把可用能力展示给 chat 用户”的产品层逻辑
5. 下一阶段应补一版：
   - `CapabilityPackage`
   - `CapabilityInvocationRequest/Result/Receipt`
   - package -> binding compiler
   - policy/tracing 接线

### 10. 审阅重点

后续审阅建议优先判断三件事：

1. 是否同意把 `skill` 从“prompt 注入物”升级成正式 package 定义对象。
2. 是否同意把 `PromptRuntimeProvider.render_skills_prompt()` 从长期 `agents_os` 语义中降级出去。
3. 是否同意后续用 `CapabilityPackage -> CapabilityBinding -> Invocation` 作为 Butler skill/capability 的正式主线。
