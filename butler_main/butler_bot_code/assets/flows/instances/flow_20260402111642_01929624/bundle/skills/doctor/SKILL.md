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

- Clear or reseed invalid role/session bindings for the current flow.
- Repair missing `flow_definition.json` or bundle sidecars for this flow instance.
- Normalize local execution/session mode so the blocked phase can resume safely.

## Forbidden

- Do not rewrite global templates, role catalogs, or unrelated repo code from inside the flow.
