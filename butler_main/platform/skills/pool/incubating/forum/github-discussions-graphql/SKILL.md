---
name: github-discussions-graphql
description: Incubating Butler wrapper spec for upstream 'GitHub Discussions GraphQL API'.
category: forum
trigger_examples: 看论坛热帖, 拉评论树, 社区舆情
allowed_roles: feishu-workstation-agent, butler-continuation-agent, orchestrator-agent
risk_level: medium
automation_safe: false
requires_skill_read: true
status: incubating
upstream_name: GitHub Discussions GraphQL API
upstream_type: official_api
review_priority: P1
---
# GitHub Discussions GraphQL API

## Status

- `incubating`
- 这不是生产可执行 skill，而是 Butler 对外部上游的包装草案。
- 默认不得加入 `chat_default` / `codex_default` / `automation_safe`。

## Proposed Butler Shape

- GitHub Discussions retrieval, maintainer FAQ extraction, release-feedback watch

## Upstream

- repo_or_entry: https://docs.github.com/en/graphql/guides/using-the-graphql-api-for-discussions
- docs: https://docs.github.com/en/graphql/guides/using-the-graphql-api-for-discussions
- upstream_type: official_api
- maturity: high

## Why This Matters

- Strong fit for open-source product support and maintainer communication channels.
- Complements issues and changelog monitoring already common in coding workflows.

## Risks

- Requires GitHub token and GraphQL query discipline.
- Per-repo permissions limit broad public crawling.

## Suggested Future Exposure

- codex_default

## Implementation Checklist

- 明确 Butler 输入输出 contract，不直接复刻上游 API。
- 确认认证、限流、缓存和错误恢复策略。
- 补执行脚本或 tool bridge，而不是只停留在说明文档。
- 补测试与 `skill-pool-verify` / `skill-pool-maintain` 校验。
- 审阅后再决定是否加入 collection registry。

