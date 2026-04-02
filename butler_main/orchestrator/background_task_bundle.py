from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import re
from typing import Any, Mapping

from .paths import resolve_butler_root


_BACKGROUND_TASKS_REL = Path("工作区") / "Butler" / "deliveries" / "background_tasks"
_SAFE_SLUG_RE = re.compile(r"[^a-z0-9]+")


def background_task_root(workspace: str) -> Path:
    root = resolve_butler_root(workspace)
    path = root / _BACKGROUND_TASKS_REL
    path.mkdir(parents=True, exist_ok=True)
    return path


def build_campaign_bundle_metadata(
    *,
    workspace: str,
    campaign_id: str,
    campaign_title: str,
    created_at: str = "",
    metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    meta = dict(metadata or {})
    bundle_root = str(meta.get("bundle_root") or "").strip()
    bundle_manifest = str(meta.get("bundle_manifest") or "").strip()
    if bundle_root and bundle_manifest:
        return {
            "primary_carrier": str(meta.get("primary_carrier") or "campaign").strip() or "campaign",
            "bundle_root": bundle_root,
            "bundle_manifest": bundle_manifest,
            "topic_slug": str(meta.get("topic_slug") or _slugify_topic(campaign_title)).strip() or "task",
            "bundle_created_at_local": str(meta.get("bundle_created_at_local") or _local_timestamp(created_at)).strip(),
        }
    created_local = _local_timestamp(created_at)
    topic_slug = str(meta.get("topic_slug") or _slugify_topic(campaign_title)).strip() or "task"
    bundle_dir = background_task_root(workspace) / f"{created_local}_{topic_slug}_{str(campaign_id or '').strip()}"
    bundle_dir.mkdir(parents=True, exist_ok=True)
    return {
        "primary_carrier": str(meta.get("primary_carrier") or "campaign").strip() or "campaign",
        "bundle_root": str(bundle_dir),
        "bundle_manifest": str(bundle_dir / "manifest.json"),
        "topic_slug": topic_slug,
        "bundle_created_at_local": created_local,
    }


def ensure_campaign_bundle_files(
    *,
    workspace: str,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    metadata = dict(payload.get("metadata") or {})
    raw_bundle_root = str(metadata.get("bundle_root") or "").strip()
    if not raw_bundle_root:
        return {}
    bundle_root = Path(raw_bundle_root)
    bundle_root.mkdir(parents=True, exist_ok=True)
    for name in ("briefs", "artifacts", "deliveries"):
        (bundle_root / name).mkdir(parents=True, exist_ok=True)
    manifest_path = Path(str(metadata.get("bundle_manifest") or bundle_root / "manifest.json")).resolve()
    deliverable_refs = _deliverable_refs(payload)
    manifest = {
        "campaign_id": str(payload.get("campaign_id") or "").strip(),
        "mission_id": str(payload.get("mission_id") or "").strip(),
        "workflow_session_id": str(payload.get("supervisor_session_id") or "").strip(),
        "source_invocation_id": str(
            metadata.get("source_invocation_id")
            or dict(metadata.get("spec") or {}).get("metadata", {}).get("source_invocation_id")
            or ""
        ).strip(),
        "startup_mode": str(metadata.get("startup_mode") or "").strip(),
        "runtime_mode": str(
            dict(metadata.get("campaign_runtime") or {}).get("mode")
            or metadata.get("campaign_runtime_mode")
            or ""
        ).strip(),
        "topic_slug": str(metadata.get("topic_slug") or "").strip(),
        "primary_carrier": str(metadata.get("primary_carrier") or "campaign").strip() or "campaign",
        "status": str(payload.get("status") or "").strip(),
        "current_phase": str(payload.get("current_phase") or "").strip(),
        "current_iteration": int(payload.get("current_iteration") or 0),
        "created_at_utc": str(payload.get("created_at") or "").strip(),
        "updated_at_utc": str(payload.get("updated_at") or "").strip(),
        "bundle_created_at_local": str(metadata.get("bundle_created_at_local") or "").strip(),
        "deliverable_refs": deliverable_refs,
        "pending_correctness_checks": list(metadata.get("pending_correctness_checks") or []),
        "resolved_correctness_checks": list(metadata.get("resolved_correctness_checks") or []),
        "waived_correctness_checks": list(metadata.get("waived_correctness_checks") or []),
        "operational_checks_pending": list(metadata.get("operational_checks_pending") or []),
        "closure_checks_pending": list(metadata.get("closure_checks_pending") or []),
        "execution_state": str(metadata.get("execution_state") or "").strip(),
        "closure_state": str(metadata.get("closure_state") or "").strip(),
        "progress_reason": str(metadata.get("progress_reason") or "").strip(),
        "closure_reason": str(metadata.get("closure_reason") or metadata.get("not_done_reason") or "").strip(),
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    progress_path = bundle_root / "progress.md"
    if not progress_path.exists():
        progress_path.write_text(
            "\n".join(
                [
                    f"# {str(payload.get('campaign_title') or payload.get('top_level_goal') or 'Background Task').strip()}",
                    "",
                    f"- campaign_id: {manifest['campaign_id'] or '-'}",
                    f"- mission_id: {manifest['mission_id'] or '-'}",
                    f"- status: {manifest['status'] or '-'}",
                    f"- runtime_mode: {manifest['runtime_mode'] or '-'}",
                ]
            ),
            encoding="utf-8",
        )
    return {
        "bundle_root": str(bundle_root),
        "bundle_manifest": str(manifest_path),
        "deliverable_refs": deliverable_refs,
    }


def _deliverable_refs(payload: Mapping[str, Any]) -> list[str]:
    refs: list[str] = []
    for artifact in payload.get("artifacts") or []:
        if not isinstance(artifact, Mapping):
            continue
        kind = str(artifact.get("kind") or "").strip().lower()
        if kind in {"working_contract", "evaluation_verdict"}:
            continue
        ref = str(
            artifact.get("deliverable_ref")
            or dict(artifact.get("metadata") or {}).get("deliverable_ref")
            or artifact.get("ref")
            or ""
        ).strip()
        if ref and ref not in refs:
            refs.append(ref)
    return refs


def _local_timestamp(created_at: str) -> str:
    if created_at:
        try:
            dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            return dt.astimezone().strftime("%Y%m%d_%H%M%S")
        except ValueError:
            pass
    return datetime.now().astimezone().strftime("%Y%m%d_%H%M%S")


def _slugify_topic(text: str) -> str:
    lowered = str(text or "").strip().lower()
    if not lowered:
        return "task"
    ascii_only = lowered.encode("ascii", errors="ignore").decode("ascii")
    normalized = _SAFE_SLUG_RE.sub("_", ascii_only).strip("_")
    if not normalized:
        return "task"
    return normalized[:24]


__all__ = [
    "background_task_root",
    "build_campaign_bundle_metadata",
    "ensure_campaign_bundle_files",
]
