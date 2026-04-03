# Review: reader

- candidate_id: `reader-feed-workbench`
- imported_path: `./butler_main/platform/skills/pool/incubating/general/reader-feed-workbench`
- priority: `P1`
- verdict: `保留在第二批或专题实现`
- upstream_type: `open_source_library`

## Review Summary

- proposed_butler_shape: persistent feed workspace, read-state management, local feed review tool
- repo_or_entry: https://github.com/lemon24/reader
- docs: https://reader.readthedocs.io/

## Why Recommended

- Stronger than raw feed parsing when Butler needs a durable watchlist or inbox model.
- Can back a future research-monitor or forum-monitor workflow.

## Risks

- Heavier than feedparser for simple one-shot pulls.
- Requires local state and lifecycle handling.

## Next Action

- 当前已作为 incubating skill 落库，但尚未实现执行脚本。
- 若进入实现阶段，先补最小执行链路，再决定是否加入 collection。
