---
type: "note"
---
# 01D 全局 skil 与注入

日期：2026-03-23  
时间标签：0323_skill_assets_and_injection  
状态：规划中

## 目标

这份文档解决的不是“再多加几个 skill”，而是：

**给 Butler 建立一套可长期维护的 skill 资产管理与注入体系，使 chat、codex、heartbeat、orchestrator、future agent frameworks 都能复用同一份 skill 真源，但每个运行时只看到自己该看到的那一小部分。**

要点有三件事：

1. skill 资产如何统一存放、登记、升级、审计
2. 不同 agent / runtime 如何选择性暴露 skill
3. prompt / AGENTS / tool / runtime request 四种注入方式如何分层，不互相打架

## 外部参照结论

### 1. MagicSkills 的核心做法

参照 `Narwhal-Lab/MagicSkills`，它最值得借鉴的不是某个 CLI 命令，而是**三层模型**：

1. `Skill`
   一个 skill 目录，最小要求是目录下存在 `SKILL.md`
2. `Skills`
   一个 agent 真正要看到的 skill working set，不等于全量技能池
3. `REGISTRY`
   持久化的命名 collection 注册表，保存 collection 配置和 skill 路径引用，而不是拷贝 skill 内容

它的关键思想是：

1. 全局只维护一份共享 skill pool
2. 每个 agent 不直接扫全量 pool，而是绑定一个命名 collection
3. 面向不同运行时，暴露方式不同：
   - 会读 `AGENTS.md` 的 agent：把 collection 同步进 `AGENTS.md`
   - 不读 `AGENTS.md` 的 framework：暴露一个稳定的 tool API

MagicSkills 还明确提供了两种 sync 模式：

1. `none`
   把 `<usage> + <available_skills>` 直接写进 `AGENTS.md`
2. `cli_description`
   不直接展开 skills，而是告诉 agent 通过统一 CLI 入口 `skill-tool` 去 list/read/exec

对 Butler 最重要的启发是：

**skill 真源、agent 可见子集、运行时注入方式，这三件事必须拆开。**

参考：

1. `MagicSkills` README：<https://github.com/Narwhal-Lab/MagicSkills>
2. `How It Works` / object model / registry / syncskills：同 README 中对应章节
3. Cursor / Codex 示例目录：
   - <https://github.com/Narwhal-Lab/MagicSkills/tree/main/Cursor_example>
   - <https://github.com/Narwhal-Lab/MagicSkills/tree/main/Codex_example>

### 2. Vercel 的反向经验

Vercel 最近做了一个很重要的结论：

**通用框架知识，`AGENTS.md` 被动上下文往往比“等模型自己触发某个 skill”更稳。**

他们的评测里：

1. skill 默认触发时，效果几乎没有提升
2. 明确告诉模型“先用 skill”会有提升，但提示词很脆弱
3. 把一个压缩后的 docs index 直接放到 `AGENTS.md`，结果最稳定

这说明一件事：

**“技能注入”不能只有一种。**

应该至少区分：

1. 被动常驻知识注入
2. 主动调用型 action skill 注入

参考：

1. Agent Skills：<https://vercel.com/docs/agent-resources/skills>
2. AGENTS.md outperforms skills：<https://vercel.com/blog/agents-md-outperforms-skills-in-our-agent-evals>

## 当前 Butler 的现状问题

### 1. 资产层问题

当前 skill 真源基本都在：

`./butler_main/butler_bot_agent/skills/`

但系统只有“目录扫描 + prompt 文本渲染”，还没有真正的：

1. collection registry
2. per-agent exposure contract
3. 统一 metadata 审计标准
4. 全局 skill 生命周期管理

### 2. 注入层问题

当前 chat 的技能注入本质上是：

1. 每轮扫描所有 `SKILL.md`
2. 生成一个 catalog shortlist
3. 塞进 prompt
4. 靠模型自己判断是否命中，再去读对应 `SKILL.md`

这有几个问题：

1. 只按目录全量扫描，没有 agent 视角的精选子集
2. `max_skills` 和 `max_chars` 都是渲染层阈值，不是资产分发层 contract
3. codex chat prompt 目前并没有对齐这套 skills 注入逻辑
4. 一部分知识其实更适合常驻 AGENTS / bootstrap，不适合伪装成 skill
5. 真正执行型 skill 和只是“知识索引/使用建议”的 skill 混在一起

### 3. 运行时问题

当前系统里，已经出现三种不同的 skill 使用方式，但还没有被统一命名：

1. `chat`
   catalog shortlist 注入
2. `heartbeat / orchestration`
   当 branch 指定 `skill_name/skill_dir/requires_skill_read=true` 时，直接读取目标 `SKILL.md` 全文硬注入
3. 一些外部框架接入场景
   未来需要 tool / function-call 风格，而不是 prompt 文本扫描

当前缺的是：

**一个统一的“skill exposure plane”。**

## 总体方案

## 一句话方案

Butler 的 skill 体系改成：

**全局 skill pool + 命名 collection registry + 四层注入模式 + 统一元数据治理。**

## 一、资产分层

### A. DNA 核心层

这些不是 skill，永远不要放进 skill pool：

1. 身体运行
2. 灵魂 / SOUL
3. 记忆
4. chat 主链
5. heartbeat 主流程
6. orchestrator 控制面

它们属于：

1. bootstrap
2. AGENTS / role / prompt
3. runtime core code

### B. Passive Knowledge Pack 层

这类不是 action skill，而是：

1. 长期知识索引
2. 文档导航
3. 压缩版 retrieval index
4. 规则型上下文

它们应该注入到：

1. `AGENTS.md` / bootstrap docs block
2. runtime 固定 prompt block

而不是出现在“请先去调用 skill”那类短名单里。

典型例子：

1. 某框架 docs index
2. 项目结构索引
3. 团队编码规范索引
4. 常用工作流路由索引

### C. Action Skill 层

这才是 skill 主体：

1. 有明确触发条件
2. 有明确输入输出
3. 有 `SKILL.md`
4. 可以读取 references / scripts / assets
5. 命中后应先读 `SKILL.md` 再执行

比如：

1. 飞书文档读取
2. 飞书历史消息导出
3. OCR
4. 网页抓取
5. 轻量 webhook 推送
6. 日常巡检流程

### D. Tool-Exposed Capability 层

有些 skill 最终应该再对外包成稳定工具接口：

1. `list`
2. `read`
3. `exec`
4. `validate`

它们服务于：

1. future MCP
2. function-calling framework
3. codex/cursor 之外的多 agent runtime

## 二、目录与元数据规范

### 目录真源

建议维持一个全局真源根：

`./butler_main/butler_bot_agent/skills/`

按分类子目录组织：

1. `feishu/`
2. `web/`
3. `ocr/`
4. `research/`
5. `ops/`
6. `delivery/`
7. `workflow/`

每个 skill 至少包含：

1. `SKILL.md`
2. 可选 `references/`
3. 可选 `scripts/`
4. 可选 `assets/`
5. 可选 `tests/`

### frontmatter 标准字段

建议统一扩展到以下字段：

1. `name`
2. `description`
3. `category`
4. `trigger_examples`
5. `allowed_runtimes`
   例如 `chat,codex,heartbeat,orchestrator`
6. `allowed_channels`
   例如 `feishu,weixi,cli`
7. `risk_level`
   `low/medium/high`
8. `requires_skill_read`
9. `heartbeat_safe`
10. `tool_ready`
11. `tool_actions`
    例如 `list,read,exec`
12. `default_exposure`
    例如 `none/shortlist/passive_index/direct_bind`
13. `owner`
14. `reviewed_at`
15. `version`
16. `deps`
17. `tags`

## 三、Registry 设计

### 新增全局 registry

建议新增：

`./butler_main/agents_os/registry/skill_collections.json`

它不存 skill 正文，只存：

1. collection 名
2. collection 中 skill 路径列表
3. 注入模式
4. 默认目标 agent/runtime
5. 默认 AGENTS / prompt sync 目标
6. tool description
7. cli description

### collection 示例

建议至少拆成以下 collection：

1. `chat_default`
   面向普通 chat 主链的 action shortlist
2. `chat_content_share`
   只保留抓取 / OCR / doc / note 相关
3. `chat_feishu_ops`
   飞书写回、历史记录、文档同步、主动提醒
4. `codex_default`
   只保留真正需要 code/runtime 执行的 action skill
5. `heartbeat_safe`
   仅 heartbeat-safe 且可后台自主运行的 skills
6. `research_default`
   研究/抓取/整理向 skills
7. `orchestrator_delivery`
   只保留交付和同步类 skills

### collection 的意义

从现在开始，不再让 agent 直接“看到所有 skills”，而是：

**每个 runtime 先绑定 collection，再渲染/注入。**

这样能解决：

1. chat 上下文噪声
2. heartbeat 误用高风险 skill
3. codex prompt 和普通 chat prompt 注入不一致
4. 同一 skill 在多 agent 里暴露方式不同

## 四、四层注入模型

### 模式 1：Passive Index 注入

适合：

1. 通用知识
2. 文档索引
3. 项目规范
4. 长期稳定规则

注入位置：

1. bootstrap block
2. `AGENTS.md`
3. 常驻 prompt header

特点：

1. 被动存在
2. 不要求模型做“要不要触发”的决策
3. 适合 Vercel 证明过更稳的那类场景

### 模式 2：Shortlist 注入

适合：

1. action skill 候选清单
2. 用户未点名 skill，但明显触发 skill 语义

注入位置：

1. chat prompt
2. codex prompt
3. planner prompt

要求：

1. 只注入 collection 子集
2. 不再从全量 pool 直接渲染
3. 文本应尽量短，保留 name + description + trigger + risk

### 模式 2.5：Family 折叠 + 二级检索

当一个 collection 内部的 leaf skill 继续增多时，不应继续把 shortlist 做成“平铺 skill 名单 + 硬截断”。

建议新增一层：

1. `skill family`
2. `leaf skill`

运行时策略改成：

1. 一级暴露只展示 family shortlist
2. family 命中后，再在该 family 内二级检索 leaf skill
3. 真正注入正文时，仍然只 direct bind 单个 leaf skill 的 `SKILL.md`

这样有几个好处：

1. prompt 不再因为 collection 内 skill 数量变大而线性膨胀
2. 相似 skill 可以在 exposure 层折叠，而不是强行物理合并
3. risk / 审计 / `requires_skill_read` 仍然保持在 leaf 粒度
4. agent 先判断“我需要哪一族能力”，再判断“这一族里具体用哪个 skill”

推荐元数据字段：

1. `family_id`
2. `family_label`
3. `family_summary`
4. `family_trigger_examples`
5. `variant_rank`

这套机制应优先落在：

1. `runtime_catalog`
2. `skill_tool(search/expand/read)`
3. prompt shortlist 渲染

而不是先去把多个相似 skill 物理合并成一个超大 `SKILL.md`。

### 模式 3：Direct Bind 注入

适合：

1. planner 已经选定某 skill
2. branch 元数据显式要求 `requires_skill_read=true`

注入方式：

1. 直接读取目标 `SKILL.md`
2. 拼接成 `【本轮指定 skill】`
3. 未找到则 fail fast

这就是现在 heartbeat branch 已经在做的事，应当扩成全局规范。

### 模式 4：Tool API 注入

适合：

1. 不稳定依赖 prompt 触发的场景
2. 多 agent framework
3. function call / MCP / runtime executor

统一入口建议叫：

`skill_tool(action, name, arg, collection, runtime_context)`

最小 action：

1. `list`
2. `search`
3. `expand`
4. `read`
5. `show`
6. `exec`

## 五、不同运行时的注入矩阵

### Chat（普通问答）

1. 常驻：
   passive index
2. 按轮：
   `chat_default` shortlist
3. 命中后：
   direct bind 读目标 `SKILL.md`

### Chat（内容转发 / 网页分享）

1. 常驻：
   passive docs index
2. 按轮：
   `chat_content_share` shortlist
3. 命中后：
   direct bind

### Chat（Codex prompt 路线）

当前最大缺口是：

**codex chat prompt 没有对齐普通 chat 的 skills 注入。**

建议改成：

1. 保留 codex 的轻量 prompt
2. 但仍注入 `codex_default` shortlist
3. 当用户明确说“用 skill/调用技能/抓取/OCR/飞书文档”时，强提醒 direct bind

### Heartbeat

heartbeat 不能看到全量 skill。

建议只暴露：

1. `heartbeat_safe` collection
2. 严格过滤 `risk_level != low/medium`
3. 禁止未审计 script 型 skill 自动执行

heartbeat 中 planner 可以看到 shortlist，但 executor 必须只吃已经选中的 direct bind skill。

### Orchestrator

orchestrator 不应自己“模糊调用 skill”，而应：

1. planner / node 产出 `capability_id`
2. 绑定 collection
3. executor 执行 direct bind 或 tool call

### Future 多 Agent Framework

对于 LangGraph / CrewAI / smolagents 这类：

1. 不再依赖 prompt 让模型自己想起 skill
2. 直接挂统一 `skill_tool()`
3. 把 collection 作为 tool 的 scope

## 六、Prompt 结构建议

### chat prompt 中 skill block 的标准格式

建议统一成两段：

1. `【可复用 Action Skills】`
2. `【本轮指定 Skill】`

第一段只放 shortlist，第二段只在命中后出现。

### shortlist 建议字段

如果 collection 规模仍较小，每项保留：

1. `name`
2. `path`
3. `一句话 description`
4. `trigger_examples`
5. `risk_level`

不要在 shortlist 里塞大段说明；真正长说明只在 direct bind 时注入。

如果 collection 已经开始膨胀，则把 shortlist 升级为 family 视图，每项改成：

1. `family_label`
2. `family_id`
3. `family_summary`
4. `member_count`
5. `代表性 trigger_examples`
6. `聚合 risk_level`

leaf skill 只在二级检索时展开，不在一级 prompt 中平铺。

### skill 注入词的真源

这部分不应继续散落在：

1. chat prompt block
2. codex prompt block
3. heartbeat extras
4. 各 agent 自己手写的 prompt 提示

建议统一收敛到 skill 池侧真源，例如：

`./butler_main/sources/skills/collections/prompt_policy.json`

由 skill 池侧维护：

1. shortlist 的统一前置说明
2. “命中后先读 `SKILL.md`”这类硬规则
3. family / 二级检索的提示语
4. heartbeat 等 runtime 的附加补充词

然后 chat / codex / heartbeat 只做：

1. 读取统一 policy
2. 按 runtime 选择 collection
3. 必要时追加极少量 runtime-specific override

这样可以避免：

1. 每个 agent 都维护一份 skill 注入词
2. 后续 family 折叠上线后，各处文案继续使用旧“平铺 skill”口径
3. chat / codex / heartbeat 三套规则慢慢漂移

### passive index 建议字段

保留：

1. index root
2. retrieval guidance
3. 压缩后的目录映射
4. 一条强制性指令

例如：

`IMPORTANT: 对框架/产品特定知识优先 retrieval-led reasoning，不要只依赖预训练记忆。`

## 七、安全与治理

### 审计等级

每个 skill 至少要标：

1. `risk_level`
2. `heartbeat_safe`
3. `tool_ready`
4. `reviewed_at`
5. `owner`

### 执行权限

高风险 skill 不得被：

1. heartbeat 自动执行
2. 未审计 planner 自动选择
3. 未经 direct bind 就执行

### 变更治理

新增或修改 skill 时必须同步：

1. `SKILL.md`
2. metadata
3. collection membership
4. 测试
5. 注入策略

## 八、Butler 的具体落地结构

### 资产目录

保留：

`./butler_main/butler_bot_agent/skills/`

新增建议：

1. `./butler_main/sources/skills/collections/registry.json`
2. `./butler_main/sources/skills/collections/prompt_policy.json`
3. `./butler_main/agents_os/skills/runtime_catalog.py`
4. `./butler_main/agents_os/skills/collection_registry.py`
5. `./butler_main/agents_os/skills/injection_policy.py`
6. `./butler_main/agents_os/skills/skill_tool.py`

### chat 接入点

1. `chat/prompt_support/skills.py`
   从“全量扫描渲染”升级为“按 collection 渲染”
2. `chat/prompting.py`
   新增 passive index block 和 direct bind block
3. `chat/runtime.py`
   根据 route / mode / cli 决定 collection
4. `chat/engine.py`
   codex prompt 路线对齐 skill exposure

### heartbeat / orchestrator 接入点

1. planner
   只看 shortlist
2. executor
   只吃 direct bind / tool call
3. registry
   作为唯一 collection 真源

## 九、推荐的 collection 初版

### `chat_default`

包含：

1. 飞书历史
2. 飞书文档读写
3. OCR
4. 网页抓取
5. 轻量通知

不包含：

1. 日常巡检
2. 主动提醒
3. heartbeat 专属能力

### `chat_content_share`

包含：

1. `web-note-capture-cn`
2. `web-image-ocr-cn`
3. `feishu-doc-read`
4. `feishu-doc-sync`

### `codex_default`

包含：

1. 真正需要 code/runtime 调度的技能
2. 较短的 shortlist

不包含：

1. 纯知识型 docs index
2. heartbeat 独占技能

### `heartbeat_safe`

只允许：

1. `heartbeat_safe=true`
2. `risk_level in {low, medium}`
3. 无 destructive side effect

## 十、0323 当天执行建议

### P0 今天必须完成

1. 把 `chat` 的 skills 渲染从“全量目录扫描直出”改成“按 collection 输出”
2. 新增 `sources/skills/collections/registry.json`
3. 新增 `sources/skills/collections/prompt_policy.json`
4. 给 `chat_default / chat_content_share / codex_default / heartbeat_safe` 建第一版 collection
5. codex prompt 路线补齐 skills 注入
6. 把 passive index 和 action skill 从概念上分开
7. shortlist 从“平铺 leaf skill”升级为“family 折叠 + 命中后二级检索”

### P1 今天如果还有时间

1. 新增统一 `skill_tool()` 入口
2. heartbeat executor 改成只吃 direct bind / tool call
3. 为高风险 skill 加审计字段校验

### P2 不是今天必须

1. MCP 封装
2. 自动生成 AGENTS skill block
3. 外部 skill 仓库同步/安装器

## 最终结论

Butler 下一步不应该继续把“skills = 一堆 `SKILL.md` 目录 + prompt shortlist”这条线补补缝缝。

应该正式升级为：

**全局 skill pool + collection registry + prompt policy + passive index + family shortlist + direct bind + tool API 的七层体系。**

其中最关键的两条原则是：

1. **不要让每个 agent 直接看到全量 skills**
2. **不要把所有知识都包装成 skill；通用知识应优先进入 AGENTS / bootstrap 被动上下文**

再补一条运行时原则：

3. **不要把一级注入继续做成平铺 skill 清单；应优先折叠成 family，并在命中后支持二级检索**

这两条一旦固定，chat、codex、heartbeat、orchestrator、future frameworks 才能共用同一套 skill 资产，而不会继续各自长歪。
