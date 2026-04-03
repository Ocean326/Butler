# Butler Console Frontend Attribution

This scaffold is intentionally minimal. Future selective vendoring must stay within the allowlist below and preserve attribution.

## Allowed Sources

- `Langflow` (`MIT`): graph shell, inspection panel patterns, flow store organization
- `AgentSmith` (`MIT`): lightweight React Flow shell, node sidebar patterns
- `SIM` (`Apache-2.0`): action bar, runtime panel structure, graph/runtime synchronization patterns
- `Flock` (`Apache-2.0`): graph mutation hooks, node config patterns
- `Flowise` (`Apache-2.0`, UI-only): toolbar, dirty-state handling, confirm dialogs

## Forbidden Sources

- `EpicStaff`: do not vendor code or UI components due to custom competitive/SaaS restrictions

## Notes

- Prefer selective vendoring of small components and hooks over copying app skeletons.
- Strip original data layer dependencies before reuse; Butler must bind to its own `GraphSnapshot` and draft APIs.
