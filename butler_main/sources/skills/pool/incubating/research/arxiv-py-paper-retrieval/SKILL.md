---
name: arxiv-py-paper-retrieval
description: Incubating Butler wrapper spec for upstream 'arxiv.py'.
category: research
trigger_examples: 查论文, 扩citation, 跟踪研究主题
allowed_roles: feishu-workstation-agent, butler-continuation-agent, orchestrator-agent
risk_level: medium
automation_safe: false
requires_skill_read: true
status: incubating
upstream_name: arxiv.py
upstream_type: open_source_library
review_priority: P0
---
# arxiv.py

## Status

- `incubating`
- 这不是生产可执行 skill，而是 Butler 对外部上游的包装草案。
- 默认不得加入 `chat_default` / `codex_default` / `automation_safe`。

## Proposed Butler Shape

- arXiv search, latest-paper watch, author/topic feed, paper metadata hydration

## Upstream

- repo_or_entry: https://github.com/lukasschwab/arxiv.py
- docs: https://lukasschwab.me/arxiv.py/
- upstream_type: open_source_library
- maturity: high

## Why This Matters

- Cleanest path to build an arXiv research-monitor skill for Butler.
- High leverage for ML, CS, math, and physics paper discovery.

## Risks

- Coverage limited to arXiv-indexed papers.
- Needs download and attachment policy if PDFs are fetched.

## Suggested Future Exposure

- chat_default
- automation_safe

## Implementation Checklist

- 明确 Butler 输入输出 contract，不直接复刻上游 API。
- 确认认证、限流、缓存和错误恢复策略。
- 补执行脚本或 tool bridge，而不是只停留在说明文档。
- 补测试与 `skill-pool-verify` / `skill-pool-maintain` 校验。
- 审阅后再决定是否加入 collection registry。

