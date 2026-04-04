# Test Cases: Butler Flow Desktop Thread Workbench

## Overview

- Feature: `butler_flow Desktop` 线程化单流工作台
- Requirements Source: 用户确认的产品方向 + `Manager -> Supervisor -> Agent focus` 流程要求 + 本轮实现的 thread-first desktop bridge / renderer
- Test Coverage: 覆盖 Manager 默认入口、History、New Flow、Templates、Supervisor stream、Agent focus、日夜主题、配置接入、operator action、错误与状态迁移
- Last Updated: 2026-04-05

## Test Case Categories

### 1. Functional Tests

#### TC-F-001: Config attach 后默认进入 Manager
- Requirement: Desktop 首屏必须先接入 config，然后默认展示 `Manager 管理台`
- Priority: High
- Preconditions:
  - Desktop 已启动
  - 可访问有效 `butler_bot.json`
- Test Steps:
  1. 在空态点击 `Select Config` 或手填 `Config Path Fallback`
  2. 完成 config attach
  3. 等待 thread-home 与 manager-thread 首次加载
- Expected Results:
  - 页面进入 `Manager 管理台`
  - 左 rail 显示 `Manager / History / New Flow / Templates`
  - Recent Threads 出现已持久化 manager / flow thread
- Postconditions: 当前 config path 已缓存到本地存储

#### TC-F-002: Manager 对话可继续 existing session
- Requirement: 现有 manager session 应以 thread 方式恢复
- Priority: High
- Preconditions:
  - 已存在 `manage_session`
  - `manager-thread` payload 可返回 blocks
- Test Steps:
  1. 打开 Desktop
  2. 进入 `Manager 管理台`
  3. 观察 thread 标题、stage 与 block 列表
- Expected Results:
  - session 对应的 `idea / requirements / team_draft / launch` block 被渲染
  - 当前 `manager_stage` 与 `pending_action` 状态可见
  - 若存在 linked flow，则出现打开 Supervisor 的动作入口
- Postconditions: 无

#### TC-F-003: New Flow 从空白 Manager thread 开始
- Requirement: `New Flow` 是一个空白 Manager 入口，而不是单独的旧分栏页面
- Priority: High
- Preconditions:
  - Desktop 已 attach config
- Test Steps:
  1. 点击左 rail 的 `New Flow 新建`
  2. 观察主区内容
  3. 输入一条新需求并发送到 Manager
- Expected Results:
  - 主区显示 starter blocks
  - 首次发送后创建新的 `manager_session_id`
  - 页面回到真实 manager thread，而不是停留在假空页
- Postconditions: 新 manager session 已落盘

#### TC-F-004: Manager 确认后自动切到 Supervisor
- Requirement: 对用户来说创建前始终面对 Manager；确认创建后自动进入 Supervisor 流
- Priority: High
- Preconditions:
  - manager thread 已进入可提交状态
  - `manager-message` 可触发 `manage_flow`
- Test Steps:
  1. 在 manager composer 中发送确认创建的消息
  2. 等待 bridge 完成 `manage_chat -> manage_flow`
- Expected Results:
  - `manager_session` 被同步到真实 `instance:<flow_id>`
  - pending action 被清理
  - 主区自动切换到对应 `Supervisor` page
- Postconditions: 新 flow instance 已创建，Supervisor page 可访问

#### TC-F-005: Supervisor stream 可打开 Agent focus
- Requirement: 用户可从 Supervisor 流点击 team 中的 agent，进入单 agent 流页
- Priority: High
- Preconditions:
  - supervisor-thread payload 带 role chips 或带 `role:*` action target
- Test Steps:
  1. 打开一个 Supervisor page
  2. 点击某个 role chip 或 block 上的 `Open Agent`
- Expected Results:
  - 页面切换到对应 `Agent Focus`
  - Agent page 展示 role brief、progress、artifact / handoff blocks
  - 可以返回 Supervisor
- Postconditions: 无

#### TC-F-006: Templates 以单流方式展示 template + team
- Requirement: `Templates` 页面负责 template 模板与 agent team 管理，不再走旧 manage detail layout
- Priority: Medium
- Preconditions:
  - workspace 中存在 builtin/template assets
- Test Steps:
  1. 点击 `Templates 模板`
  2. 切换不同 asset pill
  3. 查看 overview / team / standards blocks
- Expected Results:
  - 页面为单流卡片堆栈
  - 选中 asset 的 `role_guidance / review_checklist / manager_notes` 被展示
  - 不出现旧双栏 manage detail 壳
- Postconditions: 无

### 2. Edge Case Tests

#### TC-E-001: 无 manager session 时的 Manager 空态
- Requirement: 没有历史 session 时也必须有可用的 Manager 起点
- Priority: Medium
- Preconditions:
  - `manage_sessions/` 为空
- Test Steps:
  1. attach config
  2. 打开 `Manager 管理台`
- Expected Results:
  - 展示 starter blocks
  - `manager-thread` 返回 draft 状态
  - composer 可正常发送首条消息
- Postconditions: 无

#### TC-E-002: 无 templates 时的 Templates 空态
- Requirement: 没有 template 资产时页面仍应可理解
- Priority: Medium
- Preconditions:
  - asset list 为空
- Test Steps:
  1. 打开 `Templates 模板`
- Expected Results:
  - 页面显示 overview / empty guidance
  - 不崩溃，不报未定义字段错误
- Postconditions: 无

#### TC-E-003: Agent page 在 role 无专属 timeline 时仍有最小可读内容
- Requirement: agent focus 至少应显示 role brief，不可完全空白
- Priority: Medium
- Preconditions:
  - role 存在，但无显式 role-specific timeline
- Test Steps:
  1. 从 Supervisor 打开该 role
- Expected Results:
  - `role_brief` block 仍存在
  - 允许展示 flow-level artifact 作为最小上下文
- Postconditions: 无

### 3. Error Handling Tests

#### TC-ERR-001: 无效 config path
- Requirement: 手填无效路径时必须给出错误提示
- Priority: High
- Preconditions:
  - Desktop 已启动
- Test Steps:
  1. 在 `Config Path Fallback` 输入无效路径
  2. 点击 `Attach`
- Expected Results:
  - 展示错误 toast 或 load failure
  - 不进入半初始化状态
- Postconditions: 无

#### TC-ERR-002: Thread bridge 任一 payload 加载失败
- Requirement: `thread-home / manager-thread / supervisor-thread / template-team / agent-focus` 任一失败时，要有显式错误提示
- Priority: High
- Preconditions:
  - 桥接命令返回异常
- Test Steps:
  1. 让某个 payload 请求抛错
  2. 观察页面反馈
- Expected Results:
  - 对应 error toast 出现
  - 其他已可见区域不应整体白屏
- Postconditions: 无

#### TC-ERR-003: Manager message 执行失败
- Requirement: Manager send 失败时必须保持当前 thread，不得错误跳转
- Priority: High
- Preconditions:
  - `manager-message` 命令返回异常
- Test Steps:
  1. 在 manager composer 发送消息
  2. 让 bridge 报错
- Expected Results:
  - 显示 `Manager message failed`
  - composer 保留当前上下文
  - 不切到 Supervisor
- Postconditions: 无

### 4. State Transition Tests

#### TC-ST-001: Rail section 与 view 状态联动
- Requirement: `Manager / History / New Flow / Templates` 是 rail section；Supervisor / Agent 是主区 thread 状态
- Priority: High
- Preconditions:
  - Desktop 已 attach config
- Test Steps:
  1. 从 `Manager` 打开一个 Supervisor
  2. 再从 Supervisor 打开 Agent
  3. 回退到 Supervisor，再切到 Templates
- Expected Results:
  - rail section 保持当前入口语义
  - main view 在 `manager -> supervisor -> agent -> templates` 之间正确切换
  - 不出现旧 detail drawer/双栏残留
- Postconditions: 无

#### TC-ST-002: 日夜主题切换持久化
- Requirement: 支持 Day / Night theme 且切换结果可持久化
- Priority: Medium
- Preconditions:
  - Desktop 已启动
- Test Steps:
  1. 点击主题切换按钮
  2. 刷新或重新打开页面
- Expected Results:
  - 主题 token 切换成功
  - localStorage 中保留最近主题
  - 重新打开后沿用上次主题
- Postconditions: 主题偏好被保存

#### TC-ST-003: Operator action 后 Supervisor stream 刷新
- Requirement: Pause / Resume / Retry Phase 会通过 bridge 写回 runtime，并刷新 thread 页面
- Priority: Medium
- Preconditions:
  - 当前位于 Supervisor page
  - flow action 可执行
- Test Steps:
  1. 点击 `Pause`
  2. 点击 `Resume`
  3. 点击 `Retry Phase`
- Expected Results:
  - 对应 action payload 被发出
  - 成功 toast 展示 action type
  - thread queries 被刷新
- Postconditions: flow runtime 状态已更新

## Test Coverage Matrix

| Requirement ID | Test Cases | Coverage Status |
|---|---|---|
| REQ-001 Manager 默认入口 | TC-F-001, TC-F-002, TC-E-001 | ✓ Complete |
| REQ-002 New Flow 作为空白 Manager 入口 | TC-F-003 | ✓ Complete |
| REQ-003 Manager -> Supervisor 自动串联 | TC-F-004, TC-ERR-003 | ✓ Complete |
| REQ-004 Supervisor -> Agent focus | TC-F-005, TC-E-003 | ✓ Complete |
| REQ-005 Templates 单流模板/team 管理 | TC-F-006, TC-E-002 | ✓ Complete |
| REQ-006 thread bridge 错误与页面稳定性 | TC-ERR-001, TC-ERR-002 | ✓ Complete |
| REQ-007 rail/main 状态转换 | TC-ST-001 | ✓ Complete |
| REQ-008 day/night theme | TC-ST-002 | ✓ Complete |
| REQ-009 operator action 刷新链路 | TC-ST-003 | ✓ Complete |

## Notes

- 当前 Desktop 真实 Manager 交互依赖 `Codex CLI` 可用；若 CLI 不可用，需要额外验证错误透传与降级提示。
- `.superpowers/` 视觉草稿不是正式资产，不纳入本测试范围。
- 若后续补 Playwright e2e，建议优先把 `TC-F-001 / TC-F-004 / TC-F-005 / TC-ST-002` 变成桌面点击回归。
