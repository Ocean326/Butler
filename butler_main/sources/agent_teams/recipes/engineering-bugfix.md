# engineering-bugfix

Use this recipe when the main bottleneck is root-cause isolation rather than raw implementation speed.

## Recommended role order

1. `debugger`
2. `docs-researcher` only if the bug may depend on changing platform behavior
3. `worker`
4. `reviewer`

## Parallel window

- `docs-researcher` may run beside `debugger` if the suspected issue spans external SDK or API changes.
- `worker` should wait until `debugger` produces a credible fix surface.

## Final verdict

- `reviewer`

## Required evidence

- repro notes and minimal fix plan from `debugger`
- compatibility notes from `docs-researcher` if used
- changed files and test notes from `worker`
- prioritized findings and verdict from `reviewer`

## Avoid

- editing first and diagnosing later
- broad refactors disguised as bug fixes
- merging a fix without a review gate
