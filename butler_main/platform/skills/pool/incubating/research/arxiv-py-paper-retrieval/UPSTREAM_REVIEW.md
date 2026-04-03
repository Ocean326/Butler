# Review: arxiv.py

- candidate_id: `arxiv-py-paper-retrieval`
- imported_path: `./butler_main/platform/skills/pool/incubating/research/arxiv-py-paper-retrieval`
- priority: `P0`
- verdict: `推荐进入第一批实现`
- upstream_type: `open_source_library`

## Review Summary

- proposed_butler_shape: arXiv search, latest-paper watch, author/topic feed, paper metadata hydration
- repo_or_entry: https://github.com/lukasschwab/arxiv.py
- docs: https://lukasschwab.me/arxiv.py/

## Why Recommended

- Cleanest path to build an arXiv research-monitor skill for Butler.
- High leverage for ML, CS, math, and physics paper discovery.

## Risks

- Coverage limited to arXiv-indexed papers.
- Needs download and attachment policy if PDFs are fetched.

## Next Action

- 当前已作为 incubating skill 落库，但尚未实现执行脚本。
- 若进入实现阶段，先补最小执行链路，再决定是否加入 collection。
