# Review: Crossref REST API

- candidate_id: `crossref-rest-metadata`
- imported_path: `./butler_main/platform/skills/pool/incubating/research/crossref-rest-metadata`
- priority: `P1`
- verdict: `保留在第二批或专题实现`
- upstream_type: `official_api`

## Review Summary

- proposed_butler_shape: DOI metadata enrichment, reference normalization, publisher-source backfill
- repo_or_entry: https://www.crossref.org/documentation/retrieve-metadata/rest-api/
- docs: https://www.crossref.org/documentation/retrieve-metadata/rest-api/

## Why Recommended

- Excellent utility layer for cleaning and enriching paper metadata from other sources.
- Very useful as a behind-the-scenes helper skill rather than a user-facing standalone skill.

## Risks

- Not ideal as the only search experience.
- Needs polite client identification and cache discipline.

## Next Action

- 当前已作为 incubating skill 落库，但尚未实现执行脚本。
- 若进入实现阶段，先补最小执行链路，再决定是否加入 collection。
