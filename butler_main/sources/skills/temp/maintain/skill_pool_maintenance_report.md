# Skill Pool Maintenance Report

- source skills: `40`
- legacy skills: `9`
- missing frontmatter core fields: `0`
- not exposed by any collection: `23`
- inactive or incubating skills: `13`

## Suggestions

1. 优先把长期保留的 skill 迁到 `sources/skills/pool/`。
2. 对缺少 `name/description` 的 skill 补 frontmatter。
3. 对未进入任何 collection 的 skill，判断是保留私有、加入 `skill_ops`，还是归档。
4. 对 `status=draft/incubating` 的 skill，保持不暴露，直到实现、验证和审阅完成。

## Uncollected Skills

- ./butler_main/butler_bot_agent/skills/daily-inspection
- ./butler_main/butler_bot_agent/skills/feishu-doc-sync
- ./butler_main/butler_bot_agent/skills/feishu-webhook-tools
- ./butler_main/butler_bot_agent/skills/feishu_chat_history
- ./butler_main/butler_bot_agent/skills/feishu_doc_read
- ./butler_main/butler_bot_agent/skills/proactive-talk
- ./butler_main/butler_bot_agent/skills/skill-library-explore
- ./butler_main/butler_bot_agent/skills/web-image-ocr-cn
- ./butler_main/butler_bot_agent/skills/web-note-capture-cn
- ./butler_main/sources/skills/pool/imported/magicskills-c-to-ast
- ./butler_main/sources/skills/pool/incubating/forum/discourse-api-monitor
- ./butler_main/sources/skills/pool/incubating/forum/github-discussions-graphql
- ./butler_main/sources/skills/pool/incubating/forum/hackernews-api-ingest
- ./butler_main/sources/skills/pool/incubating/forum/praw-reddit-ingest
- ./butler_main/sources/skills/pool/incubating/forum/stackexchange-api-ingest
- ./butler_main/sources/skills/pool/incubating/general/feedparser-rss-ingest
- ./butler_main/sources/skills/pool/incubating/general/reader-feed-workbench
- ./butler_main/sources/skills/pool/incubating/general/trafilatura-web-extract
- ./butler_main/sources/skills/pool/incubating/research/arxiv-py-paper-retrieval
- ./butler_main/sources/skills/pool/incubating/research/crossref-rest-metadata
- ./butler_main/sources/skills/pool/incubating/research/europepmc-rest-biomed
- ./butler_main/sources/skills/pool/incubating/research/openalex-pyalex
- ./butler_main/sources/skills/pool/incubating/research/semantic-scholar-api

## Inactive Skills

- ./butler_main/sources/skills/pool/incubating/forum/discourse-api-monitor (incubating)
- ./butler_main/sources/skills/pool/incubating/forum/github-discussions-graphql (incubating)
- ./butler_main/sources/skills/pool/incubating/forum/hackernews-api-ingest (incubating)
- ./butler_main/sources/skills/pool/incubating/forum/praw-reddit-ingest (incubating)
- ./butler_main/sources/skills/pool/incubating/forum/stackexchange-api-ingest (incubating)
- ./butler_main/sources/skills/pool/incubating/general/feedparser-rss-ingest (incubating)
- ./butler_main/sources/skills/pool/incubating/general/reader-feed-workbench (incubating)
- ./butler_main/sources/skills/pool/incubating/general/trafilatura-web-extract (incubating)
- ./butler_main/sources/skills/pool/incubating/research/arxiv-py-paper-retrieval (incubating)
- ./butler_main/sources/skills/pool/incubating/research/crossref-rest-metadata (incubating)
- ./butler_main/sources/skills/pool/incubating/research/europepmc-rest-biomed (incubating)
- ./butler_main/sources/skills/pool/incubating/research/openalex-pyalex (incubating)
- ./butler_main/sources/skills/pool/incubating/research/semantic-scholar-api (incubating)
