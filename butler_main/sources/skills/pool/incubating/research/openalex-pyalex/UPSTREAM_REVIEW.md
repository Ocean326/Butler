# Review: OpenAlex plus PyAlex

- candidate_id: `openalex-pyalex`
- imported_path: `./butler_main/sources/skills/pool/incubating/research/openalex-pyalex`
- priority: `P0`
- verdict: `推荐进入第一批实现`
- upstream_type: `official_api_with_client`

## Review Summary

- proposed_butler_shape: institution and author lookup, work graph traversal, topic and concept monitoring
- repo_or_entry: https://github.com/J535D165/pyalex
- docs: https://docs.openalex.org/

## Why Recommended

- Broad and modern scholarly graph with practical Python wrapper support.
- Best candidate when Butler needs research landscape mapping, not just single-paper lookup.

## Risks

- Recent API-key changes mean Butler should centralize credentials and retry policy.
- Result richness can increase prompt noise if not post-filtered.

## Next Action

- 当前已作为 incubating skill 落库，但尚未实现执行脚本。
- 若进入实现阶段，先补最小执行链路，再决定是否加入 collection。
