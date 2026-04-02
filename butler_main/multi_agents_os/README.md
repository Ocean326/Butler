# multi_agents_os

Local typed collaboration substrate for workflow-backed multi-agent sessions.

Current scope:
- static workflow/template loading
- explicit role binding
- workflow session identity and recovery bundle
- shared state container for workflow-local state
- typed artifact registry with producer and visibility contract
- typed collaboration substrate for mailbox, ownership, join contract, and role handoff
- session-scoped local event log
- workflow factory as assembly/recovery entrypoint
- orchestrator node to workflow session assembly
- research/orchestrator consumers reading one stable session contract instead of file layout details

Non-goals:
- system-level orchestration
- global scheduling
- mission ledger / branch governance
- delivery transport
- team supervisor loop
- heavy mailbox bus or global message broker

Consumer surface:
- create session
- load session bundle
- patch shared state
- add artifact
- post mailbox message
- assign step owner
- declare join contract
- record role handoff
- read local event log
