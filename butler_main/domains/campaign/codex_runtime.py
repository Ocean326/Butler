from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from butler_main.agents_os.skills import (
    normalize_skill_exposure_payload,
    render_skill_exposure_prompt,
    summarize_skill_exposure,
)
from butler_main.runtime_os.agent_runtime import cli_runner

from .models import CampaignInstance, CampaignPhase, CampaignSpec, WorkingContract
from .phase_runtime import (
    CampaignArtifactRecord,
    CampaignEventRecord,
    CampaignPhaseOutcome,
    merge_phase_metadata,
)
from .supervisor import CampaignResumeOutcome, CampaignSupervisorRuntime


@dataclass(slots=True)
class CampaignCodexResult:
    ok: bool
    output_text: str
    metadata: dict[str, Any] = field(default_factory=dict)


def _receipt_text(receipt) -> str:
    bundle = getattr(receipt, "output_bundle", None)
    if bundle is not None:
        for block in list(getattr(bundle, "text_blocks", []) or [])[::-1]:
            text = str(getattr(block, "text", "") or "").strip()
            if text:
                return text
    return str(getattr(receipt, "summary", "") or "").strip()


class CampaignCodexProvider:
    """Minimal provider interface for Codex-backed Campaign runtime."""

    def run(
        self,
        *,
        prompt: str,
        workspace: str,
        timeout: int,
        runtime_request: Mapping[str, Any] | None = None,
    ) -> CampaignCodexResult:
        raise NotImplementedError


class CliRunnerCampaignCodexProvider(CampaignCodexProvider):
    """Thin adapter over runtime_os.agent_runtime cli_runner for Codex CLI execution."""

    def __init__(
        self,
        *,
        cfg: Mapping[str, Any] | None = None,
        runtime_request: Mapping[str, Any] | None = None,
    ) -> None:
        self._cfg = dict(cfg or {})
        self._runtime_request = dict(runtime_request or {})

    def run(
        self,
        *,
        prompt: str,
        workspace: str,
        timeout: int,
        runtime_request: Mapping[str, Any] | None = None,
    ) -> CampaignCodexResult:
        merged_request = _merge_runtime_request(self._runtime_request, runtime_request)
        exposure_summary = summarize_skill_exposure(merged_request.get("skill_exposure"))
        receipt = cli_runner.run_prompt_receipt(
            prompt or "",
            _normalize_workspace(workspace),
            max(10, int(timeout or 0)),
            cfg=self._cfg or None,
            runtime_request=merged_request,
        )
        output = _receipt_text(receipt)
        ok = str(getattr(receipt, "status", "") or "").strip() == "completed"
        receipt_metadata = dict(getattr(receipt, "metadata", {}) or {})
        metadata = {
            "cli": merged_request.get("cli", "codex"),
            "model": merged_request.get("model", "auto"),
            "ok": ok,
            "skill_exposure": exposure_summary,
            "external_session": dict(receipt_metadata.get("external_session") or {}),
            "recovery_state": dict(receipt_metadata.get("recovery_state") or {}),
            "vendor_capabilities": dict(receipt_metadata.get("vendor_capabilities") or {}),
        }
        if exposure_summary:
            metadata["skill_collection_id"] = str(exposure_summary.get("collection_id") or "").strip()
            metadata["skill_injection_mode"] = str(exposure_summary.get("injection_mode") or "").strip()
        if not ok:
            metadata["error"] = output or "codex run failed"
        return CampaignCodexResult(ok=ok, output_text=output, metadata=metadata)


class CodexCampaignSupervisorRuntime(CampaignSupervisorRuntime):
    """Codex-backed supervisor that attaches optional Codex artifacts per phase."""

    def __init__(
        self,
        *,
        phase_runtime=None,
        reviewer_runtime=None,
        codex_provider: CampaignCodexProvider | None = None,
        codex_timeout: int = 600,
        codex_runtime_request: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(phase_runtime=phase_runtime, reviewer_runtime=reviewer_runtime)
        self._codex_provider = codex_provider
        self._codex_timeout = max(10, int(codex_timeout or 0))
        self._codex_runtime_request = dict(codex_runtime_request or {})

    def bootstrap_campaign(
        self,
        *,
        spec: CampaignSpec,
        contract: WorkingContract,
        mission_id: str,
        supervisor_session_id: str,
    ) -> CampaignPhaseOutcome:
        outcome = super().bootstrap_campaign(
            spec=spec,
            contract=contract,
            mission_id=mission_id,
            supervisor_session_id=supervisor_session_id,
        )
        outcome.metadata = merge_phase_metadata(outcome.metadata, {"bundle_root": str(spec.metadata.get("bundle_root") or "").strip()})
        result = self._run_codex(
            prompt=_discover_prompt(spec=spec, contract=contract),
            workspace=_workspace_from_spec(spec),
            metadata=spec.metadata,
        )
        return _attach_codex_outcome(
            outcome,
            result,
            phase=CampaignPhase.DISCOVER,
            iteration=0,
            prompt_kind="discover",
        )

    def run_implement_phase(self, *, instance: CampaignInstance) -> CampaignPhaseOutcome:
        outcome = super().run_implement_phase(instance=instance)
        outcome.metadata = merge_phase_metadata(
            outcome.metadata,
            {"bundle_root": str((instance.metadata or {}).get("bundle_root") or "").strip()},
        )
        result = self._run_codex(
            prompt=_implement_prompt(instance=instance),
            workspace=_workspace_from_instance(instance),
            metadata=instance.metadata,
        )
        return _attach_codex_outcome(
            outcome,
            result,
            phase=CampaignPhase.IMPLEMENT,
            iteration=instance.current_iteration,
            prompt_kind="implement",
        )

    def run_iterate_phase(
        self,
        *,
        instance: CampaignInstance,
        verdict,
    ) -> CampaignResumeOutcome:
        outcome = super().run_iterate_phase(instance=instance, verdict=verdict)
        outcome.iterate.metadata = merge_phase_metadata(
            outcome.iterate.metadata,
            {"bundle_root": str((instance.metadata or {}).get("bundle_root") or "").strip()},
        )
        result = self._run_codex(
            prompt=_iterate_prompt(instance=instance, verdict=verdict),
            workspace=_workspace_from_instance(instance),
            metadata=instance.metadata,
        )
        updated_iterate = _attach_codex_outcome(
            outcome.iterate,
            result,
            phase=CampaignPhase.ITERATE,
            iteration=instance.current_iteration,
            prompt_kind="iterate",
        )
        runtime_metadata = merge_phase_metadata(outcome.runtime_metadata, updated_iterate.metadata)
        return CampaignResumeOutcome(
            implement=outcome.implement,
            iterate=updated_iterate,
            verdict=outcome.verdict,
            revised_contract=outcome.revised_contract,
            runtime_metadata=runtime_metadata,
        )

    def _run_codex(
        self,
        *,
        prompt: str,
        workspace: str,
        metadata: Mapping[str, Any] | None,
    ) -> CampaignCodexResult | None:
        if self._codex_provider is None:
            return None
        runtime_request = _merge_runtime_request(
            self._codex_runtime_request,
            _runtime_request_from_metadata(metadata),
        )
        return self._codex_provider.run(
            prompt=prompt,
            workspace=workspace,
            timeout=self._codex_timeout,
            runtime_request=runtime_request,
        )


def _attach_codex_outcome(
    outcome: CampaignPhaseOutcome,
    result: CampaignCodexResult | None,
    *,
    phase: CampaignPhase,
    iteration: int,
    prompt_kind: str,
) -> CampaignPhaseOutcome:
    if result is None:
        return outcome
    output_text = str(result.output_text or "").strip()
    bundle_refs = _write_phase_bundle_outputs(
        phase=phase,
        iteration=iteration,
        output_text=output_text,
        metadata=outcome.metadata,
    )
    _apply_primary_artifact_update(
        outcome,
        phase=phase,
        iteration=iteration,
        output_text=output_text,
        bundle_refs=bundle_refs,
        ok=bool(result.ok),
    )
    payload = {
        "output_text": output_text,
        "ok": bool(result.ok),
        "summary": output_text[:400] if output_text else "",
        "deliverable_refs": bundle_refs,
    }
    outcome.artifacts.append(
        CampaignArtifactRecord(
            phase=phase,
            iteration=max(0, int(iteration)),
            kind=f"codex_{prompt_kind}_report",
            label=f"Codex {prompt_kind} report",
            payload=payload,
            metadata={
                **dict(result.metadata or {}),
                "provider": "codex",
                "prompt_kind": prompt_kind,
                **({"deliverable_ref": bundle_refs[0]} if bundle_refs else {}),
            },
        )
    )
    outcome.events.append(
        CampaignEventRecord(
            event_type="codex_runtime_completed" if result.ok else "codex_runtime_failed",
            phase=phase,
            iteration=max(0, int(iteration)),
            payload={
                "provider": "codex",
                "prompt_kind": prompt_kind,
                "ok": bool(result.ok),
            },
        )
    )
    outcome.metadata = merge_phase_metadata(
        outcome.metadata,
        {
            "codex_runtime": {
                "provider": "codex",
                "prompt_kind": prompt_kind,
                "ok": bool(result.ok),
            }
        },
    )
    return outcome


def _apply_primary_artifact_update(
    outcome: CampaignPhaseOutcome,
    *,
    phase: CampaignPhase,
    iteration: int,
    output_text: str,
    bundle_refs: list[str],
    ok: bool,
) -> None:
    for artifact in outcome.artifacts:
        if artifact.phase != phase or int(artifact.iteration or 0) != max(0, int(iteration)):
            continue
        if phase == CampaignPhase.DISCOVER and artifact.kind == "discover_report":
            artifact.payload = {
                **dict(artifact.payload or {}),
                "summary": output_text[:400] if output_text else str(artifact.payload.get("summary") or "").strip(),
                "deliverable_refs": bundle_refs,
            }
            artifact.metadata = {
                **dict(artifact.metadata or {}),
                **({"deliverable_ref": bundle_refs[0]} if bundle_refs else {}),
            }
            return
        if phase == CampaignPhase.IMPLEMENT and artifact.kind == "implementation_report":
            artifact.payload = {
                **dict(artifact.payload or {}),
                "execution_summary": output_text[:400] if output_text else str(artifact.payload.get("execution_summary") or "").strip(),
                "summary": output_text[:400] if output_text else str(artifact.payload.get("summary") or "").strip(),
                "placeholder": not (ok and bool(output_text)),
                "deliverable_refs": bundle_refs,
                "next_action": (
                    "review generated deliverable and close remaining correctness checks"
                    if ok and output_text
                    else "inspect codex runtime failure and keep campaign active"
                ),
            }
            artifact.metadata = {
                **dict(artifact.metadata or {}),
                "placeholder": not (ok and bool(output_text)),
                **({"deliverable_ref": bundle_refs[0]} if bundle_refs else {}),
            }
            return
        if phase == CampaignPhase.ITERATE and artifact.kind.startswith("codex_") is False:
            artifact.metadata = {
                **dict(artifact.metadata or {}),
                **({"deliverable_ref": bundle_refs[0]} if bundle_refs else {}),
            }


def _write_phase_bundle_outputs(
    *,
    phase: CampaignPhase,
    iteration: int,
    output_text: str,
    metadata: Mapping[str, Any] | None,
) -> list[str]:
    bundle_root = _bundle_root_from_metadata(metadata)
    if bundle_root is None:
        return []
    if phase == CampaignPhase.DISCOVER:
        target = bundle_root / "briefs" / "discover_plan.md"
        title = "Discover Plan"
    elif phase == CampaignPhase.IMPLEMENT:
        target = bundle_root / "deliveries" / f"implement_iteration_{max(0, int(iteration)):02d}.md"
        title = f"Implementation Iteration {max(0, int(iteration)):02d}"
    else:
        target = bundle_root / "artifacts" / f"iterate_iteration_{max(0, int(iteration)):02d}.md"
        title = f"Iteration Wrap-up {max(0, int(iteration)):02d}"
    target.parent.mkdir(parents=True, exist_ok=True)
    content = str(output_text or "").strip() or f"{title}\n\nCodex runtime returned no textual output."
    target.write_text(f"# {title}\n\n{content}\n", encoding="utf-8")
    return [str(target)]


def _bundle_root_from_metadata(metadata: Mapping[str, Any] | None) -> Path | None:
    if not isinstance(metadata, Mapping):
        return None
    root = str(metadata.get("bundle_root") or "").strip()
    if not root:
        return None
    return Path(root)


def _merge_runtime_request(
    base: Mapping[str, Any] | None,
    override: Mapping[str, Any] | None,
) -> dict[str, Any]:
    merged: dict[str, Any] = dict(base or {})
    if isinstance(override, Mapping):
        for key, value in override.items():
            if value is None:
                continue
            merged[key] = value
    if not str(merged.get("cli") or "").strip():
        merged["cli"] = "codex"
    return merged


def _runtime_request_from_metadata(metadata: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(metadata, Mapping):
        return {}
    payload = metadata.get("codex_runtime_request")
    runtime_request = dict(payload) if isinstance(payload, Mapping) else {}
    raw_skill_exposure = metadata.get("skill_exposure")
    skill_exposure = normalize_skill_exposure_payload(
        raw_skill_exposure if isinstance(raw_skill_exposure, Mapping) else None,
        default_collection_id="codex_default",
        provider_skill_source="butler",
    )
    if skill_exposure is not None:
        runtime_request.setdefault("skill_exposure", skill_exposure)
    return runtime_request


def _workspace_from_spec(spec: CampaignSpec) -> str:
    return _normalize_workspace(spec.repo_root or spec.workspace_root)


def _workspace_from_instance(instance: CampaignInstance) -> str:
    return _normalize_workspace(instance.repo_root or instance.workspace_root)


def _normalize_workspace(value: str | None) -> str:
    text = str(value or "").strip()
    return text or "."


def _discover_prompt(*, spec: CampaignSpec, contract: WorkingContract) -> str:
    body = (
        "You are the campaign discover runtime. Provide a concise discover report.\n"
        f"Top-level goal: {spec.top_level_goal}\n"
        f"Materials: {', '.join(spec.materials) if spec.materials else 'none'}\n"
        f"Hard constraints: {', '.join(spec.hard_constraints) if spec.hard_constraints else 'none'}\n"
        f"Working contract: {contract.to_dict()}\n"
        "Return a brief summary, key risks, and a suggested next focus."
    )
    return _with_skill_exposure_prompt(
        _workspace_from_spec(spec),
        source_prompt=spec.top_level_goal,
        metadata=spec.metadata,
        body=body,
    )


def _implement_prompt(*, instance: CampaignInstance) -> str:
    contract = instance.working_contract
    acceptance = ", ".join(contract.working_acceptance) if contract.working_acceptance else "none"
    constraints = ", ".join(instance.hard_constraints) if instance.hard_constraints else "none"
    materials = ", ".join(instance.materials) if instance.materials else "none"
    body = (
        "You are the campaign implement runtime. Produce a concise implementation report.\n"
        f"Top-level goal: {instance.top_level_goal}\n"
        f"Working goal: {contract.working_goal}\n"
        f"Acceptance: {acceptance}\n"
        f"Hard constraints: {constraints}\n"
        f"Materials: {materials}\n"
        f"Iteration: {instance.current_iteration}\n"
        "Return a brief summary, notable changes, and open risks."
    )
    return _with_skill_exposure_prompt(
        _workspace_from_instance(instance),
        source_prompt=instance.top_level_goal,
        metadata=instance.metadata,
        body=body,
    )


def _iterate_prompt(*, instance: CampaignInstance, verdict) -> str:
    decision = str(getattr(verdict, "decision", "") or "").strip()
    rationale = str(getattr(verdict, "rationale", "") or "").strip()
    body = (
        "You are the campaign iterate runtime. Provide a short iteration wrap-up.\n"
        f"Top-level goal: {instance.top_level_goal}\n"
        f"Decision: {decision or 'unknown'}\n"
        f"Rationale: {rationale or 'n/a'}\n"
        "Return a brief summary and next recommended focus."
    )
    return _with_skill_exposure_prompt(
        _workspace_from_instance(instance),
        source_prompt=instance.top_level_goal,
        metadata=instance.metadata,
        body=body,
    )


def _with_skill_exposure_prompt(
    workspace: str,
    *,
    source_prompt: str,
    metadata: Mapping[str, Any] | None,
    body: str,
) -> str:
    if not isinstance(metadata, Mapping):
        return body
    raw_exposure = metadata.get("skill_exposure")
    skill_exposure = normalize_skill_exposure_payload(
        raw_exposure if isinstance(raw_exposure, Mapping) else None,
        default_collection_id="codex_default",
        provider_skill_source="butler",
    )
    exposure_prompt = render_skill_exposure_prompt(
        workspace,
        exposure=skill_exposure,
        source_prompt=source_prompt,
        runtime_name="orchestrator",
        max_catalog_skills=24,
        max_catalog_chars=1800,
    )
    if not exposure_prompt:
        return body
    return f"{exposure_prompt}\n\n{body}"


__all__ = [
    "CampaignCodexProvider",
    "CampaignCodexResult",
    "CliRunnerCampaignCodexProvider",
    "CodexCampaignSupervisorRuntime",
]
