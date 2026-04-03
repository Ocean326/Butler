# Review: Europe PMC RESTful Web Service

- candidate_id: `europepmc-rest-biomed`
- imported_path: `./butler_main/platform/skills/pool/incubating/research/europepmc-rest-biomed`
- priority: `P1`
- verdict: `保留在第二批或专题实现`
- upstream_type: `official_api`

## Review Summary

- proposed_butler_shape: biomedical literature retrieval, abstract fetch, grant and preprint monitoring
- repo_or_entry: https://europepmc.org/RestfulWebService
- docs: https://europepmc.org/RestfulWebService

## Why Recommended

- Strong specialist source for biomedical and life-science research.
- Good complement to Crossref and Semantic Scholar when domain specificity matters.

## Risks

- Domain-specific. Not necessary for a general research bundle.
- Needs a separate retrieval profile from CS-first sources like arXiv.

## Next Action

- 当前已作为 incubating skill 落库，但尚未实现执行脚本。
- 若进入实现阶段，先补最小执行链路，再决定是否加入 collection。
