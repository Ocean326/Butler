# engineering-feature-delivery

Use this recipe when a feature can be split into exploration, implementation, optional external verification, and final review.

## Recommended role order

1. `explorer`
2. `worker`
3. `docs-researcher` only if the feature depends on changing external behavior
4. `reviewer`

## Parallel window

- `worker` and `docs-researcher` may run in parallel after `explorer`.
- Do not let multiple write-capable roles edit the same file set.

## Final verdict

- `reviewer`

## Required evidence

- relevant files and boundaries from `explorer`
- changed files and test notes from `worker`
- direct source links from `docs-researcher` if used
- prioritized findings and verdict from `reviewer`

## Avoid

- same-file parallel edits
- starting implementation before the code surface is mapped
- skipping the final review pass
