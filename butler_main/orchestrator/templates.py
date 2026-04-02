from __future__ import annotations

from typing import Any


def build_mission_payload_from_template(template_id: str, inputs: dict[str, Any] | None = None) -> dict[str, Any]:
    template = str(template_id or "").strip()
    if template == "brainstorm_topic":
        return build_brainstorm_topic_payload(inputs or {})
    raise ValueError(f"unsupported template_id: {template_id}")


def build_brainstorm_topic_payload(inputs: dict[str, Any]) -> dict[str, Any]:
    topic = str(inputs.get("topic") or inputs.get("title") or "").strip()
    if not topic:
        raise ValueError("brainstorm_topic requires topic")
    title = str(inputs.get("title") or f"Brainstorm: {topic}").strip()
    goal = str(inputs.get("goal") or f"Generate actionable insights for {topic}").strip()
    context = str(inputs.get("context") or "").strip()
    current_date = str(inputs.get("current_date") or "").strip()
    references = _normalize_reference_items(inputs.get("reference_items"))
    focus_questions = _normalize_string_list(inputs.get("focus_questions"))
    top_n = max(1, int(inputs.get("top_n") or 5))
    return {
        "mission_type": "brainstorm_topic",
        "title": title,
        "goal": goal,
        "inputs": {
            "topic": topic,
            "context": context,
            "current_date": current_date,
            "reference_items": references,
            "focus_questions": focus_questions,
            "top_n": top_n,
        },
        "success_criteria": [
            "Produce a clear brainstorm scope",
            "Generate multiple implementation-relevant idea angles",
            "Summarize the strongest actionable directions",
        ],
        "constraints": {
            "max_iterations": int(inputs.get("max_iterations") or 4),
            "max_parallel_branches": int(inputs.get("max_parallel_branches") or 3),
        },
        "nodes": [
            {
                "node_id": "scope",
                "kind": "define_scope",
                "title": "Define brainstorm scope",
                "status": "pending",
                "metadata": {
                    "topic": topic,
                    "current_date": current_date,
                    "focus_questions": focus_questions,
                },
            },
            {
                "node_id": "scan_references",
                "kind": "reference_scan",
                "title": "Scan current references",
                "status": "pending",
                "dependencies": ["scope"],
                "runtime_plan": {"worker_profile": "research_scanner"},
                "metadata": {"reference_items": references},
            },
            {
                "node_id": "generate_angles",
                "kind": "brainstorm",
                "title": "Generate implementation angles",
                "status": "pending",
                "dependencies": ["scan_references"],
                "runtime_plan": {
                    "worker_profile": "brainstormer",
                    "workflow_template": {
                        "template_id": "brainstorm.generate_angles",
                        "kind": "local_collaboration",
                        "roles": [
                            {"role_id": "researcher", "capability_id": "reference_scan"},
                            {"role_id": "ideator", "capability_id": "brainstorm"},
                            {"role_id": "critic", "capability_id": "review"},
                        ],
                        "steps": [
                            {"step_id": "collect_signals", "title": "Collect signals"},
                            {"step_id": "expand_angles", "title": "Expand candidate angles"},
                            {"step_id": "critique_shortlist", "title": "Critique shortlist"},
                        ],
                        "entry_contract": {"required_inputs": ["topic", "focus_questions"]},
                        "exit_contract": {"required_outputs": ["candidate_directions"]},
                        "metadata": {"source": "brainstorm_topic_template"},
                    },
                    "workflow_inputs": {
                        "topic_ref": "mission.inputs.topic",
                        "focus_questions_ref": "mission.inputs.focus_questions",
                    },
                },
                "branch_policy": {"fanout": min(top_n, 3), "quorum": 1},
            },
            {
                "node_id": "synthesize",
                "kind": "synthesize",
                "title": "Synthesize shortlist",
                "status": "pending",
                "dependencies": ["generate_angles"],
                "runtime_plan": {"worker_profile": "synthesizer"},
                "metadata": {"top_n": top_n},
            },
            {
                "node_id": "archive",
                "kind": "archive",
                "title": "Archive brainstorm note",
                "status": "pending",
                "dependencies": ["synthesize"],
            },
        ],
        "metadata": {
            "template_id": "brainstorm_topic",
            "template_version": "2026-03-21",
        },
    }


def build_agent_harness_brainstorm_inputs(
    *,
    current_date: str,
    reference_items: list[dict[str, str]],
) -> dict[str, Any]:
    return {
        "title": "Brainstorm how Butler should absorb current agent harness research/projects",
        "topic": "Current agent harness research/projects and what Butler should absorb",
        "goal": "Generate implementation directions for Butler's orchestrator/harness based on current agent harness projects and research",
        "context": "Focus on lightweight orchestrator design, agent runtime boundaries, workflow/state contracts, subworkflow handling, and observability. The output should bias toward ideas Butler can absorb incrementally.",
        "current_date": current_date,
        "reference_items": reference_items,
        "focus_questions": [
            "What orchestration primitive set stays minimal but production-capable?",
            "How do mature projects separate runtime, workflow, and memory?",
            "Which ideas can Butler absorb without rebuilding the whole stack?",
        ],
        "top_n": 5,
        "max_iterations": 4,
        "max_parallel_branches": 3,
    }


def _normalize_string_list(values) -> list[str]:
    if not isinstance(values, list):
        return []
    seen: set[str] = set()
    normalized: list[str] = []
    for item in values:
        value = str(item or "").strip()
        if not value or value in seen:
            continue
        seen.add(value)
        normalized.append(value)
    return normalized


def _normalize_reference_items(values) -> list[dict[str, str]]:
    if not isinstance(values, list):
        return []
    normalized: list[dict[str, str]] = []
    for item in values:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        url = str(item.get("url") or "").strip()
        note = str(item.get("note") or "").strip()
        if not title and not url:
            continue
        normalized.append({"title": title, "url": url, "note": note})
    return normalized
