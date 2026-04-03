---
name: crossref-rest-metadata
description: Incubating Butler wrapper spec for upstream 'Crossref REST API'.
category: research
trigger_examples: 查论文, 扩citation, 跟踪研究主题
allowed_roles: feishu-workstation-agent, butler-continuation-agent, orchestrator-agent
risk_level: medium
automation_safe: false
requires_skill_read: true
status: incubating
upstream_name: Crossref REST API
upstream_type: official_api
review_priority: P1
---
# Crossref REST API

## Status

- `incubating`
- 这不是生产可执行 skill，而是 Butler 对外部上游的包装草案。
- 默认不得加入 `chat_default` / `codex_default` / `automation_safe`。

## Proposed Butler Shape

- DOI metadata enrichment, reference normalization, publisher-source backfill

## Upstream

- repo_or_entry: https://www.crossref.org/documentation/retrieve-metadata/rest-api/
- docs: https://www.crossref.org/documentation/retrieve-metadata/rest-api/
- upstream_type: official_api
- maturity: high

## Why This Matters

- Excellent utility layer for cleaning and enriching paper metadata from other sources.
- Very useful as a behind-the-scenes helper skill rather than a user-facing standalone skill.

## Risks

- Not ideal as the only search experience.
- Needs polite client identification and cache discipline.

## Suggested Future Exposure

- skill_ops

## Implementation Checklist

- 明确 Butler 输入输出 contract，不直接复刻上游 API。
- 确认认证、限流、缓存和错误恢复策略。
- 补执行脚本或 tool bridge，而不是只停留在说明文档。
- 补测试与 `skill-pool-verify` / `skill-pool-maintain` 校验。
- 审阅后再决定是否加入 collection registry。

