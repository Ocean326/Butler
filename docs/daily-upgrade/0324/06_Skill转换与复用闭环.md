---
type: "note"
---
# 06 Skill 转换与复用闭环

日期：2026-03-24  
状态：已落地

## 目标

把“外部候选 skill 只是放进 incubating”推进到下一步：

1. 真正转成可执行 skill
2. 纳入 `skill_manager_agent` 的管理范围
3. 明确“命中未转换 skill 时，先转换，再复用，再使用”

## 本轮落地

### 1. 新增转换管理能力

新增 ops skill：

1. `sources/skills/pool/ops/skill-incubating-promote`

作用：

1. 从 `incubating` 候选生成 active skill
2. 生成 `SKILL.md`、`references/upstream.md`、`scripts/run.py`
3. 写入转换状态 registry

### 2. 新增转换状态真源

新增：

1. `sources/skills/agent/skill_manager_agent/references/upstream_skill_conversion_registry.json`

这个文件现在承担：

1. 某个候选是否已经 active
2. active skill 路径是什么
3. 是否支持自动 promotion
4. 若不支持，为什么还停留在 incubating

### 3. 新增 12 个 active 可执行 skill

已从 incubating 提升为 active：

1. `general/web-article-extract`
2. `general/rss-feed-watch`
3. `forum/reddit-thread-read`
4. `forum/hackernews-thread-watch`
5. `forum/stackexchange-search`
6. `forum/discourse-topic-read`
7. `forum/github-discussions-read`
8. `research/arxiv-search`
9. `research/semantic-scholar-search`
10. `research/openalex-search`
11. `research/crossref-doi-enrich`
12. `research/europepmc-search`

仍未自动转换：

1. `reader-feed-workbench`

原因：

1. 它更偏持久化订阅工作台，不是简单单次查询型 skill
2. 当前没有合适的 auto-template，保留为 `incubating_manual`

### 4. 新增共享运行时

新增：

1. `sources/skills/shared/upstream_source_runtime.py`

作用：

1. 统一承接这些外部信息源 skill 的 HTTP / parse / output 逻辑
2. 每个 active skill 只需自己的 wrapper script
3. 避免 12 个 skill 各自拷一份近似代码

## skill agent 的新策略

`skill_manager_agent` 现在默认遵循：

1. 先查 `upstream_skill_conversion_registry.json`
2. 如果已是 active skill，优先复用
3. 如果还是 incubating 且支持自动 promotion，先调用 `skill-incubating-promote`
4. promotion 完成后再执行 active skill
5. 如果不支持自动 promotion，明确返回“需要人工实现”

这意味着：

**skill agent 不再只会搜候选和导入，而是开始具备“补齐能力缺口并沉淀复用资产”的闭环。**

## collection 暴露面

本轮还做了两件事：

1. 把 `skill-incubating-promote` 纳入 `skill_ops`
2. 新增 `upstream_active` collection

同时把一部分低风险高频 skill 暴露进：

1. `chat_default`
2. `codex_default`
3. `heartbeat_safe`

## 验证结果

### 测试

已通过：

1. `test_skill_registry.py`
2. `test_agents_os_skill_tool.py`
3. `test_skill_manager_agent_bundle.py`
4. `test_skill_upstream_registry.py`

### 实跑

已实际执行通过：

1. `rss-feed-watch`
2. `hackernews-thread-watch`
3. `stackexchange-search`
4. `arxiv-search`

### 资产校验

1. `skill-pool-maintain`：`inventory=49`
2. `skill-pool-verify`：`verified_skills=62`，`issue_count=0`

## 结论

这一轮之后，Butler 的 skill 体系已经从：

1. 搜候选
2. 导入候选

推进到：

1. intake 候选
2. 维护 incubating 池
3. promotion 成 active skill
4. 通过 conversion registry 控制后续复用

也就是说，“命中未转换 skill 就先转换，之后复用”的基础机制已经落地了。
