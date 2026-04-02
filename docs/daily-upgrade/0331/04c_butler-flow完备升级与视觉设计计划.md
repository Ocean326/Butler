# 04c-butler-flow 完备升级与视觉设计主计划

日期：2026-03-31  
状态：已落代码 / 已验收  
所属层级：L1 `Agent Execution Runtime`（前台附着 CLI），辅用 L2 状态/轨迹存储  
定位：`butler-flow` 作为系统级 CLI 入口的终端产品化与视觉升级主线，不进入 `campaign/orchestrator` 真源

关联：

- [00_当日总纲.md](./00_当日总纲.md)
- [02_前台WorkflowShell收口.md](./02_前台WorkflowShell收口.md)（现役真源）
- [04a_交互式CLI对标调研与ButlerFlow升级方案.md](./04a_交互式CLI对标调研与ButlerFlow升级方案.md)（外部 CLI 对标与研究）
- [04b-butler-flowV1版本开发计划.md](./04b-butler-flowV1版本开发计划.md)（已落地 V1）
- [04_前台长Agent监督Workflow产品化草稿计划.md](./04_前台长Agent监督Workflow产品化草稿计划.md)（产品面上位草稿）
- [01_Agent监管Codex实践_exec与resume.md](./01_Agent监管Codex实践_exec与resume.md)

---

## 改前四件事（执行协议）

| 项 | 内容 |
| --- | --- |
| 目标功能 | 把当前 `butler-flow` 从“可用的前台 flow CLI”升级成一套完整的系统级终端产品：全屏 TUI、清晰的信息架构、operator action 面、slash commands、hooks / permissions / subagent events，并保持现有 `run / resume / exec / status / list / preflight / action` 与非 TTY 契约。 |
| 所属层级 | 主落 L1 `Agent Execution Runtime`，状态真源继续使用本地 `workflow_state.json / turns.jsonl / actions.jsonl / artifacts.json`，不进入 `campaign/orchestrator`。 |
| 当前真源文档 | [02_前台WorkflowShell收口.md](./02_前台WorkflowShell收口.md)。 |
| 计划查看的代码与测试 | `butler_main/butler_flow/`、`butler_main/agents_os/execution/cli_runner.py`、`butler_main/chat/cli/runner.py`；回归以 `test_butler_flow.py`、`test_butler_cli.py`、`test_chat_cli_runner.py`、`test_codex_provider_failover.py` 为主。 |

---

## 一句话裁决

`04c` 不是“再做一个更花的 launcher”，而是把 `butler-flow` 升级为 **Textual 全屏 operator shell**，吸收 Codex / Claude 类 CLI 的核心交互结构：

- fullscreen / alternate screen
- raw keyboard input + 快捷键
- slash commands
- lifecycle hooks
- permissions / approvals
- subagent / runtime events

但**不照搬技术栈**。  
本轮实现路线固定为：

`Python runtime + Textual shell + serializable event spine`

而不是：

`Rust / Node 重写 + 嵌套 vendor 原生 TUI`

---

## 实施回写（2026-03-31 夜间完成）

本轮已实际落地：

- 新增 `requirements-cli.txt`，CLI 依赖单独安装
- 新增 `butler_main/butler_flow/events.py`
- 新增 `butler_main/butler_flow/tui/`
- `butler-flow` 在交互终端无子命令时，优先进入 Textual launcher
- 新增 `butler-flow tui`
- `butler-flow run` / `resume` 在交互终端下默认进入 attached TUI run screen
- 新增 `run --plain` / `resume --plain`
- 新增 `butler-flow exec run` / `butler-flow exec resume`
- `exec` 固定为非 TUI、stdout 全 JSONL、最后一行 `flow_exec_receipt`
- `FlowRuntime` 已接入 `FlowUiEvent` 事件脊柱
- TUI 已接入 slash commands、confirm-based operator action、launcher snapshot、history/settings 整屏模式、single flow summary + phase step history
- 非 TTY、`--json` 与 plain CLI 契约保持不变

已验证：

- `./.venv/bin/python -m pytest butler_main/butler_bot_code/tests/test_butler_flow.py butler_main/butler_bot_code/tests/test_butler_cli.py -q`
- `./.venv/bin/python -m pytest butler_main/butler_bot_code/tests/test_chat_cli_runner.py -q`
- `./.venv/bin/python -m pytest butler_main/butler_bot_code/tests/test_codex_provider_failover.py -q`
- `./tools/butler-flow --help`
- `./tools/butler-flow preflight`
- `./.venv/bin/python -m butler_main --help`
- `./.venv/bin/python -m butler_main.butler_flow preflight`
- `./.venv/bin/python - <<'PY' ... import ButlerFlowTuiApp ... PY`

---

## 0. 本版定位与边界

### 0.1 定位

- `butler-flow` 是系统级 CLI 入口，交互模式升级为 **Textual 全屏 TUI**。
- 运行内核仍由 Python 负责：现有 `FlowRuntime`、`turns.jsonl / actions.jsonl / artifacts.json` 继续是真源。
- `cli_runner` 继续作为执行与事件输出引擎，UI 只消费结构化事件。
- 本轮目标不是“把终端做得像 IDE”，而是做出一条 **冷静、专业、可恢复、可操作、可演进** 的 operator shell。

### 0.2 硬边界

- 不进入 `campaign/orchestrator` 主链。
- 不嵌套 vendor 原生 TUI（Codex / Claude / Cursor 自带全屏界面）：
  Butler Own UI + 子进程结构化输出 是固定裁决。
- 不做 Rust / Node 重写。
- 仅在架构上预留未来 native/Ink shell 复用入口。
- 非 TTY、`--json`、现有脚本化调用与退出码契约必须保持。

### 0.3 与 04a / 04b / 04 的关系

- `04a`：外部 CLI 对标、技术路线比较、研究材料。
- `04b`：V1 已落地实现计划与实施回写。
- `04`：前台长 workflow 的更上位产品面草稿。
- `04c`：下一轮 CLI 终端产品化与视觉设计的 **主实施计划**。

---

## 1. 关键裁决（必须写死）

### 1.1 技术路线

1. **Python + Textual 先落地**。
2. `Textual` 是全屏 TUI 主依赖；plain CLI 保留为 fallback。
3. 当前不把 CLI shell 拆成独立 sidecar 进程；先在 Python 单栈内把 controller / event spine 设计干净。
4. 未来若要做 native/Ink shell，只复用事件和控制器，不回头重做运行时真源。

### 1.2 入口行为

1. `butler-flow`：
   - TTY + 无子命令 -> 进入 TUI
   - 非 TTY -> 维持当前 help / plain 行为
2. 新增 `butler-flow tui`：
   - 强制进入 TUI
   - 若依赖缺失或终端能力不足，报错并给安装提示
3. `butler-flow run` / `resume`：
   - TTY 下默认进入 attached run screen
   - 增加 `--plain` 强制走当前纯文本路径
4. `status / list / preflight / action`：
   - 文本 / JSON 契约继续保留
   - 同等能力在 TUI 内也必须可操作
5. `python -m butler_main` 与 `butler-flow` 共享相同交互语义。

### 1.3 功能吸收原则

要吸收的是：

- fullscreen / alternate-screen operator shell
- raw input + 快捷键体系
- slash command 面
- lifecycle hooks
- permissions / approvals
- subagent / runtime event rail

不直接吸收的是：

- Rust 运行时
- Ink / React 终端框架
- Yoga 布局体系
- vendor 原生审批或工具协议的实现细节

### 1.4 事件脊柱要求

`FlowUiEvent` 必须可序列化，未来可被：

- Textual shell
- desktop / web operator surface
- future native/Ink shell

共同消费。

---

## 2. UI 与美观性设计

### 2.1 视觉方向

目标感受固定为：

- 冷静
- 专业
- 工具感强
- 高信息密度
- 层级清晰

色彩方向：

- 主色：冷青 / 钢蓝
- 辅色：灰白
- 告警：琥珀
- 错误：暗红
- 成功：低饱和绿

明确禁止：

- 霓虹黑客风
- 过多 ASCII 装饰
- 彩虹状态条
- 强动画和整屏闪烁

### 2.2 信息架构

全屏 TUI 现役信息架构固定为三种模式：

1. **Single Flow Screen**
   - 左栏：`flow_id / kind / status / phase / attempts / goal / guard / last judge / last operator / phase step history`
   - 右栏：可滚动 transcript
   - 底部：action bar + slash input
2. **History Screen**
   - 通过 `/history` 进入
   - 左栏顶部是头部样式 summary，其下是 workspace 下近期 flows
   - 左栏高亮只更新右栏 detail，不立即切 flow
   - 右栏默认展示摘要、latest signals、recent step 简表
   - `Enter` 选中并返回 single flow screen
3. **Settings Screen**
   - 通过 `/settings` 进入
   - 当前只管理 session-scoped 的 transcript follow / runtime event / filter 偏好

### 2.3 响应式规则

- `>=160` 列：single flow 左右双栏完整模式
- `120-159` 列：左栏压缩，但仍保留 summary + step history
- `<120` 列：history / settings 优先整屏，single flow 维持左右双栏的最小可用排版
- `<100` 列或终端能力不足：自动回退 plain 模式

### 2.4 呈现规范

- 只保留一级 panel 边框，不叠多层框。
- badge 文案统一短大写：`RUNNING / PAUSED / FAILED / DONE / PLAN / IMP / REVIEW`
- transcript 中 assistant 正文、system event、judge summary 必须颜色分层。
- judge 输出显示为 compact verdict card，不直接裸打印 JSON。
- 历史 flow 选择不再常驻主视图左栏，只通过 `/history` 调出。
- `/history` 左栏顶部 summary 改为“像 item 的非交互头部”，不再单独占一个大块 status panel。
- 单 flow 左栏必须同时看到“当前状态”和“历史步骤”，不再把核心信息拆给独立 inspector pane。
- `/history` 右栏默认不是纯 preview 文本，而是“摘要 + steps + latest signals”的可滚动 detail。
- artifacts 用 compact list 呈现，不把全文塞主视图。
- 只允许轻量 spinner、pulse、选中高亮；禁止“动态花活”。

---

## 3. 架构与模块拆分（Textual）

新增目录：

- `butler_main/butler_flow/tui/`

建议结构：

- `app.py`
  - Textual App 入口与路由
- `screens/`
  - launcher
  - run
  - flow_detail
  - confirm
  - help
- `widgets/`
  - status_rail
  - flow_list
  - transcript
  - inspector
  - action_bar
- `controller.py`
  - 对 `FlowApp / FlowRuntime` 的 UI 适配层
- `events.py`
  - `FlowUiEvent` 定义与映射
- `theme.py`
  - 颜色、布局、spacing tokens

固定原则：

- `FlowApp` 保持业务协调层，不直接承担全屏 UI 逻辑。
- `display.py` 保留为 plain fallback。
- `RichFlowDisplay` 不再继续扩成主实现路线；未来只承担轻量兼容显示。
- `chat/cli/runner.py` 的 `TerminalConsole` 只作为设计参考，不做直接耦合复用。

---

## 4. 事件脊柱（FlowUiEvent）

### 4.1 最小字段

- `kind`
- `flow_id`
- `phase`
- `attempt_no`
- `created_at`
- `message`
- `payload`

### 4.2 固定事件种类

- `launcher_loaded`
- `flow_selected`
- `run_started`
- `supervisor_decided`
- `codex_segment`
- `codex_runtime_event`
- `judge_result`
- `operator_action_applied`
- `artifact_registered`
- `phase_transition`
- `run_completed`
- `run_failed`
- `run_interrupted`
- `warning`
- `error`

### 4.3 当前事件映射来源

- `cli_runner.on_segment` -> `codex_segment`
- `cli_runner.on_event` -> `codex_runtime_event`
- `FlowRuntime._supervisor_decide(...)` -> `supervisor_decided`
- `judge_attempt(...)` -> `judge_result`
- `apply_operator_action(...)` / `_consume_operator_action(...)` -> `operator_action_applied`
- `artifact.registered` trace / artifact write -> `artifact_registered`
- phase 切换写回 -> `phase_transition`
- flow shell start / completed / failed / interrupted -> `run_started / run_completed / run_failed / run_interrupted`

### 4.4 序列化要求

- 所有事件可序列化为 JSON line
- 不绑定 Textual 对象
- 未来 desktop/web/native shell 可直接复用

---

## 5. Slash Commands / Hooks / Permissions

### 5.1 Slash Commands

壳内固定支持：

- `/run`
- `/resume`
- `/status`
- `/list`
- `/preflight`
- `/pause`
- `/resume-run`
- `/retry-phase`
- `/abort`
- `/inspect`
- `/artifacts`
- `/help`

### 5.2 Lifecycle Hooks

内置 hooks 固定收口为：

- `on_launch`
- `on_run_started`
- `on_phase_transition`
- `on_judge_result`
- `on_operator_action`
- `on_run_finished`
- `on_interrupt`

当前阶段先做 **内置生命周期钩子面**，不急着开放插件式外部 hooks API。

### 5.3 Permissions / Approvals

以下动作必须二次确认：

- `abort`
- `retry_current_phase`
- `overwrite_resume`

所有 operator action 继续走现有：

- `action` CLI 合同
- `actions.jsonl`
- `last_operator_action`

不新增旁路行为。

---

## 6. 依赖与安装策略

### 6.1 依赖落位

- 新增独立 CLI 依赖清单：`requirements-cli.txt`
- `Textual` 作为 TUI 主依赖
- 不并入 `requirements-dev.txt`

### 6.2 安装路径

安装示例固定为：

```bash
./.venv/bin/pip install -r requirements-cli.txt
```

### 6.3 缺依赖时的行为

- `butler-flow tui`
  - 缺依赖 -> 报错并退出
- `butler-flow`（TTY + 无子命令）
  - 缺依赖 -> 给提示并回退 plain launcher

### 6.4 为什么不直接上 Rust / Node

当前仓库事实：

- 运行时真源与 `cli_runner` 已在 Python 中打通
- 当前仓库无 Rust CLI 基础设施
- 当前仓库无终端 React / Ink CLI 基础设施
- 若直接转 Rust / Node，会把本轮从“CLI 升级”放大为“runtime 架构迁移”

因此本轮裁决是：

`先做对产品结构，再考虑是否替换 UI runtime`

---

## 7. 实施阶段（决策完成版）

### Phase 1 — TUI 框架与入口

- 新增 `tui/` 目录与 Textual App 骨架
- 新增 `butler-flow tui`
- TTY + 无子命令默认进入 TUI
- `--json` / 非 TTY 保持纯文本
- 新增 `--plain`，强制退回当前文本路径

### Phase 2 — Launcher 主界面

- 历史 flow 不再常驻主视图，而是收进 `/history`
- `/settings` 单独进入整屏偏好面
- Action Bar
- 当前 focused flow 高亮默认项
- `run / resume / status / list / preflight` 快捷操作

### Phase 3 — Attached Run Screen

- 左栏：summary + phase step history
- transcript 流式显示 `on_segment`
- `on_event` 进入 system event rail
- transcript 可滚动
- 当前状态与历史步骤不再拆去独立 inspector pane

### Phase 4 — Operator Actions

- action bar 与快捷键
- `pause / resume / append_instruction / retry / abort`
- confirm dialog
- slash command 面联通相同行为

### Phase 5 — 响应式与回退

- 宽度与能力检测
- 自动降级到 tab / 单栏 / plain
- 终端 resize 兼容
- 缺依赖回退逻辑

### Phase 6 — 复用位预留

- `FlowUiEvent` JSON 化输出
- controller 不绑定 Textual
- 为 future native/Ink shell 或 desktop/web 消费预留接口

---

## 8. 验收标准

### 8.1 功能验收

1. `butler-flow` 在 TTY 默认进入 TUI
2. `butler-flow tui` 强制进入 TUI
3. `butler-flow run --plain` / `resume --plain` 保持旧行为
4. `--json` / 非 TTY 不进入 TUI
5. `Ctrl+C` 退出码为 `130`

### 8.2 事件与状态验收

- `FlowUiEvent` 输出完整，事件可序列化
- `turns.jsonl / actions.jsonl / artifacts.json` 继续兼容
- operator action 写入行为不改合同
- `workflow_state.json` 仍是一致的状态真源

### 8.3 视觉验收

- 3 秒内可定位：
  - `flow_id`
  - `phase`
  - `last judge`
  - `next action`
- transcript / system / judge 三层一眼可分
- 无花哨 ASCII、无彩虹色污染
- 小宽度下不布局破碎

### 8.4 回归验收

- `test_butler_flow.py`
- `test_butler_cli.py`
- `test_chat_cli_runner.py`
- `test_codex_provider_failover.py`

必要时补：

- TUI controller / event mapping 测试
- `--plain` / `tui` 路由测试

---

## 9. 文档回写要求

本计划落地后，至少同步回写：

- `00_当日总纲.md`
- `docs/README.md`
- `docs/project-map/03_truth_matrix.md`
- `docs/project-map/04_change_packets.md`

并明确文档关系：

- `04a` = 对标研究
- `04b` = V1 已落实现
- `04c` = 下一轮 CLI 升级主计划

---

## 10. 明确不做

- 不做 Rust / Node 重写
- 不嵌套 Codex / Claude 原生 TUI
- 不改变 `campaign/orchestrator` 真源
- 不破坏现有脚本化入口与 `--json` 行为
- 不把外部 vendor 术语直接写回 Butler 现役真源
