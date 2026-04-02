# Review: PRAW

- candidate_id: `praw-reddit-ingest`
- imported_path: `./butler_main/sources/skills/pool/incubating/forum/praw-reddit-ingest`
- priority: `P0`
- verdict: `推荐进入第一批实现`
- upstream_type: `open_source_library`

## Review Summary

- proposed_butler_shape: Reddit thread search, subreddit watch, comment tree retrieval, discussion digest
- repo_or_entry: https://github.com/praw-dev/praw
- docs: https://praw.readthedocs.io/en/stable/

## Why Recommended

- Most mature Python entrypoint for Reddit-based forum retrieval.
- Strong fit for market sentiment, product feedback, and community monitoring.

## Risks

- Depends on Reddit API credentials and quota policy.
- Moderation removals and NSFW boundaries need explicit handling.

## Next Action

- 当前已作为 incubating skill 落库，但尚未实现执行脚本。
- 若进入实现阶段，先补最小执行链路，再决定是否加入 collection。
