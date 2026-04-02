## 20260327 · 小红书 · 航天与二阶控制论内核：拆了十三个 Agent · 完整系统脑暴

- **来源**：小红书笔记《航天与二阶控制论内核：拆了十三个 Agent 之后，我发现它们讨论的不是同一个东西》（作者：克熵Sam）
- **抓取方式**：已实际使用 `web-note-capture-cn` 抓取分享页，并下载 29 张配图到本地
- **Raw 抓取结果**：`工作区/Butler/runtime/xhs_capture/20260327_13_agent_system/xiaohongshu_69c29d4b000000002301d3b9.md`
- **Raw JSON**：`工作区/Butler/runtime/xhs_capture/20260327_13_agent_system/xiaohongshu_69c29d4b000000002301d3b9.json`
- **图片目录**：`工作区/Butler/runtime/xhs_capture/20260327_13_agent_system/images/`
- **补充说明**：我也实际尝试了 `web-image-ocr-cn` 旧 OCR 链路，但当前环境无可用 OCR 后端；下面内容来自**逐张读图后的人工还原**，不是伪造 OCR 结果

---

## 1. 一句话总纲

> **这篇的真正命题不是“哪一个 Agent 更强”，而是：过去被一股脑叫成 Agent 的东西，其实正在长成一套可分层的 Agent Stack。**
>
> 作者用**控制论 / 二阶控制论**做坐标系，把 13 个项目按“控制职责”而不是按“产品名”重排，最后得到的不是 13 个竞品，而是一套从 `runtime -> kernel -> subsystem/protocol -> gateway/workbench -> meta-loop` 逐层长出来的控制系统。

---

## 2. 作者的核心判断

### 2.1 为什么“十三个 Agent”其实不是同一个对象

作者拆了这些项目：

- `Claude Code`
- `Codex`
- `SWE-agent`
- `OpenHands`
- `OpenClaw`
- `browser-use`
- `memU`
- `Symphony`
- `Evolver`
- `AutoResearchClaw`
- `PicoClaw`
- `Mini/MimiClaw`（图中前后文写法略有出入）
- `TEN Framework`

作者的结论是：

- `Claude Code` 回答的是：**单任务控制循环怎么闭环**
- `TEN Framework` 回答的是：**异构消息与信号协议怎么统一**
- `browser-use` 回答的是：**浏览器作为感知环境时，动作空间怎么编码**
- `memU` 回答的是：**记忆要不要从“上下文的一行代码”升级成一级系统模块**
- `Evolver` 回答的是：**harness 自己怎么演化，而不是任务怎么做完**

所以问题不再是“谁是更好的 Agent”，而是：

- 它在 **Stack 的哪一层**
- 它承担 **什么控制职责**
- 它跟别的层之间是 **上下游关系**、**交叉关系** 还是 **真正同层竞争**

### 2.2 为什么要换坐标系

作者认为，只用“产品功能”比较会产生错位：

- 拿 `Claude Code` 和 `OpenHands` 比，像拿 Linux 内核和 GNOME 桌面环境比
- 拿 `OpenClaw` 和 `browser-use` 比，也是在比不同层的对象
- 拿 `memU` 和 `Claude Code` 比，是把“记忆子系统”和“控制内核”混成一类

所以他换成了一个更稳的坐标系：**控制论（Cybernetics）**。

---

## 3. 控制论是这篇文章的底层框架

### 3.1 一阶控制论：经典闭环

作者把控制系统抽象成一个基本闭环：

- `observe`
- `compare`
- `compute / decide`
- `apply`
- `feedback`

对应直觉是：

- 有目标
- 有传感
- 有反馈
- 有控制器

这套框架在不同年代反复出现：

- 蒸汽机时代：机械调速器
- 云原生时代：`K8s controller`
- AI 代码时代：`LLM + codebase + 多维反馈`

### 3.2 但 Agent 系统不是普通的一阶控制系统

作者指出，一阶控制论默认有几个前提：

- 目标清晰
- 反馈可测量
- 控制器稳定
- 观察者站在系统外部

而 Agent 系统恰恰破坏了这些前提：

- 目标从“维持 25°C”变成“把这个 bug 修好”“写一篇文献综述”——目标是**语义化、会漂移的**
- 反馈从“温度传感器读数”变成“代码质量”“研究深度”“结论可信度”——反馈是**多维、主观、难量化的**
- 控制器不再是 PID，而是 LLM —— **概率系统**
- LLM 既是控制器又部分充当观察者，其输出还会进入下一轮输入

### 3.3 二阶控制论：把观察者纳入系统

因此作者转向二阶控制论，认为 Agent 系统至少有三个核心风险：

1. **自指（Self-reference）**
   - 模型生成代码，再评价自己生成的代码
   - 系统不是依据外部反馈调整，而是在依据自己的产出评价自己

2. **目标漂移（Goal Drift）**
   - 用户说“修这个 bug”
   - Agent 修着修着开始重构，甚至改写问题本身
   - 参考值不再稳定，控制器改写了目标

3. **反馈污染（Feedback Contamination）**
   - Agent 的输出进入训练数据、代码库、记忆库，再回流影响下一轮决策
   - 反馈不再独立，系统开始自我强化偏差

作者的观点非常明确：

> 这不是“高级功能”，而是 Agent 系统的**底层病灶**。忽略它们，系统就会漂移、退化，并在错误方向上自我强化。

---

## 4. 作者还原出来的 Agent Stack

### 4.1 总体层级

作者最终给出的主图是：

1. `Runtime`
2. `Kernel`
3. `Subsystem / Protocol`
4. `Gateway / Workbench`
5. `Meta-loop`

它回答的不是“谁更完整”，而是：

- 哪一层负责**环境感知与动作执行**
- 哪一层负责**单任务闭环**
- 哪一层负责**记忆 / 协议 / 信号抽象**
- 哪一层负责**系统入口与边界控制**
- 哪一层负责**多 Agent 协调与系统自演化**

### 4.2 Runtime 层：环境与动作原语

作者放在这一层的典型项目：

- `browser-use`
- `AutoResearchClaw`
- `PicoClaw`
- `Mini/MimiClaw`

这一层的共同问题是：

- 感知什么环境
- 动作如何编码
- 反馈如何回收
- 在成本、上下文、设备约束下怎么运行

作者给出的例子很具体：

- `browser-use`
  - 感知：浏览器 DOM + 截图
  - 动作：`click / type / scroll / navigate`
  - 反馈：页面状态变化

- `AutoResearchClaw`
  - 感知：论文 / 网页 / 专利库
  - 动作：搜索 / 阅读 / 对比 / 引用验证
  - 反馈：证据覆盖率

- `PicoClaw`
  - 约束：`10MB` 可执行文件 + 最低成本运行

- `Mini/MimiClaw`
  - 约束：`$5` 量级单片机 + `16KB` 上下文

作者的关键判断：

- 这些项目底层都能压缩成 `observe -> act / evaluate` 的闭环
- **但它们运行的世界完全不同**
- 所以 runtime 是**不可互换**的
- 通用 harness 平台必须把 **kernel 与 runtime 解耦**

### 4.3 Kernel 层：单任务控制内核

作者放在这一层的典型项目：

- `Claude Code`
- `Codex`
- `SWE-agent`

它们共同回答的问题是：

> **单任务控制循环怎么闭环？**

作者给的三种代表性解法：

- `Claude Code`
  - 极简内核：`while(tool_call)` 单线程循环 + 一组原语工具
  - 智能推给模型，harness 做窄

- `Codex`
  - 安全内核：Rust 三层策略引擎 + 文件/网络卫士 + 用户确认
  - 难点不是循环，而是谁来拦截什么

- `SWE-agent`
  - 学术化内核：围绕 `ACI`（Agent-Computer Interface）与 benchmark 设计控制环
  - 强调窗口、动作原语、实验设置会显著影响结果

作者的抽象是：

- 三者底层控制结构是同构的
- 核心仍是 `observe -> compare -> compute -> apply -> feedback`
- `Kernel` 的护城河不一定最深，因为 while 循环式代理会越来越普及
- 但 Kernel 仍然是整个 Stack 的最小稳定控制芯

### 4.4 Subsystem / Protocol 层：把“附属功能”升格为一级系统模块

作者放在这一层的项目：

- `memU`
- `TEN Framework`

这一层的核心不是“再补一个功能”，而是：

- 记忆如何系统化
- 信号如何统一
- 文本之外的控制面如何成立

作者对 `memU` 的判断是：

- 它不是“更好的 Agent”
- 它在回答一个更窄但更关键的问题：
  - **记忆要不要成为一级系统模块？**
- 它更像未来平台里的 `memory service`
- 而不是完整 runtime

作者特别点名了 `memU` 的设计信号：

- 三层渐进：`topics -> segments -> full content`
- 三信号显著性评分：`similarity × log(reinforcement) × recency_decay`

作者对 `TEN Framework` 的判断是：

- 它定义了四种一等消息类型：
  - `cmd`
  - `data`
  - `audio_frame`
  - `video_frame`
- 把文本之外的信号流纳入统一协议层
- 它在做的是给 Agent 建一条“高速公路”
- 而不是让每次函数调用都走乡间小路

作者的整体判断：

- 记忆和信号流已经不该再是一行代码
- 它们应该成为**一级系统模块**

### 4.5 Gateway / Workbench 层：系统入口、边界与工作台

作者在这一层实际上区分了两个角色：

- `OpenClaw`：更偏 `Gateway`
- `OpenHands`：更偏 `Workbench`

#### `OpenClaw`：Gateway

作者认为 `OpenClaw` 不是完整 Agent 的替代品，而是：

- control plane 的**入口边界**
- 它关心：
  - `provider routing`
  - `session` 生命周期管理
  - `policy enforcement`
  - `session mediation`

也就是说：

- 一个入口接多个模型后端
- 对话 / 会话状态有显式生命周期
- 请求到内核前先做拦截与预处理

#### `OpenHands`：Workbench

作者认为 `OpenHands` 更像平台壳层：

- 给内核提供工作台
- 给用户提供交互面
- 给多能力提供装配环境

作者特别点出 `OpenHands` 的 EventStream 架构：

- `Action / Observation` 被类型化
- `Condenser` 负责上下文压缩策略
- 多种 `Runtime` 负责环境隔离
- 用户看到的是 IDE 式界面
- 底层跑的是事件驱动的 Agent 生命周期

作者的总结非常关键：

> **内核之上不是“用户界面”这么简单，而是一层有自己控制职责的系统层。**

### 4.6 Meta-loop 层：协调多个 Agent，并让 harness 自己演化

作者放在这一层的项目：

- `Symphony`
- `Evolver`

它们不再在优化“一个 Agent 怎么做完任务”，而是在优化：

- 多个 Agent 怎么协同
- harness 自己怎么学习和演进

#### `Symphony`

作者给它的定位：

- 多 Agent orchestration
- 用 `Elixir / OTP` 的 `Supervision Tree` 管理多个 `Codex` 实例
- `GenServer` 维护全局调度状态
- `WORKFLOW.md` 一份文件装下：
  - 轮询间隔
  - 并发上限
  - 审批策略
  - agent prompt 模板

作者把它理解为：

- 不是任务 runtime
- 而是多 Agent 之间的**协作调度系统**

#### `Evolver`

作者给它的定位更偏“系统自演化”：

- 记忆图谱：`SignalSnapshot -> Hypothesis -> Attempt -> Outcome`
- 会计算每个 `Gene` 的成功率
- 自动 ban 掉屡次失败策略
- 强制从 `repair` 跳到 `innovate`
- 对爆炸半径做控制：
  - `max_files`
  - `forbidden_paths`
  - 超界后 `git checkout` / `git clean -fd`

作者的结论是：

- 这不是一阶“任务如何完成”的问题
- 而是二阶“多个执行者如何协调”“系统如何改进自己”的问题
- 没有这一层，Stack 只能执行，**不能演化**

---

## 5. 这套系统里，哪些是可复用的，哪些是领域私有的

作者给出了一条很重要的分界线。

### 5.1 平台可复用的，不是能力，而是控制结构

作者认为跨领域真正可复用的是：

- `loop`
- `evaluator`
- `trace`
- `policy`
- `governance`

更展开一点，就是：

- 闭环：`observe -> compare -> act -> feedback`
- 评估：生成器与评估器分离，输出必须经过检查
- 追踪：每步动作事件化、可回放、可审计
- 策略：哪些动作自动执行、哪些动作需要确认、哪些动作直接禁止
- 治理：人在回路中不是可选开关，而是控制循环的一部分

### 5.2 领域私有的，是感知器、执行器、参考值和领域评估器

作者认为不同领域真正不同的是：

- `sensor`
- `actuator`
- `reference`
- `domain evaluator`

这也是为什么：

- 浏览器 runtime
- 研究 runtime
- 嵌入式 runtime
- 航天 runtime

不能简单互相替代。

---

## 6. 生成与验证不对称：作者给出的硬边界

作者借 `Cobbe et al.` 的研究强调：

> **生成正确解，比验证正确解难得多。**

他把这件事翻译成工程原则：

- 你不需要把生成器写得“神”
- 你需要把评估器写得更准
- 生成器可以换模型
- 评估器必须定制

作者举的几个例子：

- `Claude Code` 的 `92%` 阈值压缩，是内核自带评估器
- `AutoResearchClaw` 的四层引文验证，是研究领域评估器
- `Codex` 的三层策略引擎，本质上是安全维度的评估器

也就是说：

- **Generator 可以多样**
- **Evaluator 必须硬**

这件事直接决定了作者后面为什么一定要去“高风险、不可失败领域”做验证。

---

## 7. 作者眼里的竞争结构与护城河

### 7.1 竞争不再是“一个 Agent 打败另一个 Agent”

作者明确说：

- 真正的竞争不是“谁的 Agent 更强”
- 而是“谁占住了 Stack 中更核心的一层”

如果这套 Stack 分层成立，那么竞争会变成：

- `Kernel`：谁的单任务控制环更稳、更清晰
- `Protocol / Subsystem`：谁定义了被生态采纳的消息与记忆标准
- `Gateway`：谁把住了入口与治理边界
- `Runtime`：谁扎进了真实行业，把领域感知和动作做深
- `Meta-loop`：谁真正拥有系统自演化所需的运行数据与失败闭环

### 7.2 作者的护城河判断

作者的趋势判断大致是：

- `Kernel`
  - 护城河不一定最深
  - 因为 while 循环式代理会越来越像公共能力

- `Subsystem / Protocol`
  - 反而非常深
  - 因为一旦底层标准被采纳，就很难替换

- `Runtime`
  - 很深
  - 因为必须真正进入那个行业，积累专属感知与反馈知识

- `Meta-loop`
  - 也很深
  - 因为它依赖大量真实运行数据与失败样本做校准

所以作者把问题改写成一句非常漂亮的话：

> **以后不问“你有没有 Agent”，而问“你站在 Stack 的哪一层”。**

---

## 8. 为什么作者最后要把它拿去航天验证

这是这篇最有意思也最硬的部分。

作者不是随便找个行业落地，而是刻意挑了一个**不允许失败**的领域：

- 航天是确定性系统
- 单次错误可能不可逆
- 互联网可以“先上线再修”
- 航天很多时候不允许这样做

所以作者判断：

- 在航天里，`生成即决策` 会出事
- 可行路径只能是：
  - `生成`
  - `评估`
  - `人审`
  - `执行`

作者还指出航天恰好具备几个天然适合验证这套架构的条件：

1. **强审计**
   - 每条结论要能追溯到来源文档
   - 出事故时，调查链不是可选项

2. **强 Trace**
   - 不是锦上添花
   - 而是系统基座

3. **高信息流摩擦**
   - 工程师大量时间耗在验证、追溯、文档和异常排查
   - 正适合 Agent 自动化切入

4. **不允许“边飞边错”**
   - 所以能逼出最严的评估、治理和闭环设计

作者最终想做的，不是再造一个 coding agent，而是：

- 用这 13 个项目里提炼出的控制结构和工程模式
- 搭一个面向航天工程信息流自动化的开源 harness 平台
- 把需求追溯、测试报告生成、异常初筛、运维建议串起来
- **不替代工程师判断，只压缩“数据产生 -> 人可决策”之间的摩擦**

---

## 9. 我对这套系统的完整还原

如果把作者整篇内容压成一套更干净的系统表达，我会写成：

### 9.1 系统目标

不是造“更强的 Agent”，而是造：

- 一套**可分层**
- 可治理
- 可审计
- 可跨领域挂载 runtime
- 可在高风险场景落地

的 `Agent Stack / Harness Platform`

### 9.2 系统总图

```text
Meta-loop
  ├─ 多 Agent 协调
  └─ harness 自演化

Gateway / Workbench
  ├─ 入口、路由、会话、策略边界
  └─ 用户工作台、事件总线、上下文压缩

Subsystem / Protocol
  ├─ 记忆模块
  └─ 多模态/多信号协议层

Kernel
  └─ 单任务控制内核（observe → compare → compute/apply → feedback）

Runtime
  └─ 具体领域的感知环境、动作原语与反馈结构
```

### 9.3 横切规则

无论哪一层，系统都要被下面五类横切规则约束：

- `Evaluator`
- `Trace`
- `Policy`
- `Governance`
- `Human-in-the-loop`

### 9.4 领域装配规则

平台层与领域层分工是：

- 平台提供：
  - `loop`
  - `evaluator skeleton`
  - `trace`
  - `policy`
  - `governance`

- 领域提供：
  - `sensor`
  - `actuator`
  - `reference`
  - `domain evaluator`

这就是作者所谓：

> 复用的不是能力，而是控制结构。

---

## 10. 这篇对我们最有启发的地方

### 10.1 最值钱的，不是“13 个项目目录”

我觉得这篇最值钱的不是那张项目大表，而是它做了两件事：

1. **把“Agent”去神化**
   - Agent 不是一个单体产品类别
   - 而是一套正在分层的系统

2. **把“平台”重新定义成控制结构**
   - 真平台不是把所有能力煮成一锅
   - 而是抽出可复用控制结构，让不同领域挂自己的 runtime

### 10.2 它对架构判断的几个硬提醒

- 不要跨层比较产品
- 不要把 memory 当附属功能
- 不要把 UI / IDE 壳层误当“只是前端”
- 不要把人类审核看成外挂按钮
- 不要把评估器写成事后补丁
- 不要拿低风险 demo 的成功，替代高风险场景的验证

### 10.3 我认同的部分

- **分层视角是对的**
  - 这比“全叫 Agent”清晰太多

- **二阶控制论切入是对的**
  - 对 LLM 系统来说，目标漂移 / 反馈污染 / 自指，确实是比“再多几个工具”更底层的问题

- **生成器和评估器必须分开**
  - 这是把 Agent 从演示玩具推到工程系统的关键

- **高风险场景验证比内部 benchmark 更有说服力**
  - 因为只有硬约束环境，才会逼出真的治理结构

### 10.4 我会补充的部分

- 这套图已经很强，但还可以再补一层：
  - `Durability / Writeback / Recovery`
  - 也就是长期运行时的恢复、持久化、审计回写

- 作者虽然讲了 `trace / governance / policy`
  - 但对**投影层 / 观测读模型**说得还不够细
  - 真平台化时，给用户看的状态、给审计看的事件、给系统恢复用的持久化对象，最好继续拆开

- 另外它很强调 Stack 分层
  - 但组织侧谁拥有哪层、谁定义契约、谁做回归验证，这一层还没完全展开

---

## 11. 一个更直接的结论

如果把这篇话说得再白一点：

> **Agent 不是一个产品类别，而是一套正在分层的控制架构。**
>
> **真正值得做的，不是又一个更强的 Agent，而是一个让 `loop / memory / protocol / runtime / coordination / governance` 各归其位的控制平面。**

这也是为什么作者最后会把终极验证场放在航天：

- 不是因为航天听起来酷
- 而是因为那是一个足够硬、足够不允许失败、足够依赖追溯与审计的地方
- 能把“这套控制结构到底是不是工程系统”这件事一次性验出来

---

## 12. 后续如果继续深挖，可以怎么做

### 12.1 继续拆作者这套图的三个方向

1. **把 13 个项目补成逐项卡片**
   - 每个项目一张卡：
     - 所在层
     - 解决的问题
     - 作者给它的关键词
     - 我们自己的补充判断

2. **把这套 Agent Stack 画成真正的架构图**
   - 不只是文字表述
   - 直接重画一张干净图，便于和别的 Agent 系统对照

3. **专门拆“航天验证闭环”**
   - 看作者后面真落地时，如何把：
     - 需求追溯
     - 测试报告
     - 异常初筛
     - 人审执行
     - 审计链
     串成一个真正可运行的 harness

### 12.2 对我们最适合的继续方式

如果后面你愿意，我觉得最值的一步不是继续泛泛聊，而是二选一：

- **路线 A：**
  我把这篇里的 `13 个项目 -> 5 层 Stack -> 控制职责` 直接整理成一张总表

- **路线 B：**
  我把这套 `Agent Stack` 直接映射到 Butler 当前分层，做一版“外部框架 vs 我们现状”的对照脑图

---

## 13. 参考

- George（`@odysseus0z`）《Harness Engineering Is Cybernetics》
- Norbert Wiener《Cybernetics: Or Control and Communication in the Animal and the Machine》（1948）
- Heinz von Foerster：Second-Order Cybernetics
- Cobbe et al.：Generation-Verification Asymmetry

