# 0405 Butler Flow Desktop 线程化工作台与 Manager-Supervisor 串联落地

日期：2026-04-05
状态：已落代码 / 已验收 / 当前真源
所属层级：L1 `Agent Execution Runtime`

## 1. 本轮目标

把 Butler Flow Desktop 从“可编译的 bridge 壳”继续推进到“可按产品主线使用的 thread-first workbench”，并明确以下产品裁决已经进入现役：

1. 对用户来说，创建前只面对 `Manager`
2. 左 rail 固定保留 `Manager / History / New Flow / Templates`
3. 主区不再保留旧 detail drawer / 双栏；全部页面统一为单流卡片堆栈
4. `History` 按 `Project Thread` 理解 manager session 与 supervisor flow
5. `Templates` 页面负责 `template + agent team` 管理
6. `Manager -> Supervisor -> Agent focus` 必须串起来，而不是停留在只读 UI 原型
7. 视觉基线以冷白 / 蓝灰日间模式和蓝黑夜间模式为准，不再沿用暖色方案
8. 视觉壳层对齐 Codex 交互壳，但 Butler 语义、线程命名与入口概念保持不改名

## 2. 一句话裁决

当前 Butler Flow Desktop 的现役 shared surface 与 renderer 心智更新为：

> **`thread-home / manager-thread / supervisor-thread / agent-focus / template-team / manager-message` 组成 thread-first Desktop contract，用户默认从 `Manager` 进入，在同一条 thread 上继续切到 `Supervisor` 与 `Agent focus`。**

## 3. 代码侧落点

### 3.1 Python state / surface

新增与升级：

- `butler_main/products/butler_flow/state.py`
  - 新增 `read_jsonl()`
  - 新增 `read_manage_turns()`
  - 新增 `list_manage_sessions()`
- `butler_main/products/butler_flow/surface/dto.py`
  - 新增 `ThreadBlockDTO`
  - 新增 `ThreadSummaryDTO`
  - 新增 `ThreadHomeDTO`
  - 新增 `ManagerThreadDTO`
  - 新增 `SupervisorThreadDTO`
  - 新增 `AgentFocusDTO`
  - 新增 `TemplateTeamDTO`
- `butler_main/products/butler_flow/surface/service.py`
  - 新增 `thread_home_payload()`
  - 新增 `manager_thread_payload()`
  - 新增 `supervisor_thread_payload()`
  - 新增 `agent_focus_payload()`
  - 新增 `template_team_payload()`
  - 把 manager / supervisor / agent / template 全部投影到统一 block schema

### 3.2 Python Desktop bridge

`butler_main/products/butler_flow/desktop_bridge.py` 新增：

- `thread-home`
- `manager-thread`
- `supervisor-thread`
- `agent-focus`
- `template-team`
- `manager-message`

其中 `manager-message` 当前不是只读桥：

- 先执行 `manage_chat`
- 若返回 `action=manage_flow + action_ready=true`
- 则自动继续执行 `manage_flow`
- 成功后同步更新 `manager_session / draft / pending_action`
- 再把 Desktop 主区切到对应 `Supervisor` flow

因此当前产品上对用户已经成立：

- 创建前只面对 `Manager`
- 一旦进入创建确认，Desktop 会自动把 thread 从 `Manager` 切到 `Supervisor`

### 3.3 Desktop renderer

`butler_main/products/butler_flow/desktop/src/renderer/App.tsx` 已整体改成 thread-first shell：

- rail：
  - `Manager 管理台`
  - `History 历史`
  - `New Flow 新建`
  - `Templates 模板`
  - `Recent Threads`
- 主区：
  - `Manager` page：thread blocks + composer
  - `History` page：Project Threads 列表
  - `Supervisor` page：summary + role chips + action strip + stream blocks
  - `Agent focus` page：focused agent stream
  - `Templates` page：asset pills + overview/team/standards stream
- 状态：
  - `config path` 本地持久化
  - `day/night theme` 本地持久化
  - `manager message` 发送后自动刷新 thread queries
  - `bridge missing` 显式降级为空页面态，不在纯浏览器环境抛 preload/query 风暴

### 3.4 0405 第二波：视觉壳升级与线程合同补齐

本轮又把 thread-first Desktop 从“已经可用”继续推进到“视觉与交互壳对齐 Codex，但仍保留 Butler 语义”的完成态：

- `App.tsx + workbench.css`
  - 左 rail 收窄，统一冷色 card / rail token
  - `Manager / New Flow` 改成 `thread stream + bottom dock composer`
  - composer 默认小，输入增长后最多占视口 `1/3`
  - `night` 改成默认主题
- `History / Recent Threads`
  - `thread-home` 现役合同改成同时保留 linked `manager` 与 `supervisor` 两类 thread
  - renderer 改成按 `thread_kind` 判别 thread 身份，不再用 `flow_id` 猜测 manager/supervisor
  - 从 `History/Recent Threads -> Supervisor -> Manager` 时，会同步 `manager_session_id`，避免上下文漂移
- `bridge fallback`
  - 当 `window.butlerDesktop` 未注入时，Desktop 显示 `Desktop bridge 未连接`
  - 所有 thread query 都以 bridge availability 控制 `enabled/refetch`
- mock / test fixtures
  - mock adapter 新增第二条 flow / manager session，用来覆盖线程 round-trip
  - alternate flow 的 `Agent Focus` 现已按 `flowId` 返回正确上下文，而不是错误落回主 flow

## 4. 产品口径更新

### 4.1 Manager 是唯一创建前入口

`New Flow` 不再是另一套旧页面，只是一个空白 Manager thread。
实际首轮输入仍然走 `manager-message`，并由 manager session 落盘到：

- `manage_sessions/<manager_session_id>/session.json`
- `draft.json`
- `turns.jsonl`
- `pending_action.json`

### 4.2 Supervisor 与 Agent 是同一 thread 的运行视图

`Supervisor` 页面以 flow timeline 为真源。
点击 role chip 或 block 内 `role:*` action target 时，进入 `Agent focus`。

当前裁决：

- Agent 不是单独历史线程
- Agent 是同一 flow thread 内的 focused stream

### 4.2.1 History 是 project thread list，而不是单一 manager 索引

0405 第二波后，`thread-home` 的现役裁决进一步明确为：

- launched manager session 仍保留一条 `manager` thread summary
- linked flow 也保留一条 `supervisor` thread summary
- 两者都可出现在 `History / Recent Threads`
- renderer 必须按 `thread_kind` 决定打开 `Manager` 还是 `Supervisor`
- supervisor summary 若带有 `manager_session_id`，则返回 `Manager` 时要回到对应 session，而不是默认 manager

### 4.3 Templates 回到 thread 风格而非旧 manage detail

`Templates` 页面当前只保留 thread-like 单流展示：

- `overview`
- `team`
- `default_standards`

其目标是承载 `template + agent team`，而不是回到旧 `manage center detail` 双栏心智。

## 5. 视觉裁决

当前现役视觉方向更新为：

- 日间：
  - 冷白背景
  - 蓝灰边界
  - 轻玻璃化 rail / cards
- 夜间：
  - 蓝黑背景
  - 冷蓝 accent
  - 保持同一信息层级，不做另一套布局
- 不再沿用暖色 beige / copper 路线
- 主区统一单流；不再把细节塞进常驻右侧抽屉
- `Manager / New Flow` 的 composer 是页面底部 dock，而不是并列 side panel
- `Agent Focus` 是 full-thread role lens，不是 drawer/detail pane

## 6. 测试与验证

### 6.1 Python 回归

- `./.venv/bin/python -m pytest butler_main/butler_bot_code/tests/test_butler_flow_surface.py -q`
  - 当前结果：`10 passed`
  - 新增覆盖：
    - `thread-home`
    - `manager-thread`
    - `supervisor-thread`
    - `agent-focus`
    - linked flow 同时保留 `manager + supervisor` 双 thread summary
- `./.venv/bin/python -m pytest butler_main/butler_bot_code/tests/test_butler_flow_desktop_bridge.py -q`
  - 当前结果：`4 passed`
  - 新增覆盖：
    - `thread-home`
    - `manager-thread`
    - `supervisor-thread`
    - bridge CLI 输出 linked flow 的双 thread history 合同

### 6.2 Desktop 工程验证

- `cd butler_main/products/butler_flow/desktop && npm run typecheck`
  - 当前结果：通过
- `cd butler_main/products/butler_flow/desktop && npm run test:renderer`
  - 当前结果：`14 passed`
  - 覆盖：
    - bridge missing fallback
    - config attach / Manager 默认页
    - `New Flow` 空白 manager thread
    - manager launch -> supervisor
    - `History` project threads
    - launched manager row 即使带 `flow_id` 也仍打开 Manager
    - theme 持久化
    - composer 结构与高度上限
    - secondary flow 上下文 round-trip
    - mock adapter alternate-flow agent focus
- `cd butler_main/products/butler_flow/desktop && npm run build`
  - 当前结果：通过
- `cd butler_main/products/butler_flow/desktop && npm run test:e2e`
  - 当前结果：脚本级阻塞
  - 原因：当前主机没有 `DISPLAY`，也没有 `xvfb-run / Xvfb`
  - 结论：本轮不能把 Electron 点击回归记成“已通过”，只能记成“已尝试但受环境阻塞”

### 6.3 测试用例文档

已新增：

- `butler_main/butler_bot_code/tests/butler_flow_desktop_visual_shell_test_cases.md`

其中覆盖：

- Functional
- Edge
- Error handling
- State transition

## 7. 当前风险

当前仍保留以下边界：

1. `manager-message` 的真实执行仍依赖本机 `Codex CLI` 可用
2. Electron e2e 当前受本机图形环境阻塞，尚未拿到真实窗口层通过证据
3. 本轮 renderer tests 虽已补更多结构/状态回归，但几何视觉仍主要依赖 Electron 层确认
4. 工作区当前存在与本轮无关的旧脏改动：
   - `.superpowers/`
   - 根 `package-lock.json`
   - Desktop `package.json/package-lock.json` 的 Electron 版本改动并非本轮主目标

因此当前收口裁决是：

- 可以对本轮 thread-first Desktop 功能做代码级验收
- 但在 git 收口时不能盲目把所有脏改动一起打包

## 8. 现役结论

从 `2026-04-05` 起，Butler Flow Desktop 的现役真源更新为：

- 主对象：`Manager thread / Supervisor thread / Agent focus / Template team`
- 主桥接：`desktop_bridge.py` 的 thread-first commands
- 主 UI：左 rail 固定入口 + 主区单流卡片堆栈
- 创建链路：`Manager -> manage_flow -> Supervisor`
- 继续工作链路：`Supervisor -> Agent focus`

旧 `workspace/manage/flow/detail drawer` Desktop 心智降为历史实现背景，不再作为当前产品面的首真源。
