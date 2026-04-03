# External Skill Candidates

日期：2026-03-24  
维护者：`skill_manager_agent`

这份清单记录的不是“已经安装进 Butler 的 skill”，而是适合作为 `sources/skills` 后续引入来源的外部上游。

筛选标准：

1. 上游成熟，不是一次性 demo
2. 官方 API 或事实上的主流 client 明确存在
3. 能被包装成 Butler 的 action skill 或 passive knowledge pack
4. 风险可以在工程上控制，不需要把主 chat 绑死在单一供应商上

## 结论

如果只先做一轮最有价值的引入，优先级建议是：

1. `Trafilatura`：补齐通用网页正文抽取底座
2. `feedparser`：补齐 RSS / Atom 监控底座
3. `PRAW`：补齐 Reddit 社区信息获取
4. `Hacker News API`：补齐技术社区热帖与评论监控
5. `Stack Exchange API`：补齐技术问答检索
6. `arxiv.py`：补齐 arXiv 论文检索与 watch
7. `Semantic Scholar API`：补齐 citation / related papers 扩展
8. `OpenAlex + PyAlex`：补齐研究图谱和机构作者维度检索

## 候选清单

### 一、通用信息获取

#### 1. Trafilatura

- 上游：
  - Repo: <https://github.com/adbar/trafilatura>
  - Docs: <https://trafilatura.readthedocs.io/en/latest/>
- 建议做成：
  - `web-article-extract`
  - `forum-thread-cleanup`
  - `research-page-note`
- 优点：
  - 对网页正文抽取、清洗、元数据保留比较成熟
  - 很适合作为多个上层 skill 的共用底座
- 风险：
  - 动态加载页面仍需要浏览器回退链路
  - 需要在 Butler 输出层加来源标注
- 建议优先级：`P0`

#### 2. feedparser

- 上游：
  - Repo: <https://github.com/kurtmckee/feedparser>
  - Docs: <https://feedparser.readthedocs.io/en/latest/>
- 建议做成：
  - `rss-watch`
  - `feed-digest`
  - `source-monitor`
- 优点：
  - 足够稳定，覆盖博客、论坛公告、研究更新等多种源
  - 很适合自动化巡检与周期摘要
- 风险：
  - 只覆盖暴露 feed 的站点
  - 需要做好去重和新鲜度判断
- 建议优先级：`P0`

#### 3. reader

- 上游：
  - Repo: <https://github.com/lemon24/reader>
  - Docs: <https://reader.readthedocs.io/>
- 建议做成：
  - `feed-inbox`
  - `persistent-watchlist`
- 优点：
  - 比单纯 feedparser 更适合长期订阅和读状态管理
  - 后续能直接支撑“关注列表”类 agent 流程
- 风险：
  - 状态管理更重
  - 不适合最小 one-shot skill
- 建议优先级：`P1`

### 二、论坛 / 社区 / 讨论区

#### 4. PRAW

- 上游：
  - Repo: <https://github.com/praw-dev/praw>
  - Docs: <https://praw.readthedocs.io/en/stable/>
- 建议做成：
  - `reddit-thread-read`
  - `subreddit-watch`
  - `reddit-keyword-digest`
- 优点：
  - Reddit Python 生态里最成熟的入口之一
  - 对产品反馈、行业讨论、舆情抓取很有价值
- 风险：
  - 依赖 Reddit API 凭证与配额策略
  - 敏感内容、删除内容需要显式处理
- 建议优先级：`P0`

#### 5. Hacker News API

- 上游：
  - Official repo/docs: <https://github.com/HackerNews/API>
- 建议做成：
  - `hn-top-watch`
  - `hn-comment-brief`
  - `launch-discussion-scan`
- 优点：
  - 官方、轻量、几乎零接入门槛
  - 对开发工具、AI 产品、创业圈信号非常强
- 风险：
  - 评论树长，容易噪声过大
  - 需要关键词和排序窗口控制
- 建议优先级：`P0`

#### 6. Stack Exchange API

- 上游：
  - Official docs: <https://api.stackexchange.com/docs>
- 建议做成：
  - `stack-overflow-search`
  - `accepted-answer-fetch`
  - `tag-watch`
- 优点：
  - 技术问答密度高，适合做“问题对照检索”
  - 比通用网页搜索更可控
- 风险：
  - 需要遵守 backoff / throttle 规则
  - 必须做 site、tag、时间窗口约束
- 建议优先级：`P0`

#### 7. Discourse API

- 上游：
  - Official docs: <https://meta.discourse.org/t/discourse-rest-api-documentation/22706>
- 建议做成：
  - `discourse-topic-read`
  - `community-announcement-watch`
  - `support-forum-summarize`
- 优点：
  - 大量开发者社区、产品社区、开源论坛都跑在 Discourse 上
  - 一次打通后复用面很广
- 风险：
  - 不同站点的权限和限流差异大
  - 需要兼容不同版本和插件扩展
- 建议优先级：`P1`

#### 8. GitHub Discussions GraphQL API

- 上游：
  - Official docs: <https://docs.github.com/en/graphql/guides/using-the-graphql-api-for-discussions>
- 建议做成：
  - `github-discussions-read`
  - `repo-community-watch`
  - `maintainer-faq-extract`
- 优点：
  - 很适合开源项目支持区、路线图讨论、用户反馈整理
  - 与 codex 开发工作流天然接近
- 风险：
  - 依赖 token 和 GraphQL 查询设计
  - 访问范围受 repo 权限限制
- 建议优先级：`P1`

### 三、科研 / 论文 / 元数据

#### 9. arxiv.py

- 上游：
  - Repo: <https://github.com/lukasschwab/arxiv.py>
  - Docs: <https://lukasschwab.me/arxiv.py/>
- 建议做成：
  - `arxiv-search`
  - `arxiv-topic-watch`
  - `paper-brief-from-arxiv`
- 优点：
  - 对 arXiv 这条链路足够直接，适合先快速落地
  - ML / CS / 数学类检索价值很高
- 风险：
  - 只覆盖 arXiv
  - 如抓 PDF，要补下载策略和缓存策略
- 建议优先级：`P0`

#### 10. Semantic Scholar API

- 上游：
  - Official docs: <https://www.semanticscholar.org/product/api>
- 建议做成：
  - `paper-lookup`
  - `citation-expand`
  - `related-papers`
- 优点：
  - citation 和 related paper 方向很强
  - 适合 Butler 做“从一篇文献扩到一片文献树”
- 风险：
  - 需要先确认当前 key 与配额策略
  - 覆盖面按领域会有差异
- 建议优先级：`P0`

#### 11. OpenAlex + PyAlex

- 上游：
  - API docs: <https://docs.openalex.org/>
  - Python client: <https://github.com/J535D165/pyalex>
- 建议做成：
  - `openalex-author-lookup`
  - `institution-research-map`
  - `topic-landscape-scan`
- 优点：
  - 研究图谱维度很强，适合作者、机构、主题全景检索
  - 比单点 paper search 更适合做 research agent
- 风险：
  - API key 策略有变化，需要统一管理
  - 结果信息量大，不做过滤容易污染 prompt
- 建议优先级：`P0`

#### 12. Crossref REST API

- 上游：
  - Official docs: <https://www.crossref.org/documentation/retrieve-metadata/rest-api/>
- 建议做成：
  - `doi-enrich`
  - `reference-normalize`
  - `publisher-metadata-backfill`
- 优点：
  - 非常适合做研究 skill 底层元数据补全
  - 不一定做成面向用户的独立 skill，更像 research pipeline 的后处理组件
- 风险：
  - 不是最好的主搜索入口
  - 要注意 polite pool / client identity 规范
- 建议优先级：`P1`

#### 13. Europe PMC RESTful Web Service

- 上游：
  - Official docs: <https://europepmc.org/RestfulWebService>
- 建议做成：
  - `biomed-paper-search`
  - `preprint-watch-biomed`
  - `grant-linked-literature`
- 优点：
  - 生物医药方向很强
  - 适合做垂直 research bundle
- 风险：
  - 泛研究场景下不是第一优先
  - 更适合后续单独分 domain collection
- 建议优先级：`P1`

## 对 Butler 的落地建议

第一批建议直接做 4 个基础 skill：

1. `rss-watch`，基于 `feedparser`
2. `reddit-thread-read`，基于 `PRAW`
3. `stack-overflow-search`，基于 `Stack Exchange API`
4. `arxiv-search`，基于 `arxiv.py`

第二批建议做 3 个增强 skill：

1. `web-article-extract`，基于 `Trafilatura`
2. `hn-top-watch`，基于 `Hacker News API`
3. `paper-lookup` / `citation-expand`，基于 `Semantic Scholar API`

第三批再做研究图谱和垂直领域：

1. `openalex-author-lookup`
2. `institution-research-map`
3. `biomed-paper-search`

## 说明

本轮结论优先依据上游成熟度、官方性和 Butler 工程适配度判断。由于采集时 GitHub 在线元数据偶发超时，未把 star 数硬编码进这份清单；如后续要做更严格的“热门度”排序，建议在 `skill_manager_agent` 里补一条单独的 GitHub metadata 拉取与缓存链路。
