# 动态 Agent 注册表

## 使用场景

当出现以下情况时，可新增 Agent：
- 某类任务持续超过每周 3 次且已有 Agent 负载过高
- 新任务需要专门方法论（如基金申报、专利布局、图表美化）
- 现有职责边界频繁冲突

## 新增流程（由飞书工作站执行）

1. 定义新 Agent 的唯一职责与边界
2. 创建文件：`agents/sub-agents/<new_agent_name>.md`（合并 ROLE_SPEC、rules、REFLECTION_LOG 模板）
3. 更新：`docs/AGENTS_ARCHITECTURE.md`、`docs/AGENT_SPECS_AND_PROMPTS.md`
4. 发布生效说明（变更原因 + 使用方式）

## 注册模板

| 字段 | 内容 |
|---|---|
| agent_name |  |
| role |  |
| responsibilities |  |
| in_scope |  |
| out_of_scope |  |
| handoff_to |  |
| created_at |  |
