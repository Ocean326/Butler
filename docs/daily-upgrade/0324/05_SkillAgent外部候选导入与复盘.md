---
type: "note"
---
# 05 SkillAgent 外部候选导入与复盘

日期：2026-03-24
状态：已落地

## 这次做了什么

这次不是继续补“搜到一个 skill 仓库就拉下来”，而是把 `skill_manager_agent` 对外部能力的 intake 路径补完整了：

1. 对已经是 `SKILL.md` 结构的外部仓库，继续走 `skill-github-import`
2. 对只是 API / library / 官方 docs 的候选，不再硬塞进 `pool/imported`
3. 新增 `skill-upstream-intake-review`，把这类候选落成 `sources/skills/pool/incubating/` 下的草案 skill 资产
4. 给 runtime / maintain / verify 补了 `status=incubating` 治理逻辑

## 本轮实际结果

已把 13 个外部候选导入为 incubating 资产：

1. 通用信息获取
   - `trafilatura-web-extract`
   - `feedparser-rss-ingest`
   - `reader-feed-workbench`
2. 论坛 / 社区
   - `praw-reddit-ingest`
   - `hackernews-api-ingest`
   - `stackexchange-api-ingest`
   - `discourse-api-monitor`
   - `github-discussions-graphql`
3. 科研
   - `arxiv-py-paper-retrieval`
   - `semantic-scholar-api`
   - `openalex-pyalex`
   - `crossref-rest-metadata`
   - `europepmc-rest-biomed`

每个候选现在都有：

1. `SKILL.md`
2. `UPSTREAM_REVIEW.md`
3. `UPSTREAM_INTAKE.json`

总览报告产物：

1. `butler_main/sources/skills/temp/upstream-review/skill_upstream_intake_report.md`
2. `butler_main/sources/skills/temp/upstream-review/skill_upstream_intake_report.json`

## 复盘结论

### 1. 原来的 skill agent 有一个结构性缺口

原先只有：

1. 搜候选
2. 导 GitHub skill 仓库
3. 盘点与校验

但缺了中间这层：

**“候选不是 skill 仓库，只是一个值得包装的上游能力时，怎么落成本地可审阅资产。”**

这会直接导致两个坏结果：

1. 要么停留在口头 shortlist，无法进入 skill 真源
2. 要么把非 skill 仓库硬导进 `pool/imported`，污染资产边界

### 2. 这次补的改进是对的

补完后，skill agent 现在有 4 种明确动作：

1. `search`：候选搜索与 shortlist
2. `github-import`：导入现成 skill 仓库
3. `upstream-intake-review`：把 API/library/docs 候选转成 incubating skill 草案
4. `maintain/verify`：治理与校验

这让 `sources/skills` 里第一次出现了清晰的生命周期：

1. candidate shortlist
2. incubating
3. implemented
4. collection exposure

### 3. 运行时还需要的保护已经补了一半

如果只把 incubating 资产放进 `sources/skills/pool/`，但不做运行时过滤，会有两个风险：

1. 全量扫描 catalog 时把草案 skill 误当成可见 skill
2. 后面有人手滑把草案放进 collection，却没人告警

本轮已补：

1. runtime catalog 默认跳过 `status in {draft, incubating, archived, disabled, private}` 的 skill
2. `skill-pool-maintain` 会显式统计 inactive/incubating
3. `skill-pool-verify` 会对 collection 中暴露了 inactive skill 的情况报错

## 目前 skill agent 的能力边界

现在的 `skill_manager_agent` 已经可以：

1. 管理 skill 真源和 collection registry 的分离
2. 处理外部候选搜索、GitHub skill 导入、API/library intake、维护、校验
3. 生成适合 talk / orchestrator 继续消费的冷数据和报告

但它还不能自动做：

1. 根据 incubating skill 自动生成执行脚本
2. 自动跑第三方依赖可用性验证
3. 自动产出 registry patch 并附带风险评分
4. 在 talk / orchestrator 里按用户意图自动切到 `skill_manager_agent`

## 下一步建议

优先级最高的是 3 件事：

1. 给 `skill_manager_agent` 增加“incubating -> implemented”的脚手架生成能力
2. 把 talk / orchestrator 接上 `skill_manager_agent` profile 路由
3. 对第一批 P0 候选先实现 4 个真实 skill：
   - `feedparser-rss-ingest`
   - `praw-reddit-ingest`
   - `stackexchange-api-ingest`
   - `arxiv-py-paper-retrieval`

## 一句话结论

这次不是简单多了 13 个候选，而是把 skill agent 从“会搜、会导”推进到了“会 intake、会审阅、会隔离草案状态”的阶段。下一步应该从 incubating 里挑 P0 候选，开始生成真正可执行的 Butler skill。
