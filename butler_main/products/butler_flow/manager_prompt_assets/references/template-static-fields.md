Template static fields

- Keep reusable intent at the template layer: `label`, `description`, reusable `goal`, reusable `guard_condition`, and reusable `phase_plan`.
- Keep template-level defaults lightweight: `role_guidance`, `control_profile`, `supervisor_profile`, and `source_bindings` are references for future runs, not rigid policy.
- When discussing a template, separate "what should stay reusable" from "what belongs only to this run".
- If the current request mainly changes reusable structure or review standards, stay on template work before creating a flow.
