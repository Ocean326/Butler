# Sources And Adoption Notes

This file records which external sources shaped the templates in this directory and how much authority each source has.

## Tier 1: Official Syntax And Runtime Behavior

These are the only sources treated as syntax truth:

- OpenAI Codex Subagents
  - https://developers.openai.com/codex/subagents
  - Used for `.codex/agents/*.toml`, user/project agent directories, and current example fields such as `name`, `description`, `developer_instructions`, `model`, `model_reasoning_effort`, and `sandbox_mode`.
- OpenAI Codex Config Reference
  - https://developers.openai.com/codex/config-reference
  - Used for `[agents]` settings such as `max_threads`, `max_depth`, and `job_max_runtime_seconds`.
- OpenAI Codex Subagent Concepts
  - https://developers.openai.com/codex/concepts/subagents
  - Used for the separation rationale around focused workers and reduced context pollution.
- Claude Code Subagents
  - https://docs.anthropic.com/en/docs/claude-code/sub-agents
  - Used for `.claude/agents/*.md`, project vs user directories, and YAML-frontmatter shape.
- Claude Code Agent Teams
  - https://code.claude.com/docs/en/agent-teams
  - Used for the claim that agent teams are official, experimental, disabled by default, and best for parallel collaborative work.
- Claude Code Model Configuration
  - https://docs.anthropic.com/en/docs/claude-code/model-config
  - Used for `haiku`, `sonnet`, and `opus` aliases.

## Tier 2: Curated Community Template Inspiration

These were used to identify repeated role patterns and useful prompt shapes. They are not syntax truth.

- VoltAgent awesome-claude-code-subagents
  - https://github.com/VoltAgent/awesome-claude-code-subagents
  - Useful for repeated role families such as reviewer, debugger, architect, and researcher.
- supatest-ai awesome-claude-code-sub-agents
  - https://github.com/supatest-ai/awesome-claude-code-sub-agents
  - Useful for compact subagent prompt patterns and role naming conventions.

Adopted takeaways:

- stable role families beat one-off personalities
- prompts should define deliverables, not just tone
- read-only reviewer roles are more reusable than mixed review-edit roles

## Tier 3: Low-Signal Forum Input

These were searched but not adopted as schema truth:

- OpenAI Developer Community threads about Codex behavior
- Anthropic community discussions around Claude Code workflows
- Cursor forum threads about custom agents and multi-agent judging

Reason for non-adoption:

- most forum threads were about product behavior, limits, or feature requests
- few contained stable file formats
- almost none provided portable role contracts

## Butler-Specific Conclusions

1. Keep the Butler source of truth vendor-neutral.
2. Keep role permissions explicit and conservative.
3. Treat "team" as a workflow recipe so the same recipe can steer either Codex or Claude.
4. Prefer five stable roles per suite over a large ungoverned template dump.
