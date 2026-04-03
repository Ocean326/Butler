---
name: semantic-scholar-api
description: Incubating Butler wrapper spec for upstream 'Semantic Scholar API'.
category: research
trigger_examples: 查论文, 扩citation, 跟踪研究主题
allowed_roles: feishu-workstation-agent, butler-continuation-agent, orchestrator-agent
risk_level: medium
automation_safe: false
requires_skill_read: true
status: incubating
upstream_name: Semantic Scholar API
upstream_type: official_api
review_priority: P0
---
# Semantic Scholar API

## Status

- `incubating`
- 这不是生产可执行 skill，而是 Butler 对外部上游的包装草案。
- 默认不得加入 `chat_default` / `codex_default` / `automation_safe`。

## Proposed Butler Shape

- paper lookup, citation graph hops, author impact summary, related-paper expansion

## Upstream

- repo_or_entry: https://www.semanticscholar.org/product/api
- docs: https://www.semanticscholar.org/product/api
- upstream_type: official_api
- maturity: high

## Why This Matters

- Good balance between scholarly metadata richness and agent-friendly API shape.
- Useful when Butler needs citation expansion instead of simple keyword search.

## Risks

- Quota and API-key policy must be checked before automation.
- Coverage varies by field and source.

## Suggested Future Exposure

- chat_default
- skill_ops

## Implementation Checklist

- 明确 Butler 输入输出 contract，不直接复刻上游 API。
- 确认认证、限流、缓存和错误恢复策略。
- 补执行脚本或 tool bridge，而不是只停留在说明文档。
- 补测试与 `skill-pool-verify` / `skill-pool-maintain` 校验。
- 审阅后再决定是否加入 collection registry。

