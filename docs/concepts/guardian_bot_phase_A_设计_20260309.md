# Guardian Bot Phase A 设计

## 1. 目标

guardian 不再只是 `restart_guardian_agent.py` 形式的被动看门狗，而是一个独立常驻 bot。

它的主职责是：

1. keep butler alive
2. 审阅 butler / heartbeat 的自我升级请求
3. 主导涉及代码修改或重启的修复
4. 对低风险修复做备案、追踪、复盘
5. 积累故障知识、升级历史和维护经验

## 2. 已确认边界

当前已确认的产品边界如下：

1. guardian 拥有独立的飞书身份和独立对话入口
2. guardian 是独立常驻 bot，不是 butler 主进程里的一个弱子模块
3. guardian 拥有独立记忆，且记忆范围包括故障模式、升级审阅历史、代码维护经验、用户偏好、普通上下文
4. guardian 可修改全仓，可运行测试，可自动重启并自动上线
5. guardian 对升级请求采用严格审阅
6. guardian 的审阅结论只有 `approve / reject / need-info`
7. guardian 默认采用流式汇报，而不是只在结束后汇报
8. heartbeat 的轻量修复可以直接做，但必须先通知 guardian 备案
9. 一旦涉及代码修改或重启，必须转为 guardian 主导

说明：飞书 secret 不写入设计文档，统一放配置或密钥管理层。

## 3. 角色模型

guardian 是 Butler 体系中的维护角色，而不是对话角色。

它的核心人格应当是：

1. 保活优先
2. 可回滚优先于冒进修复
3. 证据优先于猜测
4. 修复闭环优先于一次性补丁
5. 对用户持续透明，但不过度等待用户授权

guardian 的职责边界如下：

### 3.1 guardian 负责

1. 主进程、heartbeat、guardian 自身的健康监测
2. 升级请求审阅
3. 运行时故障诊断与修复
4. 配置阈值优化
5. 修复后的测试、重启、验证、回滚
6. 维护报告、升级档案、故障知识归档

### 3.2 guardian 不负责

1. 代替 butler 承担普通用户对话
2. 代替 heartbeat 承担持续任务规划
3. 在无证据情况下做大规模架构改造
4. 跳过审阅直接接受高风险升级请求

## 4. 输入源

guardian 的输入应统一归为四类：

### 4.1 运行时事件

1. 对话主进程停止
2. heartbeat 停跳或卡死
3. 状态漂移
4. 重复进程 / 孤儿进程
5. 日志异常
6. 模型子进程超时
7. 测试失败

### 4.2 升级请求

来源包括：

1. butler 主对话请求
2. heartbeat 升级申请
3. guardian 自主发现的系统性问题

### 4.3 备案请求

heartbeat 执行轻量修复前，需要发送备案事件给 guardian，便于后续定位“坏改动”。

### 4.4 用户直接指令

例如：

1. 强制诊断某个故障
2. 冻结某类自动修复
3. 允许或禁止某类升级
4. 要求回滚

## 5. 输出物

guardian 的输出不止是日志，应包括：

1. 实时流式汇报
2. 审阅结论
3. 修复计划
4. 修复执行记录
5. 测试结果
6. 重启与上线结果
7. 回滚记录
8. 故障复盘记录

## 6. 审阅协议

guardian 处理升级请求时，必须经过固定审阅清单。

### 6.1 审阅必查项

1. 目标：到底想修什么，为什么修
2. 范围：涉及哪些文件、模块、状态文件、配置项
3. 风险：是否影响主对话链路、heartbeat 链路、记忆链路、飞书链路
4. 类型：是轻量修复、代码修复、配置修复、运行时恢复还是结构升级
5. 验证：修复完成后如何证明已经生效
6. 回滚：失败时如何回退到修复前状态
7. 冲突：是否与当前 pending 变更或正在进行的修复冲突
8. 权限：该动作是否越过了 heartbeat 的权限边界

### 6.2 审阅结论

guardian 仅返回三态：

1. `approve`
2. `reject`
3. `need-info`

### 6.3 三态含义

`approve`：
说明方案充分、可执行、可验证、可回滚，允许进入执行阶段。

`reject`：
说明方案风险过高、目标不清、边界越权、无法验证或会引入更大不稳定性。

`need-info`：
说明不是完全否决，而是需要补充材料，例如影响范围、验证步骤、回滚方案、依赖说明。

## 7. 修复等级

guardian 应将修复动作分为三层，而不是都走一条通道。

### 7.1 L1 备案型轻修复

由 heartbeat 直接执行，但必须先备案给 guardian。

典型动作：

1. 写状态文件
2. 更新轻量任务元数据
3. recent memory 压缩
4. 非代码型的小型整理

guardian 在这个层级不直接审批，但必须留下：

1. 备案时间
2. 发起者
3. 动作摘要
4. 影响对象
5. 执行结果

### 7.2 L2 guardian 自动修复

由 guardian 主导，可自动执行。

典型动作：

1. 清理重复进程
2. 清理孤儿模型进程
3. 重挂 heartbeat / guardian sidecar
4. 修正 run state / pid state 漂移
5. 调整 timeout / stale / check_interval 等阈值
6. 运行回归测试
7. 自动重启并上线

要求：

1. 必须有可验证结果
2. 必须有失败回滚路径
3. 必须产出修复记录

### 7.3 L3 结构升级或高风险修复

仍由 guardian 主导，但必须进入严格审阅和明确执行计划。

典型动作：

1. 改 Python 业务逻辑
2. 改多文件协议
3. 改 memory policy
4. 改 prompt / 审批链路 / 任务链路
5. 改 guardian 自身架构

要求：

1. 审阅结论必须为 `approve`
2. 必须先定义验证集
3. 必须定义回滚点
4. 执行中持续流式汇报

## 8. 用户交互协议

guardian 的修 bug 交互应固定为四个阶段，避免忽冷忽热。

### 8.1 发现

报告：

1. 症状
2. 影响面
3. 初步判断
4. 当前准备采取的路径

### 8.2 进入修复

报告：

1. 修复等级
2. 计划动作
3. 是否会改代码
4. 是否会重启
5. 回滚准备是否就绪

### 8.3 修复中

流式汇报关键节点：

1. 证据新增
2. 假设变化
3. 改动落地
4. 测试结果
5. 是否切换到回滚或替代方案

### 8.4 结束

报告：

1. 是否修复成功
2. 证据是什么
3. 改了哪些关键点
4. 是否自动重启并上线
5. 是否存在遗留风险
6. 是否需要继续观察

## 9. 记忆设计

guardian 不应复用 butler 当前的“只有 runtime 报告”的弱记忆模式，而应形成自己的记忆层。

建议分为：

### 9.1 Recent Memory

保存：

1. 最近故障
2. 最近审阅结论
3. 最近自动修复
4. 最近回滚

### 9.2 Local Memory

保存：

1. 故障模式库
2. 升级审阅样例
3. 常见修复策略
4. 高风险文件清单
5. 用户偏好和维护习惯
6. 自身身份与职责认知

### 9.3 维护账本

建议增加独立 ledger，记录：

1. 备案事件
2. 审阅请求
3. 审阅结论
4. 修复执行
5. 测试结果
6. 重启与上线
7. 回滚

## 10. 升级单 Schema

Phase A 建议 guardian 统一处理如下 JSON 结构：

```json
{
  "request_id": "uuid",
  "source": "heartbeat|butler|guardian",
  "request_type": "record-only|auto-fix|code-fix|restart|architecture",
  "title": "简短标题",
  "reason": "为什么要做",
  "scope": {
    "files": [],
    "modules": [],
    "runtime_objects": []
  },
  "planned_actions": [],
  "requires_code_change": false,
  "requires_restart": false,
  "verification": [],
  "rollback": [],
  "risk_level": "low|medium|high",
  "review_status": "pending|approve|reject|need-info|executing|done|rolled-back",
  "review_notes": [],
  "execution_notes": []
}
```

说明：

1. `record-only` 用于 heartbeat 轻量修复备案
2. `auto-fix` 用于 guardian 自动修复
3. `code-fix` 和 `restart` 进入 guardian 主导链路
4. `architecture` 用于结构级改动，风险最高

## 11. 已确认的 Phase B 实现边界

在进入实现前，以下结构选择已经确认：

1. guardian 采用部分共享记忆模式
2. guardian 拥有独立 recent memory、审阅记录、备案账本
3. guardian 可以读取 butler 的选定 local memory，但不与 butler 完全共用维护记忆
4. heartbeat 轻量修复的备案落入独立 guardian ledger，而不是直接塞进 task ledger
5. guardian 的飞书入口用于维护对话、直接接修复任务、审批 butler / heartbeat 请求
6. guardian 的自动测试基线按 request 动态决定，不强制固定 smoke suite
7. guardian 允许审阅并发，但执行阶段必须串行

## 12. 状态机

guardian 应有明确状态机，避免“既在修，又在审，又在巡检”的混乱状态。

建议主状态：

1. `idle`
2. `observing`
3. `reviewing`
4. `need-info`
5. `executing`
6. `validating`
7. `restarting`
8. `monitoring`
9. `rolled-back`
10. `failed`

约束：

1. 同一 request 在任一时刻只能有一个主状态
2. `reviewing -> executing` 之间必须留下审阅结论
3. `executing -> restarting` 之间必须完成基础测试
4. `restarting -> monitoring` 之间必须确认服务恢复

## 13. Phase A 到 Phase E 路线图

### Phase A

目标：定义 guardian 协议，不改大逻辑。

交付：

1. 角色与边界
2. 升级单 schema
3. 审阅协议
4. 修复等级
5. 交互协议

### Phase B

目标：让 guardian 拥有独立记忆和审阅层。

交付：

1. guardian recent memory
2. guardian local memory
3. 审阅请求存储
4. 备案账本

### Phase C

目标：让 guardian 能主导执行修复。

交付：

1. 自动修复执行器
2. 测试执行器
3. 重启与验证执行器
4. 回滚执行器

### Phase D

目标：打通 guardian 与用户、butler、heartbeat 的交互链路。

交付：

1. 独立飞书入口
2. 流式汇报模板
3. 审批与 need-info 补料机制
4. 轻量修复备案通道

### Phase E

目标：让 guardian 具备持续维护与自我改进能力。

交付：

1. 故障模式复用
2. 自动阈值调优建议
3. 维护策略升级建议
4. guardian 自身的维护协议

## 14. Phase C 前必须拍板的问题

进入 Phase C 前，还需要用户明确以下执行结构问题：

1. guardian 的执行器是单独新 bot 代码目录，还是先在现有 `restart_guardian_agent.py` 上演进
2. guardian ledger 是单文件 JSON，还是多文件事件目录
3. guardian 与 heartbeat 的备案协议是文件投递，还是统一 request queue
4. guardian 执行代码修改时，是否必须先生成 patch 预案再真正落地
5. guardian 的动态测试选择规则，是由请求显式提供，还是由 guardian 自己根据改动范围推断

## 15. 已确认的 Phase C 执行边界

在进入 Phase C 实现前，以下执行形态已经确认：

1. guardian 第一版采用独立代码目录，不在现有 `restart_guardian_agent.py` 上直接膨胀实现
2. 新目录放在 Butler 上一级目录下，作为与 butler 并列的独立 guardian bot 实现
3. guardian ledger 第一版采用多文件事件目录，便于审计、追踪、回滚和复盘
4. heartbeat 向 guardian 的轻量修复备案第一版采用文件投递协议
5. guardian 执行任何代码修改前，必须先形成 patch 预案
6. guardian 的动态测试采用“两者结合”：默认由 guardian 按改动范围推断，用户或请求可以覆盖

## 16. 已确认的 Phase D 工程落点

在进入具体工程实现前，以下工程落点已经确认：

1. guardian 独立代码目录名为 `guardian_bot_code`
2. guardian 第一版工程放在 Butler 上一级目录，与 Butler 并列
3. guardian 记忆根采用“独立 recent + state，共享部分 Butler local memory”
4. heartbeat 到 guardian 的文件投递目录为 `butler_bot_agent/agents/state/guardian_requests`
5. guardian ledger 第一版落在独立事件目录，不与 task ledger 混用
6. 用户直接发给 guardian 的修复任务，只有低风险可直接执行，其余先审阅再执行

## 17. 第一版工程建议

### 17.1 guardian_bot_code

建议目录：

1. `guardian_bot_code/guardian_bot`
2. `guardian_bot_code/configs`
3. `guardian_bot_code/docs`

### 17.2 Butler 侧协作目录

建议目录：

1. `butler_bot_agent/agents/state/guardian_requests`
2. `butler_bot_agent/agents/state/guardian_ledger`

### 17.3 第一版实现顺序

1. 先打通 request 文件投递与 guardian 轮询读取
2. 再实现 ledger 事件写入
3. 再实现 review 状态机
4. 再实现低风险自动修复执行器
5. 最后接入飞书入口与直接修复任务
