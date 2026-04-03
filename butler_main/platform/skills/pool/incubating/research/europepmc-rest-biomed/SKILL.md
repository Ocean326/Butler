---
name: europepmc-rest-biomed
description: Incubating Butler wrapper spec for upstream 'Europe PMC RESTful Web Service'.
category: research
trigger_examples: 查论文, 扩citation, 跟踪研究主题
allowed_roles: feishu-workstation-agent, butler-continuation-agent, orchestrator-agent
risk_level: medium
automation_safe: false
requires_skill_read: true
status: incubating
upstream_name: Europe PMC RESTful Web Service
upstream_type: official_api
review_priority: P1
---
# Europe PMC RESTful Web Service

## Status

- `incubating`
- 这不是生产可执行 skill，而是 Butler 对外部上游的包装草案。
- 默认不得加入 `chat_default` / `codex_default` / `automation_safe`。

## Proposed Butler Shape

- biomedical literature retrieval, abstract fetch, grant and preprint monitoring

## Upstream

- repo_or_entry: https://europepmc.org/RestfulWebService
- docs: https://europepmc.org/RestfulWebService
- upstream_type: official_api
- maturity: high

## Why This Matters

- Strong specialist source for biomedical and life-science research.
- Good complement to Crossref and Semantic Scholar when domain specificity matters.

## Risks

- Domain-specific. Not necessary for a general research bundle.
- Needs a separate retrieval profile from CS-first sources like arXiv.

## Suggested Future Exposure

- skill_ops

## Implementation Checklist

- 明确 Butler 输入输出 contract，不直接复刻上游 API。
- 确认认证、限流、缓存和错误恢复策略。
- 补执行脚本或 tool bridge，而不是只停留在说明文档。
- 补测试与 `skill-pool-verify` / `skill-pool-maintain` 校验。
- 审阅后再决定是否加入 collection registry。

