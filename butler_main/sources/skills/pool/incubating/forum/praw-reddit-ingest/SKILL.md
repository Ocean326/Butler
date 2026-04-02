---
name: praw-reddit-ingest
description: Incubating Butler wrapper spec for upstream 'PRAW'.
category: forum
trigger_examples: 看论坛热帖, 拉评论树, 社区舆情
allowed_roles: feishu-workstation-agent, butler-continuation-agent, orchestrator-agent
risk_level: medium
automation_safe: false
requires_skill_read: true
status: incubating
upstream_name: PRAW
upstream_type: open_source_library
review_priority: P0
---
# PRAW

## Status

- `incubating`
- 这不是生产可执行 skill，而是 Butler 对外部上游的包装草案。
- 默认不得加入 `chat_default` / `codex_default` / `automation_safe`。

## Proposed Butler Shape

- Reddit thread search, subreddit watch, comment tree retrieval, discussion digest

## Upstream

- repo_or_entry: https://github.com/praw-dev/praw
- docs: https://praw.readthedocs.io/en/stable/
- upstream_type: open_source_library
- maturity: high

## Why This Matters

- Most mature Python entrypoint for Reddit-based forum retrieval.
- Strong fit for market sentiment, product feedback, and community monitoring.

## Risks

- Depends on Reddit API credentials and quota policy.
- Moderation removals and NSFW boundaries need explicit handling.

## Suggested Future Exposure

- skill_ops

## Implementation Checklist

- 明确 Butler 输入输出 contract，不直接复刻上游 API。
- 确认认证、限流、缓存和错误恢复策略。
- 补执行脚本或 tool bridge，而不是只停留在说明文档。
- 补测试与 `skill-pool-verify` / `skill-pool-maintain` 校验。
- 审阅后再决定是否加入 collection registry。

