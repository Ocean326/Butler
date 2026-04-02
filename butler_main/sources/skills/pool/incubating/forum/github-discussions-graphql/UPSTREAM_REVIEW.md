# Review: GitHub Discussions GraphQL API

- candidate_id: `github-discussions-graphql`
- imported_path: `./butler_main/sources/skills/pool/incubating/forum/github-discussions-graphql`
- priority: `P1`
- verdict: `保留在第二批或专题实现`
- upstream_type: `official_api`

## Review Summary

- proposed_butler_shape: GitHub Discussions retrieval, maintainer FAQ extraction, release-feedback watch
- repo_or_entry: https://docs.github.com/en/graphql/guides/using-the-graphql-api-for-discussions
- docs: https://docs.github.com/en/graphql/guides/using-the-graphql-api-for-discussions

## Why Recommended

- Strong fit for open-source product support and maintainer communication channels.
- Complements issues and changelog monitoring already common in coding workflows.

## Risks

- Requires GitHub token and GraphQL query discipline.
- Per-repo permissions limit broad public crawling.

## Next Action

- 当前已作为 incubating skill 落库，但尚未实现执行脚本。
- 若进入实现阶段，先补最小执行链路，再决定是否加入 collection。
