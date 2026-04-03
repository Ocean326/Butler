---
name: flow-doctor
description: Repair the current flow's runtime assets first; if the fault is in butler-flow code, emit diagnosis + fix plan and request pause.
---

# Flow Doctor

## Recovery order

1. Validate current flow runtime bindings and local sidecars.
2. Repair instance-local assets before suggesting broader action.
3. If the fault is a framework bug, do not fake recovery; output `DOCTOR_FRAMEWORK_BUG:` with diagnosis and fix plan.

## Allowed repairs

- Clear or reseed invalid role/session bindings.
- Repair missing `flow_definition.json` or instance bundle files for the current flow.
- Normalize execution/session mode for the current flow when required for safe recovery.

## Forbidden

- Do not rewrite global templates, role catalogs, or unrelated repo code from inside the flow.
