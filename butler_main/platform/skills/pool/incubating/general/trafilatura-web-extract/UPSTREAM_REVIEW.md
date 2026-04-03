# Review: Trafilatura

- candidate_id: `trafilatura-web-extract`
- imported_path: `./butler_main/platform/skills/pool/incubating/general/trafilatura-web-extract`
- priority: `P0`
- verdict: `推荐进入第一批实现`
- upstream_type: `open_source_library`

## Review Summary

- proposed_butler_shape: web article extraction, cleanup, metadata capture, source note generation
- repo_or_entry: https://github.com/adbar/trafilatura
- docs: https://trafilatura.readthedocs.io/en/latest/

## Why Recommended

- Good fit for turning arbitrary pages into clean text for downstream summarization and archival.
- Works well as a shared primitive under web-note, forum snapshot, and research ingestion skills.

## Risks

- Dynamic sites and login walls still need browser automation or a secondary fetch path.
- Needs source attribution rules in Butler output.

## Next Action

- 当前已作为 incubating skill 落库，但尚未实现执行脚本。
- 若进入实现阶段，先补最小执行链路，再决定是否加入 collection。
