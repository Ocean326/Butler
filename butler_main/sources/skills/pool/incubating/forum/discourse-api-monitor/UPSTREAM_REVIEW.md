# Review: Discourse API

- candidate_id: `discourse-api-monitor`
- imported_path: `./butler_main/sources/skills/pool/incubating/forum/discourse-api-monitor`
- priority: `P1`
- verdict: `保留在第二批或专题实现`
- upstream_type: `official_api`

## Review Summary

- proposed_butler_shape: Discourse forum topic fetch, category watch, announcement ingestion, support-thread summarization
- repo_or_entry: https://meta.discourse.org/t/discourse-rest-api-documentation/22706
- docs: https://meta.discourse.org/t/discourse-rest-api-documentation/22706

## Why Recommended

- A large number of product, devtool, and open-source communities run on Discourse.
- One integration can unlock many vendor and community forums.

## Risks

- Each forum has its own auth and rate constraints.
- Schema differences across versions need tolerant parsing.

## Next Action

- 当前已作为 incubating skill 落库，但尚未实现执行脚本。
- 若进入实现阶段，先补最小执行链路，再决定是否加入 collection。
