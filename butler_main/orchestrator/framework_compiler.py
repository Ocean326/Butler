from __future__ import annotations

from typing import Any, Mapping

from .framework_profiles import get_framework_profile_definition, resolve_framework_profile_id
from .models import Branch, Mission, MissionNode
from .workflow_ir import WorkflowIR


def _text(value: Any, *, default: str = "") -> str:
    text = str(value or "").strip()
    return text or default


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _list_of_dicts(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    out: list[dict[str, Any]] = []
    for item in value:
        if isinstance(item, Mapping):
            out.append(dict(item))
    return out


def _deep_merge(base: Mapping[str, Any] | None, override: Mapping[str, Any] | None) -> dict[str, Any]:
    result = dict(base or {})
    for key, value in dict(override or {}).items():
        if isinstance(value, Mapping) and isinstance(result.get(key), Mapping):
            result[key] = _deep_merge(result.get(key), value)
            continue
        result[key] = value
    return result


def _first_text_from_sources(sources: tuple[Mapping[str, Any], ...], key: str) -> str:
    for source in sources:
        value = str(source.get(key) or "").strip()
        if value:
            return value
    return ""


def _first_mapping_from_sources(sources: tuple[Mapping[str, Any], ...], key: str) -> dict[str, Any]:
    for source in sources:
        payload = source.get(key)
        if isinstance(payload, Mapping):
            return dict(payload)
    return {}


def _text_list(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple, set)):
        return []
    items: list[str] = []
    seen: set[str] = set()
    for item in value:
        text = str(item or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        items.append(text)
    return items


def _sanitize_name(value: str) -> str:
    cleaned = []
    for ch in str(value or "").strip().lower():
        if ch.isalnum():
            cleaned.append(ch)
        elif ch in {"-", "_", ".", "/"}:
            cleaned.append(".")
    text = "".join(cleaned).strip(".")
    while ".." in text:
        text = text.replace("..", ".")
    return text


def _normalize_framework_compiler_inputs(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        return {}
    raw = dict(payload)
    if isinstance(raw.get("entry"), Mapping) or isinstance(raw.get("mapping"), Mapping):
        entry = _mapping(raw.get("entry"))
        mapping = _mapping(raw.get("mapping"))
        raw = {
            "framework_id": _text(entry.get("framework_id")),
            "display_name": _text(entry.get("display_name")),
            "source_kind": _text(entry.get("source_kind")),
            "butler_targets": _list_of_dicts(mapping.get("butler_targets")),
            "absorbed_packages": _list_of_dicts(mapping.get("absorbed_packages")),
            "governance_defaults": _mapping(mapping.get("governance_defaults")),
            "runtime_binding_hints": _mapping(mapping.get("runtime_binding_hints")),
            "compiler_profile_templates": _list_of_dicts(mapping.get("compiler_profile_templates")),
        }
    normalized = dict(raw)
    templates = _list_of_dicts(normalized.get("compiler_profile_templates"))
    if not templates:
        return normalized
    template = dict(templates[0])
    if not _text(normalized.get("template_id")) and _text(template.get("template_id")):
        normalized["template_id"] = _text(template.get("template_id"))
    if not _text(normalized.get("workflow_kind")) and _text(template.get("workflow_kind")):
        normalized["workflow_kind"] = _text(template.get("workflow_kind"))
    if not _text(normalized.get("capability_package_ref")) and _text(template.get("capability_package_ref")):
        normalized["capability_package_ref"] = _text(template.get("capability_package_ref"))
    if not _text(normalized.get("team_package_ref")) and _text(template.get("team_package_ref")):
        normalized["team_package_ref"] = _text(template.get("team_package_ref"))
    if not _text(normalized.get("governance_policy_ref")) and _text(template.get("governance_policy_ref")):
        normalized["governance_policy_ref"] = _text(template.get("governance_policy_ref"))
    normalized["runtime_binding_hints"] = _deep_merge(
        _mapping(normalized.get("runtime_binding_hints")),
        _mapping(template.get("runtime_binding")),
    )
    normalized["input_contract"] = _deep_merge(
        _mapping(normalized.get("input_contract")),
        _mapping(template.get("input_contract")),
    )
    normalized["output_contract"] = _deep_merge(
        _mapping(normalized.get("output_contract")),
        _mapping(template.get("output_contract")),
    )
    return normalized


def _extract_framework_compiler_inputs(
    sources: tuple[Mapping[str, Any], ...],
    raw_profile: Mapping[str, Any] | None,
) -> dict[str, Any]:
    resolved = _normalize_framework_compiler_inputs(_mapping(raw_profile).get("framework_compiler_inputs"))
    resolved = _deep_merge(resolved, _normalize_framework_compiler_inputs(_mapping(raw_profile).get("framework_mapping_bundle")))
    for source in sources:
        for key in ("framework_compiler_inputs", "framework_mapping_bundle"):
            resolved = _deep_merge(resolved, _normalize_framework_compiler_inputs(source.get(key)))
    return resolved


def _runtime_safe_role_binding(payload: Mapping[str, Any]) -> dict[str, Any]:
    binding = dict(payload or {})
    metadata = _mapping(binding.get("metadata"))
    package_ref = _text(binding.get("package_ref"))
    if package_ref and "package_ref" not in metadata:
        metadata["package_ref"] = package_ref
    framework_binding = {
        key: value
        for key, value in binding.items()
        if key
        not in {
            "role_id",
            "id",
            "agent_spec_id",
            "capability_id",
            "capability",
            "package_ref",
            "policy_refs",
            "metadata",
        }
    }
    if framework_binding:
        metadata["framework_binding"] = _deep_merge(metadata.get("framework_binding"), framework_binding)
    return {
        "role_id": _text(binding.get("role_id") or binding.get("id")),
        "agent_spec_id": _text(binding.get("agent_spec_id")),
        "capability_id": _text(binding.get("capability_id") or binding.get("capability")),
        "policy_refs": _text_list(binding.get("policy_refs")),
        "metadata": metadata,
    }


def _runtime_safe_role_bindings(payload: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        binding
        for binding in (_runtime_safe_role_binding(item) for item in payload)
        if binding.get("role_id")
    ]


class FrameworkProfileCompiler:
    """Compile normalized framework profiles into Butler WorkflowIR."""

    def compile(
        self,
        *,
        mission: Mission,
        node: MissionNode,
        branch: Branch,
        profile_id: str = "",
        profile_payload: Mapping[str, Any] | None = None,
    ) -> WorkflowIR:
        sources = (
            dict(branch.input_payload or {}),
            dict(branch.metadata or {}),
            dict(node.runtime_plan or {}),
            dict(node.metadata or {}),
        )
        raw_profile = _deep_merge(_first_mapping_from_sources(sources, "framework_profile"), profile_payload or {})
        framework_compiler_inputs = _extract_framework_compiler_inputs(sources, raw_profile)
        framework_id = _text(
            raw_profile.get("framework_id")
            or framework_compiler_inputs.get("framework_id")
            or _first_text_from_sources(sources, "framework_id")
        )
        resolved_profile_id = resolve_framework_profile_id(
            profile_id or _text(raw_profile.get("profile_id") or raw_profile.get("framework_profile_id") or _first_text_from_sources(sources, "framework_profile_id")),
            framework_id=framework_id,
        )
        definition = get_framework_profile_definition(resolved_profile_id, framework_id=framework_id)
        if not definition:
            raise ValueError(f"unsupported framework profile: {profile_id or framework_id or '(empty)'}")

        profile = _deep_merge(definition, framework_compiler_inputs)
        profile = _deep_merge(profile, raw_profile)
        framework_id = _text(profile.get("framework_id"), default=framework_id)
        profile_id = _text(profile.get("profile_id"), default=resolved_profile_id)
        workflow_template = _deep_merge(profile.get("workflow_template"), _mapping(raw_profile.get("workflow_template_override")))
        rich_role_bindings = _list_of_dicts(profile.get("role_bindings"))
        if not workflow_template.get("roles") and rich_role_bindings:
            workflow_template["roles"] = [dict(item) for item in rich_role_bindings]
        role_bindings = _runtime_safe_role_bindings(rich_role_bindings)

        runtime_binding_hints = _deep_merge(profile.get("runtime_binding_hints"), _mapping(raw_profile.get("runtime_binding_hints")))
        explicit_runtime_binding = _first_mapping_from_sources(sources, "runtime_binding")
        runtime_key = _text(
            _first_text_from_sources(sources, "runtime_key")
            or runtime_binding_hints.get("runtime_key"),
            default="default",
        )
        worker_profile = _text(
            _first_text_from_sources(sources, "worker_profile")
            or runtime_binding_hints.get("worker_profile"),
            default=runtime_key,
        )
        default_agent_id = ".".join(
            part
            for part in [
                "orchestrator",
                _sanitize_name(runtime_key),
                _sanitize_name(framework_id),
                _sanitize_name(profile_id),
            ]
            if part
        )
        agent_id = _text(
            _first_text_from_sources(sources, "agent_id")
            or runtime_binding_hints.get("agent_id"),
            default=default_agent_id or f"orchestrator.{runtime_key}",
        )
        runtime_binding = _deep_merge(
            runtime_binding_hints,
            {
                "runtime_key": runtime_key,
                "worker_profile": worker_profile,
                "agent_id": agent_id,
            },
        )
        runtime_binding = _deep_merge(runtime_binding, explicit_runtime_binding)
        runtime_binding.setdefault("runtime_key", runtime_key)
        runtime_binding.setdefault("worker_profile", worker_profile)
        runtime_binding.setdefault("agent_id", agent_id)

        governance_defaults = _mapping(profile.get("governance_defaults"))
        verification = _deep_merge(governance_defaults.get("verification"), _first_mapping_from_sources(sources, "verification"))
        approval = _deep_merge(governance_defaults.get("approval"), _first_mapping_from_sources(sources, "approval"))
        recovery = _deep_merge(governance_defaults.get("recovery"), _first_mapping_from_sources(sources, "recovery"))

        capability_package_ref = _text(
            _first_text_from_sources(sources, "capability_package_ref") or profile.get("capability_package_ref")
        )
        team_package_ref = _text(
            _first_text_from_sources(sources, "team_package_ref") or profile.get("team_package_ref")
        )
        governance_policy_ref = _text(
            _first_text_from_sources(sources, "governance_policy_ref") or profile.get("governance_policy_ref")
        )

        input_contract = _deep_merge(profile.get("input_contract"), _first_mapping_from_sources(sources, "input_contract"))
        output_contract = _deep_merge(profile.get("output_contract"), _first_mapping_from_sources(sources, "output_contract"))
        workflow_inputs = {
            "mission_id": mission.mission_id,
            "mission_type": mission.mission_type,
            "mission_title": mission.title,
            "mission_goal": mission.goal,
            "node_id": node.node_id,
            "node_kind": node.kind,
            "node_title": node.title,
            "branch_id": branch.branch_id,
            "framework_id": framework_id,
            "framework_profile_id": profile_id,
        }
        workflow_inputs.update(_mapping(profile.get("workflow_inputs")))
        workflow_inputs.update(_first_mapping_from_sources(sources, "workflow_inputs"))

        framework_origin = {
            "framework_id": framework_id,
            "profile_id": profile_id,
            "display_name": _text(profile.get("display_name")),
            "source_kind": _text(profile.get("source_kind"), default="framework_profile"),
            "compiler_variant": "orchestrator.framework_compiler.v1",
            "butler_targets": list(profile.get("butler_targets") or []),
            "runtime_binding_hints": dict(runtime_binding_hints or {}),
            "governance_defaults": dict(governance_defaults or {}),
            "compiler_hints": dict(profile.get("compiler_hints") or {}),
        }

        workflow_template.setdefault("template_id", _text(profile.get("template_id") or workflow_template.get("template_id"), default=f"framework.{framework_id}.{profile_id}"))
        workflow_template.setdefault("kind", _text(profile.get("workflow_kind") or workflow_template.get("kind"), default="local_collaboration"))
        workflow_template.setdefault("entry_step_id", _text(workflow_template.get("entry_step_id")))
        workflow_template["package_refs"] = {
            "capability_package_ref": capability_package_ref,
            "team_package_ref": team_package_ref,
            "governance_policy_ref": governance_policy_ref,
        }
        workflow_template["runtime_binding"] = dict(runtime_binding)
        workflow_template["entry_contract"] = dict(input_contract)
        workflow_template["exit_contract"] = dict(output_contract)
        workflow_template["metadata"] = _deep_merge(
            workflow_template.get("metadata"),
            {
                "framework_origin": framework_origin,
                "compiler_hints": dict(profile.get("compiler_hints") or {}),
            },
        )
        entry_step_id = _text(
            _first_text_from_sources(sources, "entry_step_id")
            or workflow_template.get("entry_step_id")
            or (workflow_template.get("steps") or [{}])[0].get("step_id"),
        )

        lineage = {
            "compiler_version": "orchestrator.framework_compiler.v1",
            "mission_type": _text(mission.mission_type),
            "mission_title": _text(mission.title),
            "mission_priority": int(mission.priority or 0),
            "node_status": _text(node.status),
            "framework_id": framework_id,
            "framework_profile_id": profile_id,
        }

        metadata = _deep_merge(
            {
                **lineage,
                "framework_origin": framework_origin,
                "field_taxonomy": {
                    "compile_time": [
                        "workflow",
                        "steps",
                        "edges",
                        "roles",
                        "artifacts",
                        "handoffs",
                        "verification",
                        "approval",
                        "recovery",
                        "capability_package_ref",
                        "team_package_ref",
                        "governance_policy_ref",
                        "runtime_binding",
                        "input_contract",
                        "output_contract",
                    ],
                    "runtime": [
                        "workflow_session_id",
                        "workflow_inputs",
                        "runtime_key",
                        "agent_id",
                        "worker_profile",
                        "subworkflow_kind",
                        "research_unit_id",
                        "scenario_action",
                    ],
                    "observability": [
                        "metadata",
                        "lineage",
                        "tags",
                        "gate_policies",
                        "execution_boundary",
                    ],
                },
            },
            _first_mapping_from_sources(sources, "workflow_metadata"),
        )

        return WorkflowIR(
            workflow_id=_text(branch.branch_id),
            mission_id=_text(mission.mission_id),
            node_id=_text(node.node_id),
            branch_id=_text(branch.branch_id),
            workflow_kind=_text(workflow_template.get("kind"), default="local_collaboration"),
            driver_kind="orchestrator_node",
            entrypoint="orchestrator",
            runtime_key=runtime_key,
            agent_id=agent_id,
            worker_profile=worker_profile,
            node_kind=_text(node.kind),
            node_title=_text(node.title),
            template_id=_text(workflow_template.get("template_id")),
            workflow_template=workflow_template,
            role_bindings=role_bindings,
            workflow_inputs=workflow_inputs,
            verification=verification,
            approval=approval,
            recovery=recovery,
            capability_package_ref=capability_package_ref,
            team_package_ref=team_package_ref,
            governance_policy_ref=governance_policy_ref,
            runtime_binding=runtime_binding,
            input_contract=input_contract,
            output_contract=output_contract,
            entry_step_id=entry_step_id,
            steps=_list_of_dicts(workflow_template.get("steps")),
            edges=_list_of_dicts(workflow_template.get("edges")),
            roles=_list_of_dicts(workflow_template.get("roles")),
            artifacts=_list_of_dicts(workflow_template.get("artifacts")),
            handoffs=_list_of_dicts(workflow_template.get("handoffs")),
            runtime_state={
                "workflow_session_id": _first_text_from_sources(sources, "workflow_session_id"),
                "mission_id": _text(mission.mission_id),
                "node_id": _text(node.node_id),
                "branch_id": _text(branch.branch_id),
                "status": "compiled",
                "workflow_inputs": workflow_inputs,
                "runtime_key": runtime_key,
                "agent_id": agent_id,
                "worker_profile": worker_profile,
                "node_kind": _text(node.kind),
                "subworkflow_kind": "",
                "research_unit_id": "",
                "scenario_action": "",
                "metadata": {
                    "framework_origin": framework_origin,
                },
            },
            observability={
                "tags": [
                    item
                    for item in [
                        _text(workflow_template.get("kind"), default="local_collaboration"),
                        _text(node.kind),
                        worker_profile,
                        framework_id,
                        profile_id,
                    ]
                    if item
                ],
                "lineage": lineage,
            },
            metadata=metadata,
        )
