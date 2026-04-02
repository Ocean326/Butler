# Butler Flow Role Packs

This directory stores seed role prompts for foreground `butler-flow`.

- `coding_flow/`
  - planner, implementer, reviewer, fixer, reporter
- `research_flow/`
  - planner, researcher, implementer, reviewer, fixer, reporter

Each role file stays intentionally light. Runtime-specific state, handoffs, and artifacts are injected by `butler_flow.role_runtime`.
