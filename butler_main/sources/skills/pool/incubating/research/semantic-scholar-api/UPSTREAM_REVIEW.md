# Review: Semantic Scholar API

- candidate_id: `semantic-scholar-api`
- imported_path: `./butler_main/sources/skills/pool/incubating/research/semantic-scholar-api`
- priority: `P0`
- verdict: `推荐进入第一批实现`
- upstream_type: `official_api`

## Review Summary

- proposed_butler_shape: paper lookup, citation graph hops, author impact summary, related-paper expansion
- repo_or_entry: https://www.semanticscholar.org/product/api
- docs: https://www.semanticscholar.org/product/api

## Why Recommended

- Good balance between scholarly metadata richness and agent-friendly API shape.
- Useful when Butler needs citation expansion instead of simple keyword search.

## Risks

- Quota and API-key policy must be checked before automation.
- Coverage varies by field and source.

## Next Action

- 当前已作为 incubating skill 落库，但尚未实现执行脚本。
- 若进入实现阶段，先补最小执行链路，再决定是否加入 collection。
