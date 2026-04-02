---
name: openalex-pyalex
description: Incubating Butler wrapper spec for upstream 'OpenAlex plus PyAlex'.
category: research
trigger_examples: 查论文, 扩citation, 跟踪研究主题
allowed_roles: feishu-workstation-agent, butler-continuation-agent, orchestrator-agent
risk_level: medium
automation_safe: false
requires_skill_read: true
status: incubating
upstream_name: OpenAlex plus PyAlex
upstream_type: official_api_with_client
review_priority: P0
---
# OpenAlex plus PyAlex

## Status

- `incubating`
- 这不是生产可执行 skill，而是 Butler 对外部上游的包装草案。
- 默认不得加入 `chat_default` / `codex_default` / `automation_safe`。

## Proposed Butler Shape

- institution and author lookup, work graph traversal, topic and concept monitoring

## Upstream

- repo_or_entry: https://github.com/J535D165/pyalex
- docs: https://docs.openalex.org/
- upstream_type: official_api_with_client
- maturity: high

## Why This Matters

- Broad and modern scholarly graph with practical Python wrapper support.
- Best candidate when Butler needs research landscape mapping, not just single-paper lookup.

## Risks

- Recent API-key changes mean Butler should centralize credentials and retry policy.
- Result richness can increase prompt noise if not post-filtered.

## Suggested Future Exposure

- skill_ops
- automation_safe

## Implementation Checklist

- 明确 Butler 输入输出 contract，不直接复刻上游 API。
- 确认认证、限流、缓存和错误恢复策略。
- 补执行脚本或 tool bridge，而不是只停留在说明文档。
- 补测试与 `skill-pool-verify` / `skill-pool-maintain` 校验。
- 审阅后再决定是否加入 collection registry。

