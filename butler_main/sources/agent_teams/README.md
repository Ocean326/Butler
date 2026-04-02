# Butler Agent Team Sources

This directory is the Butler fourth-layer source of truth for reusable agent-role templates and team recipes.

It exists in `butler_main/sources/agent_teams/` on purpose:

1. These assets are product/domain resources, not orchestrator core code.
2. Butler keeps runtime truth, product ports, and reusable resources separate.
3. The files here are source artifacts. They are not auto-loaded by Codex or Claude until exported into a runtime directory.

## Scope

Version 1 ships two suites:

- `engineering-core`: templates for coding, debugging, review, and documentation lookup
- `research-campaign`: templates for planning, literature scouting, evidence synthesis, reporting, and evaluation

Each role directory contains:

- `butler-agent.yaml`: Butler canonical contract
- `codex.toml`: OpenAI Codex custom-agent template
- `claude.md`: Claude Code subagent template

`recipes/` contains playbooks for multi-role workflows. These recipes are the Butler representation of an "agent team". They are prompt-level orchestration assets, not a runtime kernel object.

## Layout

```text
butler_main/sources/agent_teams/
  README.md
  MAPPING.md
  references/sources.md
  collections/registry.json
  pool/
    engineering-core/<role>/
    research-campaign/<role>/
  recipes/
```

## Working Rules

1. Update the canonical Butler manifest first, then keep vendor files aligned.
2. Treat official vendor docs as the syntax source of truth.
3. Treat curated community repositories as template inspiration only.
4. Keep permissions explicit. Role intent stays read-only/write-scoped in every canonical manifest even if a vendor mapping needs a wider runtime sandbox to avoid false repo-only limits.
5. Keep model selection profile-based in Butler, vendor-specific only at export time.

## Activation

Use `MAPPING.md` for export instructions:

- Codex target: project `.codex/agents/*.toml`
- Claude target: project `.claude/agents/*.md`

The source files here intentionally do not write into those runtime directories automatically.
