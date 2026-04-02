# Butler Agent Team Mapping

This document maps Butler role contracts to vendor-native files and local runtime settings.

## Vendor Targets

- Codex custom agents: project `.codex/agents/*.toml`
- Codex global settings: project `.codex/config.toml`
- Claude Code subagents: project `.claude/agents/*.md`
- Claude Code team toggle: project `.claude/settings.json`

For Butler, prefer project-level exports over user-level exports so the role set stays attached to this repository.

## Canonical Fields

Butler role manifests use the same top-level contract for every suite:

- `id`
- `suite`
- `display_name`
- `purpose`
- `use_when`
- `avoid_when`
- `inputs`
- `outputs`
- `evidence_rules`
- `permissions_profile`
- `model_profile`
- `tool_profile`
- `vendor_files`

## Permissions Mapping

- `read_only`
  - Codex: `sandbox_mode = "danger-full-access"`
  - Note: Butler keeps the role read-only via `developer_instructions` and `tool_profile`; Codex sandbox is widened so native subagents do not incorrectly claim they are limited to the current repo/workspace.
  - Claude: keep only read/search/web tools in frontmatter
- `workspace_write`
  - Codex: `sandbox_mode = "danger-full-access"`
  - Note: Butler still constrains scope through role ownership and instructions; the wider Codex sandbox avoids false "repo-only" filesystem limits during chat-side native agent work.
  - Claude: allow edit/write/bash tools in frontmatter

Version 1 does not try to force per-agent approval policy. Let the parent session or local settings decide approval prompts.

## Model Mapping

Butler uses profile names first, then maps them to vendor models.

### Codex

These templates only use models confirmed in the current local Codex model cache on this workstation:

- `fast` -> `gpt-5.1-codex-mini`
- `balanced` -> `gpt-5.2-codex`
- `deep` -> `gpt-5.4`

### Claude Code

Use current official model aliases instead of hard-coded dated names:

- `fast` -> `haiku`
- `balanced` -> `sonnet`
- `deep` -> `opus`

## Codex Export

Codex custom agents are standalone TOML files. The current official examples use fields such as `name`, `description`, `developer_instructions`, `model`, `model_reasoning_effort`, and `sandbox_mode`.

### Recommended project settings

Append or merge this into `.codex/config.toml`:

```toml
[agents]
max_threads = 4
max_depth = 3
job_max_runtime_seconds = 1200
```

### Export example

```powershell
New-Item -ItemType Directory -Force .codex\agents | Out-Null
Copy-Item `
  butler_main\sources\agent_teams\pool\engineering-core\explorer\codex.toml `
  .codex\agents\explorer.toml
Copy-Item `
  butler_main\sources\agent_teams\pool\engineering-core\reviewer\codex.toml `
  .codex\agents\reviewer.toml
```

Use the recipes in `recipes/` as prompt-level orchestration guidance. Codex does not currently get a separate Butler-managed "team config" file in this source tree.

Keep `name` aligned with the exported filename unless there is a strong reason not to, so project-level runtime exports remain predictable.

## Claude Export

Claude Code subagents are Markdown files with YAML frontmatter.

### Export example

```powershell
New-Item -ItemType Directory -Force .claude\agents | Out-Null
Copy-Item `
  butler_main\sources\agent_teams\pool\engineering-core\explorer\claude.md `
  .claude\agents\explorer.md
Copy-Item `
  butler_main\sources\agent_teams\pool\research-campaign\evaluator\claude.md `
  .claude\agents\evaluator.md
```

### Optional team-mode toggle

Claude Code agent teams are official but experimental and disabled by default. If you want direct teammate orchestration, add this to `.claude/settings.json`:

```json
{
  "env": {
    "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"
  },
  "teammateMode": "in-process"
}
```

Butler still keeps team structure in `recipes/` because the same team logic must map to both Codex and Claude.

## Recipe Usage

- `engineering-feature-delivery`: use when a feature can be split into exploration, implementation, and final review
- `engineering-bugfix`: use when the first bottleneck is root-cause isolation
- `research-discovery`: use when the main job is search, filtering, and evidence building
- `research-iteration`: use when the campaign already has partial findings and needs another bounded cycle

## Maintenance Notes

1. If vendor syntax changes, update the vendor file first, then update `references/sources.md`.
2. If the local Codex provider exposes a different model set later, only `codex.toml` files and this mapping doc need updates. The Butler canonical manifests should stay profile-based.
3. If Butler later gains an export command, this directory remains the source input to that exporter.
