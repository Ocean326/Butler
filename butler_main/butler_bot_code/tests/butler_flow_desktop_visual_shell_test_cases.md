# Test Cases: Butler Flow Desktop Visual Shell Upgrade

## Overview

- Feature: `Butler Flow Desktop` Codex 气质视觉壳升级
- Requirements Source: 已确认的视觉升级设计稿 + 本轮 renderer / mock adapter / Electron e2e 实现
- Test Coverage: 覆盖 Butler-native thread 工作台、Codex 风格桌面壳、Manager/New Flow 底部 dock composer、History/Recent Thread 上下文回跳、Agent Focus role lens、Templates、主题、桥接异常、配置接入和状态迁移
- Last Updated: 2026-04-05

## Test Case Categories

### 1. Functional Tests

#### TC-F-001: Attach Config 后默认进入 Butler Manager thread
- Requirement: Desktop 首屏先接入 config，默认进入 `Manager 管理台`
- Priority: High
- Preconditions:
  - Desktop 已启动
  - 有效 `butler_bot.json` 可访问
- Test Steps:
  1. 通过 `Select Config` 或 `Config Path Fallback` 接入 config
  2. 等待 `thread-home` 与 `manager-thread` 加载完成
- Expected Results:
  - 主区进入 `Desktop 线程工作台`
  - 左 rail 保留 `Manager / Threads 历史 / New Flow / Templates`
  - `Manager` 的 docked composer 可见
- Postconditions: 最近使用的 config path 被缓存

#### TC-F-002: New Flow 从空白 manager thread 开始
- Requirement: `New Flow` 必须是空白 manager thread，而不是旧的单独功能页
- Priority: High
- Preconditions:
  - 已接入有效 config
- Test Steps:
  1. 点击 `New Flow 新建`
  2. 观察主区标题与 starter 内容
  3. 在 `Start with Manager` 输入第一条消息并发送
- Expected Results:
  - 主区显示 `新建 Flow`
  - composer 目标是 `Blank manager thread`
  - 第一次发送使用 `manageTarget=new`
- Postconditions: 新 manager session 已创建

#### TC-F-003: Manager 确认后自动进入 Supervisor thread
- Requirement: 对用户来说，创建前始终面对 Manager；确认创建后自动切入 Supervisor
- Priority: High
- Preconditions:
  - Manager thread 已就绪
- Test Steps:
  1. 在 Manager composer 发送确认创建 flow 的消息
  2. 等待 `manager-message -> manage_flow`
- Expected Results:
  - `manager_session_id` 被同步
  - 页面跳转到 Supervisor thread
  - `Pause / Resume / Retry Phase` 操作条可见
- Postconditions: flow instance 已创建

#### TC-F-004: History 中选择 Supervisor thread 后，返回 Manager 仍回到对应上下文
- Requirement: `History/Recent Thread -> Supervisor -> Manager` 必须保持 manager context 不漂移
- Priority: High
- Preconditions:
  - 存在至少两个不同 `manager_session_id`
  - 各自关联不同 flow thread
- Test Steps:
  1. 打开 `Threads 历史`
  2. 选择另一个 supervisor thread
  3. 再点击左 rail 的 `Manager 管理台`
- Expected Results:
  - 进入的 Supervisor 对应正确 flow
  - 返回 Manager 后显示与该 flow 绑定的 manager thread
  - 不会回到先前默认 manager session
- Postconditions: 当前 manager context 与当前项目线程一致

#### TC-F-005: Agent Focus 表现为 role lens，而不是 detail drawer
- Requirement: `Agent Focus` 是单个 role 的完整线程聚焦页
- Priority: High
- Preconditions:
  - Supervisor thread 含 role chip 或 `role:*` action target
- Test Steps:
  1. 打开任一 Supervisor thread
  2. 点击某个 role chip 或 `Open Agent`
- Expected Results:
  - 页面切换到该 role 的完整聚焦页
  - 顶部存在 `Back to Supervisor`
  - 主区仍是 thread 风格流式内容，不是侧栏/抽屉
- Postconditions: 可无损返回 Supervisor

#### TC-F-006: Templates 使用同一视觉系统表达 template team
- Requirement: `Templates` 页要属于同一工作台视觉系统，而不是旧后台壳
- Priority: Medium
- Preconditions:
  - 至少存在一个 template asset
- Test Steps:
  1. 点击 `Templates 模板`
  2. 切换不同 asset pill
  3. 查看 blocks 与说明
- Expected Results:
  - 页面进入统一 thread/page shell
  - `overview / team / standards` 等 block 可见
  - 视觉上不退回旧 `manage detail` 双栏心智
- Postconditions: 当前 template asset 选择状态已更新

#### TC-F-007: Day/Night 主题切换并持久化
- Requirement: 双主题都成立，且切换结果持久化
- Priority: Medium
- Preconditions:
  - Desktop 已 attach config
- Test Steps:
  1. 点击顶部主题按钮
  2. 刷新页面或重开应用
- Expected Results:
  - `data-theme` 从 `night` 切到 `day` 或反向切换
  - localStorage 中保留最近选择
  - 重开后保持上次主题
- Postconditions: 主题偏好已保存

### 2. Edge Case Tests

#### TC-E-001: 无历史 session 时仍能从 Butler Manager 起步
- Requirement: 空工作区也必须可从 Manager 正常开始
- Priority: Medium
- Preconditions:
  - `manage_sessions` 为空
- Test Steps:
  1. attach config
  2. 进入 `Manager 管理台`
- Expected Results:
  - 展示 starter thread 或空态引导
  - composer 仍可发送第一条消息
- Postconditions: 无

#### TC-E-002: Composer 默认小，高度增长但不超过 1/3 视口
- Requirement: `Manager/New Flow` composer 默认小，随输入变高，但最大不超过页面高度 1/3
- Priority: High
- Preconditions:
  - 已进入 Manager 或 New Flow
- Test Steps:
  1. 初始观察 composer 高度
  2. 连续输入长文本
  3. 再输入超过多屏内容
- Expected Results:
  - 默认高度明显低于旧大文本框
  - 文本增多时高度增加
  - 达到上限后 textarea 内部滚动，而不是继续侵占主区
- Postconditions: 无

#### TC-E-003: New Flow 不应高亮旧 manager session
- Requirement: 进入 `New Flow` 时必须清空旧的 manager 选中态
- Priority: High
- Preconditions:
  - 当前已有某个 manager thread 被选中
- Test Steps:
  1. 点击 `New Flow 新建`
  2. 观察 Recent Threads 与主区
- Expected Results:
  - `New Flow` 主区显示空白 manager thread
  - Recent Threads 中旧 manager 不再错误保持 active 高亮
- Postconditions: 当前上下文为新的空白 manager thread

#### TC-E-004: History 与 Recent Threads 同时存在同名条目时仍可正确进入目标线程
- Requirement: 即使侧栏 Recent Threads 与 History 列表重复出现相同标题，也不能造成目标线程混淆
- Priority: Medium
- Preconditions:
  - 某个项目线程同时出现在 Recent Threads 与 History
- Test Steps:
  1. 分别从 Recent Threads 和 History 打开同一 supervisor thread
  2. 返回 Manager
- Expected Results:
  - 两条路径都进入同一 flow
  - 返回的 manager context 一致
- Postconditions: 当前线程上下文未漂移

### 3. Error Handling Tests

#### TC-ERR-001: Desktop bridge 未注入时显示显式产品态空页
- Requirement: preload 缺失时必须显示 `Desktop bridge 未连接`，而不是崩溃
- Priority: High
- Preconditions:
  - `window.butlerDesktop` 未注入
- Test Steps:
  1. 以纯浏览器 / 无 preload 环境打开 renderer
- Expected Results:
  - 页面显示 bridge 缺失说明
  - 不抛出查询错误 toast 风暴
- Postconditions: 无

#### TC-ERR-002: 手填无效 config path
- Requirement: `Config Path Fallback` 输入无效路径时必须有明确错误反馈
- Priority: High
- Preconditions:
  - Desktop 已启动
- Test Steps:
  1. 输入不存在的 config path
  2. 点击 `Attach Path`
- Expected Results:
  - 出现错误反馈
  - 页面不进入半初始化状态
- Postconditions: 不保存错误路径为有效工作区

#### TC-ERR-003: Thread payload 任意一条加载失败时，其他界面不应整体白屏
- Requirement: `thread-home / manager-thread / supervisor-thread / template-team / agent-focus` 任一失败时要局部报错
- Priority: High
- Preconditions:
  - 桥接命令返回异常
- Test Steps:
  1. 让某个 payload 查询抛错
  2. 观察页面反馈
- Expected Results:
  - 对应 error toast 可见
  - 其余结构仍保留
- Postconditions: 无

#### TC-ERR-004: Manager message 执行失败后保留当前 thread
- Requirement: manager send 失败时不得错误切换到 Supervisor
- Priority: High
- Preconditions:
  - `manager-message` 返回异常
- Test Steps:
  1. 在 Manager / New Flow 中发送消息
  2. 让 bridge 报错
- Expected Results:
  - 显示 `Manager message failed`
  - 仍停留在当前 manager thread
  - 输入上下文保留
- Postconditions: 无

### 4. State Transition Tests

#### TC-ST-001: Manager -> Supervisor -> Agent Focus -> Supervisor
- Requirement: thread-first 工作路径必须可持续切换，不丢上下文
- Priority: High
- Preconditions:
  - Flow 已创建
- Test Steps:
  1. 从 Manager 进入 Supervisor
  2. 从 Supervisor 进入 Agent Focus
  3. 再返回 Supervisor
- Expected Results:
  - 每一步的标题、role、flow 上下文都正确
  - 返回后仍处于原始 supervisor thread
- Postconditions: 当前 flow 上下文仍有效

#### TC-ST-002: History/Recent Thread -> Supervisor -> Manager
- Requirement: supervisor thread 与 manager session 的绑定要保持一致
- Priority: High
- Preconditions:
  - 至少两条 thread 存在不同 `manager_session_id`
- Test Steps:
  1. 从 History 或 Recent Threads 打开一个非默认 supervisor thread
  2. 返回 `Manager 管理台`
- Expected Results:
  - `managerSessionId` 被同步成该 thread 来源
  - Manager 显示对应 manager thread
- Postconditions: manager/supervisor 上下文一一对应

#### TC-ST-003: 切换到 New Flow 会清空旧 manager 选中态
- Requirement: 新建 flow 时不能继承旧 manager 的 active selection
- Priority: High
- Preconditions:
  - 当前正在查看某个 manager thread
- Test Steps:
  1. 点击 `New Flow 新建`
  2. 观察 rail active 状态
- Expected Results:
  - `New Flow` 为当前入口
  - 旧 manager thread 不再以 active 方式高亮
- Postconditions: 当前处于 blank manager thread

#### TC-ST-004: 主题切换后不影响线程导航与操作能力
- Requirement: Day/Night 只是视觉状态，不改变功能
- Priority: Medium
- Preconditions:
  - 已 attach config
- Test Steps:
  1. 切换主题
  2. 再执行 `History -> Supervisor -> Agent Focus`
- Expected Results:
  - 所有导航与操作行为仍可用
  - 仅视觉 token 发生变化
- Postconditions: 无

## Test Coverage Matrix

| Requirement ID | Test Cases | Coverage Status |
|---|---|---|
| REQ-001 Butler-native thread surfaces | TC-F-001, TC-F-004, TC-ST-001, TC-ST-002 | ✓ Complete |
| REQ-002 Codex 风格视觉壳 | TC-F-001, TC-F-006, TC-F-007, TC-E-002 | ✓ Complete |
| REQ-003 全页面统一视觉系统 | TC-F-001, TC-F-005, TC-F-006, TC-ERR-001, TC-ERR-003 | ✓ Complete |
| REQ-004 Manager/New Flow 底部 dock composer | TC-F-002, TC-E-002, TC-ST-003 | ✓ Complete |
| REQ-005 Composer 默认小且上限 1/3 视口 | TC-E-002 | ✓ Complete |
| REQ-006 Agent Focus 是 role lens | TC-F-005, TC-ST-001 | ✓ Complete |
| REQ-007 双主题支持与持久化 | TC-F-007, TC-ST-004 | ✓ Complete |
| REQ-008 renderer-only，不改 bridge 合同 | TC-ERR-001, TC-ERR-003 | ✓ Complete |
| REQ-009 manager / supervisor thread 上下文不漂移 | TC-F-004, TC-E-004, TC-ST-002, TC-ST-003 | ✓ Complete |

## Notes

- Electron e2e 依赖可用图形环境；若当前机器没有 `DISPLAY` 且缺少 `xvfb-run`，需在具备图形环境或 Xvfb 的机器上补跑桌面点击回归。
- 本文档补充的是“视觉壳升级”场景；旧的 [butler_flow_desktop_thread_workbench_test_cases.md](./butler_flow_desktop_thread_workbench_test_cases.md) 仍保留 thread-first Desktop 的基础覆盖。
- 自动化测试优先建议覆盖：`TC-F-002`、`TC-F-004`、`TC-F-005`、`TC-E-002`、`TC-ERR-001`、`TC-ST-002`。
