# Butler Skills Index

本文件只负责 **skills 目录索引、分类入口与放置约定**。

什么时候必须/优先使用 skill、调用前必须做什么、如何透明说明本次用了哪个 skill，这些统一规则都以 `./butler_bot_agent/skills/skills.md` 为真源；不要把两份文档写成两套总则。

Butler 的 skills 只承载可插拔、可复用、可配置的外部能力，不承载 DNA 核心能力。

## DNA 边界

- 身体运行：飞书消息循环、主进程生命周期、运行时日志。
- 灵魂：角色基线、气质、长期人格锚点。
- 记忆：recent/local/长期记忆的读写、整理、压缩。
- 心跳：规划、调度、心跳执行、基础自维护。

以上仍留在 `butler_bot_code/`，不要抽成 skill。

## 适合放进 skills 的能力

- 飞书外围能力：历史消息、文档检索、群/会话工具。
- 外部平台能力：小红书、网页资料抓取、第三方系统操作。
- 复用型流程能力：巡检、导出、批处理、资料整理套路。

## 分类约定

新增 skill 优先采用分类子目录：

- `feishu/`：飞书相关外围能力
- `operations/`：巡检、运维、治理、批处理流程
- `research/`：调研、资料抓取、平台采集
- `general/`：暂时无法归类的通用能力

当前仓库仍兼容历史扁平布局；主代码会按 `SKILL.md` 的 `category` 字段或目录名自动归类。

## 当前目录索引

- `daily-inspection/`：每日启动与收口巡检流程。
- `feishu-webhook-tools/`：Webhook 推送与轻量脚本化通知。
- `feishu_chat_history/`：飞书历史会话获取、导出与分页拉取。
- `openclaw-find-skills/`：从 OpenClaw/Skills.sh 生态查找技能并给出安装命令（内化自 OpenClaw skill-finder 流程）。
- `proactive-talk/`：心跳主动沟通与 tell_user 类流程。
- `xiaohongshutools/`：小红书相关抓取与交互能力。

新增或迁移 skill 时，优先更新本索引与对应目录的 `SKILL.md`，而不是在多个 role 文档里重复登记一遍。

## Skill 入口约定

每个 skill 目录至少包含：

- `SKILL.md`：能力说明、适用场景、配置来源
- 可选代码文件：脚本或 Python 模块
- 可选 `reference.md`：API、细节、注意事项

目标是让主代码只需要知道：有哪些 skills、各自做什么、何时调用；而不是把外部能力继续塞回核心运行时代码。