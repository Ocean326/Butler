# Review: Hacker News API

- candidate_id: `hackernews-api-ingest`
- imported_path: `./butler_main/platform/skills/pool/incubating/forum/hackernews-api-ingest`
- priority: `P0`
- verdict: `推荐进入第一批实现`
- upstream_type: `official_api`

## Review Summary

- proposed_butler_shape: HN top/new/best story ingestion, comment-tree fetch, launch sentiment snapshots
- repo_or_entry: https://github.com/HackerNews/API
- docs: https://github.com/HackerNews/API

## Why Recommended

- Official and lightweight. Easy to operationalize without complex auth.
- Excellent source for engineering, startup, and tool ecosystem signals.

## Risks

- Thread trees can be large and noisy.
- Needs rank-window and keyword filters to stay useful.

## Next Action

- 当前已作为 incubating skill 落库，但尚未实现执行脚本。
- 若进入实现阶段，先补最小执行链路，再决定是否加入 collection。
