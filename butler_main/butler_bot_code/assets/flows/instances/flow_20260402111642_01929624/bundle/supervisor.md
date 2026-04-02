# Supervisor Notes · KDD Section 1 Flow

- Preserve the current flow goal and guard condition before any local optimization.
- If repeated service faults, invalid session bindings, or resume/no-rollout failures occur, escalate to the temporary `doctor` role.
- `doctor` only repairs current-flow runtime bindings, instance-local static assets, and safe local execution/session settings.
- If `doctor` reports a butler-flow framework/code bug, pause and surface the diagnosis to the operator instead of forcing more retries.
