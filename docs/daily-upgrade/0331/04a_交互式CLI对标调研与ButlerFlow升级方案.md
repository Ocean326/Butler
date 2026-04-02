# 0331 Butler Flow CLI 交互式升级：对标调研与技术方案

日期：2026-03-31  
状态：调研结论 + 分阶段实施方案（未落代码）  
所属层级：L1 `Agent Execution Runtime` 产品面；与 `Product Surface`（Visual Console / Operator）可衔接但不互替  
关联：

- [00_当日总纲.md](./00_当日总纲.md)
- [02_前台WorkflowShell收口.md](./02_前台WorkflowShell收口.md)（现役 butler-flow 真源）
- [04_前台长Agent监督Workflow产品化草稿计划.md](./04_前台长Agent监督Workflow产品化草稿计划.md)（产品化主线，本文聚焦 CLI 技术壳）
- [01_Agent监管Codex实践_exec与resume.md](./01_Agent监管Codex实践_exec与resume.md)

## 改前四件事（执行协议）


| 项          | 内容                                                                                                                                                                                              |
| ---------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 目标功能       | 将当前以 `print + input()` 为主的 butler-flow launcher / 观测面，升级为接近 Copilot CLI / Cursor CLI / Codex CLI 的**可导航、可流式观测、可会话恢复**的交互式命令行体验，且**不破坏**既有 `run / resume / status / list / preflight` 与非 TTY 行为。 |
| 所属层级       | L1 前台附着执行运行时；状态仍落在本地 `butler_flow/<flow_id>/`，不进入 `campaign/orchestrator`。                                                                                                                      |
| 当前真源文档     | [02_前台WorkflowShell收口.md](./02_前台WorkflowShell收口.md)。                                                                                                                                           |
| 计划查看的代码与测试 | `butler_main/butler_flow/`（`cli.py`、`app.py`、`display.py`、`runtime.py`）、`butler_main/agents_os/execution/cli_runner.py`；回归以 `butler_main/butler_bot_code/tests/test_butler_flow.py` 等为主。        |


---

## 1. 对标对象：三家 CLI 的「交互式」共性

### 1.0 2026-03-31 外部 CLI 现状刷新

按 2026-03-31 重新核对官方资料，当前值得重点对标的 CLI 可分三类：

1. **官方且开源**
   - `OpenAI Codex CLI`：`openai/codex`，官方仓库直接定义为本地运行的 coding agent，仓库内同时暴露 CLI、Rust 核心与 SDK 结构，适合对标 **system CLI entry + local agent runtime + 多表面复用**。
   - `Google Gemini CLI`：`google-gemini/gemini-cli`，官方 README 直接定义为 **open-source AI agent**，并显式提供 `--output-format json / stream-json`、checkpointing、MCP、trusted folders，适合对标 **headless / event stream / safety rail**。
   - `Goose`：`block/goose`，官方 README 明确是 **local, extensible, open source AI agent**，强调任意 LLM、多模型配置、MCP 与 CLI/desktop 共存，适合对标 **provider-agnostic runtime + extension 面**。
2. **官方但当前不按开源主仓口径使用**
   - `Claude Code`：官方文档当前重点是 Terminal / IDE / Desktop / Web 多表面、MCP、hooks、custom commands、subagents、remote control。  
     截至 2026-03-31，我在官方文档与官方 GitHub 检索里**没有命中明确的官方开源主仓入口**；因此这里把它视为“**产品形态很值得对标，但当前不按开源项目处理**”。这是基于官方资料的**推断**。
3. **社区/创业项目，但终端产品感非常值得学**
   - `OpenCode`：当前仓库迁到 `anomalyco/opencode`，README 直接强调 **100% open source**、built-in `build/plan` agents、`@general` subagent、TUI focus、client/server architecture。
   - `aider`：仍是终端里成熟度很高的一类 open-source coding assistant，强项在 **repo map、git integration、lint/test 闭环、voice-to-code、IDE 内嵌**。

### 1.0.1 对 Butler 当前最有价值的不是“换模型”，而是“吸交互结构”

从这些 CLI 提炼，Butler 接下来最值得吸收的是：

1. 同一能力同时支持 `TTY / headless / structured events`
2. 终端主界面不是单栏 print，而是固定布局 + 状态区 + 操作区
3. 把 `session / checkpoint / resume` 做成一等对象，而不是帮助文案
4. 把 operator action 放进壳里，不要求用户记忆二级命令
5. CLI 与 desktop / web / remote control 复用同一 run/event schema

以下基于公开文档与社区材料整理，用于**能力分解**，不是实现抄袭；Butлер 侧约束是 **双 harness（Codex 主执行 + Cursor judge）** 与 **本地文件型状态机**，与任意单一厂商 CLI 都不一一同构。

### 1.1 能力矩阵（抽象维度）


| 维度   | GitHub Copilot CLI                 | Cursor CLI                | OpenAI Codex CLI                      | 对 Butler Flow 的启示                                                                      |
| ---- | ---------------------------------- | ------------------------- | ------------------------------------- | -------------------------------------------------------------------------------------- |
| 会话模型 | 交互会话 + 单次 `-p` 程序化                 | `agent` 交互；模式与参数          | 全功能 TUI 会话；`resume` 多形态               | 需要 **flow 级会话 id**（已有 `workflow_id` / `codex_session_id`）+ **统一「恢复最近」叙事**（已有 `--last`） |
| 呈现   | 终端内多轮对话与工具输出                       | 消息流、快捷键审阅 patch           | 流式输出 + 会话回放                           | 需 **可滚动日志区** + **当前 phase / judge 摘要区**（可选双栏）                                          |
| 模式   | Ask / Execute；Plan（如 Shift+Tab）    | Agent / Plan / Ask； slash | Slash 命令体系                            | Butler 已有 `single_goal` vs `project_loop`；可映射为「模式条」而非替换 vendor 内部模式                    |
| 人工门控 | 工具执行前确认（产品叙事）                      | 命令批准；Ctrl+R 审阅            | 对话内批准步进                               | judge 已存在；缺的是 **operator 在壳内的一条「暂停 / 注入指令 / 跳过本轮」** 的产品化通道（见第 5 节）                     |
| 恢复   | 会话延续（产品能力）                         | 可恢复对话                     | `resume` / picker / `--last`；TUI 降低闪屏 | launcher 可用 **可搜索列表 + 高亮** 对齐 picker 体验；**不必**自研分页 TUI 才能 MLP                          |
| 扩展   | `.github/extensions/`、JSON-RPC 子进程 | MCP、Rules、云 Agent handoff | MCP、skills                            | Butler 已处理 MCP guard、`codex_home` 隔离；交互壳应 **暴露同一 preflight 信息**                        |


### 1.2 架构层面的共性

1. **父进程编排 + 子能力进程**：Copilot CLI 明确有扩展子进程；Butler 已是 **Python 编排 + `cli_runner` 子进程**。
2. **TTY 检测**：交互模式仅在 `isatty` 时启用；你们已在 `cli.py` 对无子命令场景做 TTY 分支。
3. **程序化/CI 入口**：三家均保留「非交互、可脚本化」路径；Butler 必须保持 `--json`、管道、exit code 契约。

**结论**：Butler Flow 升级的重点不是「换一个 AI」，而是 **在现有编排外围增加一套合格的终端 UI 层（TUI 或强化的 Rich 半屏）**，并把 **流式事件、状态、恢复点** 从「混在一起打印」提升为「可扫视、可操作的布局」。

---

## 2. 现状与差距（相对上述共性）

当前实现要点（代码入口）：

- `butler_main/butler_flow/cli.py`：`argparse` + 无子命令且 TTY 时走 `FlowApp.launcher()`。
- `butler_main/butler_flow/app.py`：`launcher` 为 **while True + `input()` 菜单**；`FlowDisplay` 仅为 `write`/`write_json`（`butler_main/butler_flow/display.py`）。
- 子进程与 receipt：`cli_runner.run_prompt_receipt`；Codex 流式已有 `--no-stream` 等开关。

**主要差距**：

1. **无布局**：无固定头部（workspace / flow_id / phase）、无持久可见的「最近动作」区域。
2. **弱导航**：列表选择依赖数字 / 手输 id，缺少方向键、模糊搜、分页（Codex resume picker 级体验）。
3. **流式与 judge 交替可读性**：多轮循环时，操作者难以一眼区分「本轮 Codex 输出」「Cursor JSON 判定」「状态落盘」。
4. **嵌套 TTY 风险**：若在 Butler 内再拉起 **交互式** `codex` / `cursor` 全屏 TUI，会出现 **双层终端 UI、信号与 resize** 问题；当前主线是 `**exec` / 非交互 `resume**`，与「外包交互给厂商 CLI」路线冲突，需在方案里二选一或分层。

---

## 3. 技术路线选项（推荐组合）

### 方案 A — 「编排壳 + 半屏 Rich」（低风险增量）

**内容**：保留现有控制流；引入 `rich`（仓库若未锁依赖需评估）：

- `rich.console.Console` + `Live` / `Progress` 做 **状态条 + 近期日志窗口**（高度可配置）。
- `prompt_toolkit` 或 Rich 的 `Prompt` 做 **带历史的输入行**（可选）。
- launcher 改为 **单次清屏分段渲染** 或 **底部固定 input 的简化 layout**，不强制全屏。

**优点**：与现有 `FlowDisplay` 渐进融合；易测（仍可向 `StringIO` 打桩）；Windows/SSH 兼容性通常好于重度全屏 TUI。  
**缺点**：达不到 Codex 原生 TUI 的「应用感」；复杂布局维护成本上来后可能再迁 Textual。

**适用阶段**：**MVP / 第一期**。

### 方案 B — 全屏 TUI：**Textual**（Python 主线推荐）

**内容**：用 [Textual](https://github.com/Textualize/textual)（基于 Rich）实现：

- **左侧**：flow 列表 / 筛选（对齐 `list` + `resume` picker）。
- **中部**：聚合日志（Codex stdout 分块、judge 摘要、状态迁移）。
- **底部**：命令面板（run / resume / inject operator note / quit）；快捷键绑定。
- **与业务层**：`FlowApp` 拆为 **纯逻辑 API**（无 `input`）+ `TextualFlowApp` 仅负责视图与事件。

**优点**：结构化组件、可维护；与「类 IDE CLI」心智接近。  
**缺点**：学习曲线；全屏在部分终端 / CI 需 **自动降级** 到方案 A 或纯 argparse。

**适用阶段**：**第二期**（API 稳定后）。

### 方案 C — prompt_toolkit 全屏应用

**内容**：低层布局与 key binding 完全自控。

**优点**：极大灵活。  
**缺点**：工程量大；与 Textual 重叠。仅当已有 prompt_toolkit 重度经验或需嵌入 REPL 时考虑。

### 方案 D — 不嵌套厂商 TUI：坚持「Butler Own UI + 子进程机器可解析输出」

**内容**：不在 Butler 内长期附着交互式 `codex` TUI；继续 `exec`/`resume` 结构化消费；若用户要「纯 Codex 手感」，文档引导 **直接开 `codex**`，Butler 只负责 **会话外监督**（与当前架构一致）。

**优点**：避免 PTY 地狱。  
**缺点**：「一个窗口搞定一切」的产品叙事弱化。

**结论**：**默认采用 D 的进程模型 + A 或 B 的呈现**。不在第一优先级做「Butler 里再嵌一个完整 Codex TUI」。

---

## 4. 与多厂商（Copilot / Cursor / Codex）对齐策略

Butler Flow **当前**硬绑定：**Codex 执行 + Cursor judge**（见 `runtime.py` 报错信息与 `prompts.py`）。「各家 CLI」在路线图里应理解为：


| 角色          | 短期（建议）                               | 中期                                                                |
| ----------- | ------------------------------------ | ----------------------------------------------------------------- |
| Codex       | 主执行唯一真源保持不变                          | 若引入 Copilot CLI，仅当 **cli_runner 抽象** 能输出统一 `ExecutionReceipt` 再挂接 |
| Cursor      | judge 真源保持不变                         | 同上，统一 receipt                                                     |
| Copilot CLI | 不作为第一里程碑；_NODE 依赖与认证链路与现有 Python 栈隔离 | 若接入，建议 **独立 adapter 进程**（JSON-RPC/stdio）与 A/B 壳通信，避免把 Node 绑进核心循环 |


**交互壳本身的厂商无关性**：壳只消费 **结构化事件**（phase、attempt、receipt 字段、流式 chunk），底层 provider 可通过 `cli_runner` 扩展。

## 4.1 对标结论：当前应优先学谁

若按“短期可落地价值 / 对 Butler 现状的贴合度”排序，建议是：

1. **Codex CLI**
   - 当前本来就以 Codex 为主执行。
   - 要学的是 `resume picker`、structured events、命令面统一、TTY 一致性。
2. **Claude Code**
   - 当前最强的是 **多表面统一引擎** 和 **MCP + hooks + commands + subagents + remote control** 的产品收口。
   - 要学的是“同一引擎，多壳复用”，不是照搬其闭源实现。
3. **OpenCode**
   - 最接近“开源版 Claude Code 体验”。
   - 要学的是 **TUI 形态** 和 **client/server 兼容位**。
4. **Gemini CLI**
   - 适合对标 `json / stream-json / checkpointing / trusted folders / MCP` 这一组 automation 能力。
5. **aider / goose**
   - aider 适合吸 **git / lint / test / review 节奏**。
   - goose 适合吸 **provider-agnostic runtime + extension/distribution**。

---

## 5. 分阶段实施计划（可直接排期）

### 5.0 总裁决

当前不建议把 Butler Flow 升级理解成“做一个更花的 launcher”，而应理解成：

`system CLI entry -> stable event spine -> operator TUI shell -> optional remote/desktop reuse`

也就是先把 **系统级 CLI 入口**、**run/event schema**、**TTY operator shell** 打稳，再考虑更大产品面。

### 阶段 0：契约冻结（1–2 天）

- 冻结 **非 TTY** 行为：`--json`、exit code、`test_butler_flow` 覆盖。
- 在 `02_...` 或本文补充：**交互模式能力边界**（不承诺嵌套 vendor TUI）。
- 冻结 `run / resume / status / list / preflight / action` 的系统级入口叙事：`butler-flow` 为唯一主命令。
- 冻结事件骨架：至少统一 `run_started / phase_changed / assistant_chunk / judge_result / operator_action / run_finished / interrupted`。

### 阶段 1：呈现层抽象（3–5 天）

- 从 `FlowDisplay` 抽出接口：`status_line`、`event_stream`、`confirm`、`choose_flow`。
- 默认实现保留 **现状**（字符流）；新增 `RichFlowDisplay`（方案 A）可选 `--rich` 或自动 TTY 探测。
- 所有 display 更新都只消费结构化事件，不直接读业务对象，避免后面切 Textual / desktop 时重写 runtime。

### 阶段 2：Launcher 体验（3–7 天）

- 最近 flow：`Inquirer`/自研 数字选择 + **默认项高亮**（已有 default_action，可扩展到视觉）。
- `resume`：可选「仅显示 in_progress / interrupted」过滤（需状态字段约定）。
- 集成 **只读** `tail` 最近 trace 文件摘要（若已有 trace_store API）。
- 增加 `quick actions`：最近一条 flow 可直接 `resume / status / retry_current_phase / append_instruction`，减少重新选项跳转。

### 阶段 3：运行中观测（5–10 天）

- `FlowRuntime` 循环内向 display 推送 **类型化事件**（`codex_chunk`、`judge_result`、`phase_transition`）。
- Rich `Live` 或 Textual 单屏 **多 Panel**；支持 `**--no-ui` 或环境变量** 回退当前简单打印（CI）。
- 增加固定 `status rail`：`flow_id / phase / attempt / provider / last judge / last operator action / session id`。
- 把流式正文区和系统事件区分栏，避免现在 Codex 输出、judge 摘要、状态落盘混在一起。

### 阶段 4：Operator 介入（与 04 产品稿对齐）

- 壳内快捷键：`p` pause（协作信号写入本地 state 或 watchdog）、`m` 附加 operator message 进入下一轮 prompt 前缀。
- 与 [04_前台长Agent监督Workflow产品化草稿计划.md](./04_前台长Agent监督Workflow产品化草稿计划.md) 中的 `thread/turn/item` 对齐时，事件模型应 **可序列化**，便于日后升到 Console。
- 增加 `approve / reject / recover / open artifact / copy command` 这类 operator verbs，对齐 Claude Code / OpenCode 那种“壳内完成主要人工决策”的体验。

### 阶段 5（可选）：Textual 全屏应用

- 新入口：`butler-flow tui` 或 TTY 自动升级；保持 `butler-flow run ...` 脚本兼容。
- 若做到这步，应同时预留 **headless server/client** 兼容位，避免把 Textual 绑定成唯一壳。

---

## 6. 风险与对策


| 风险                  | 对策                                                                   |
| ------------------- | -------------------------------------------------------------------- |
| 依赖膨胀                | Rich/Textual 可选 extra：`pip install butler[flow-tui]` 或文档说明           |
| Windows / 非 ANSI 终端 | 能力探测失败则降级为朴素 `print`                                                 |
| 嵌套 TUI / 伪终端        | 坚持方案 D；文档写清                                                          |
| 测试不稳定               | 视图与逻辑分离；核心逻辑仍无 TTY 单测                                                |
| 与 Visual Console 重复 | CLI 面向「附着终端的 operator」；Console 面向浏览器；共享 **同一事件 JSON schema** 作为长期收敛点 |


---

## 7. 参考链接（外部）

- [OpenAI Codex GitHub](https://github.com/openai/codex)
- [Claude Code Overview](https://code.claude.com/docs/en/overview)
- [Google Gemini CLI GitHub](https://github.com/google-gemini/gemini-cli)
- [OpenCode GitHub](https://github.com/anomalyco/opencode)
- [Goose GitHub](https://github.com/block/goose)
- [aider GitHub](https://github.com/Aider-AI/aider)
- [About GitHub Copilot CLI](https://docs.github.com/en/copilot/concepts/agents/about-copilot-cli)
- [Cursor CLI 概览](https://cursor.com/docs/cli/overview) 与 [Using Agent in CLI](https://cursor.com/docs/cli/using)

---

## 8. 验收建议（CLI 侧）

1. **TTY**：launcher 在无子命令时可操作、可 `q` 退出；窗口缩放不崩溃（Textual 阶段）。
2. **非 TTY**：行为与当前一致；`--json` 输出稳定。
3. **长任务**：`project_loop` 至少 **10 轮** 仍可扫视当前 phase 与最近 judge 结论。
4. **恢复**：`resume --last` 与壳内选最近一条 **指向同一 flow**。

---

## 与 `04`_ 产品化计划的关系

- **04** 讲的是前台长 workflow **产品主线与 harness 边界**。
- **04a（本文）** 只解决 **终端交互壳与多厂商对齐的技术选型**，不升格后台 campaign，也不替代 `02_` 现役语义。
- 若阶段 4 的 operator 介入与事件 schema 落地，应回写 `04_` 与 `project-map`（届时另开变更批次，遵守仓库文档回写协议）。
