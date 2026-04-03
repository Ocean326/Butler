from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Mapping

from butler_main.runtime_os.agent_runtime import (
    DeliveryRequest,
    MissionOrchestrator as MissionOrchestratorProtocol,
    OutputBundle,
    RouteProjection,
    RuntimeRequest,
    TextBlock,
    WorkflowProjection,
)
from butler_main.runtime_os.process_runtime import WorkflowReceipt

from ..workspace import build_orchestrator_service_for_workspace
from .ingress_service import OrchestratorIngressService
from .query_service import OrchestratorQueryService

_MISSION_ID_RE = re.compile(r"(?:task|mission)[_\s-]*id\s*[=:：]\s*([A-Za-z0-9._:-]+)", re.IGNORECASE)
_MISSION_TOKEN_RE = re.compile(r"\b(mission[_:-][A-Za-z0-9._:-]+)\b", re.IGNORECASE)


@dataclass(slots=True, frozen=True)
class MissionIngressResolution:
    operation: str
    payload: dict[str, Any]
    workspace: str


class ButlerMissionOrchestrator(MissionOrchestratorProtocol):
    """Product-layer mission runtime wrapper on top of the orchestrator service."""

    def __init__(
        self,
        *,
        ingress_service: OrchestratorIngressService | None = None,
        query_service: OrchestratorQueryService | None = None,
        service_factory=None,
    ) -> None:
        self._ingress_service = ingress_service or OrchestratorIngressService()
        self._query_service = query_service or OrchestratorQueryService()
        self._service_factory = service_factory or build_orchestrator_service_for_workspace

    def orchestrate(self, request: RuntimeRequest) -> WorkflowReceipt:
        resolved = self._resolve_request(request)
        route = request.route or self._build_route_projection(request, resolved)
        try:
            if resolved.operation == "create":
                ingress = self._ingress_service.create_mission(resolved.workspace, resolved.payload)
                mission_id = str(ingress.get("mission_id") or "").strip()
                status_payload = self._query_service.get_mission_status(resolved.workspace, mission_id)
            elif resolved.operation == "status":
                mission_id = str(resolved.payload.get("mission_id") or "").strip()
                status_payload = self._query_service.get_mission_status(resolved.workspace, mission_id)
            elif resolved.operation == "control":
                mission_id = str(resolved.payload.get("mission_id") or "").strip()
                action = str(resolved.payload.get("action") or "pause").strip().lower() or "pause"
                self._query_service.control_mission(resolved.workspace, mission_id, action)
                status_payload = self._query_service.get_mission_status(resolved.workspace, mission_id)
            elif resolved.operation == "feedback":
                mission_id = str(resolved.payload.get("mission_id") or "").strip()
                feedback = str(resolved.payload.get("feedback") or "").strip()
                self._query_service.append_user_feedback(resolved.workspace, mission_id, feedback)
                status_payload = self._query_service.get_mission_status(resolved.workspace, mission_id)
            else:
                raise ValueError(f"unsupported mission operation: {resolved.operation}")
            projection = self._build_workflow_projection(request, route, status_payload, resolved.operation)
            bundle = self._build_output_bundle(status_payload, resolved.operation)
            delivery_request = None
            if request.delivery_session is not None:
                delivery_request = DeliveryRequest(
                    session=request.delivery_session,
                    bundle_ref=bundle.bundle_id,
                    bundle=bundle,
                    metadata={"mission_operation": resolved.operation, "workflow_id": projection.workflow_id},
                )
            return WorkflowReceipt(
                invocation_id=request.invocation.invocation_id,
                workflow_id=projection.workflow_id,
                workflow_kind=projection.workflow_kind or "mission",
                status=projection.status,
                route=route,
                projection=projection,
                output_bundle=bundle,
                delivery_request=delivery_request,
                summary=bundle.summary,
                metadata={"mission_operation": resolved.operation, "workspace": resolved.workspace},
            )
        except Exception as exc:
            bundle = OutputBundle(
                summary=f"mission operation failed: {exc}",
                text_blocks=[TextBlock(text=f"mission operation failed: {exc}")],
                metadata={"mission_operation": resolved.operation},
            )
            return WorkflowReceipt(
                invocation_id=request.invocation.invocation_id,
                workflow_id="",
                workflow_kind="mission",
                status="failed",
                route=route,
                output_bundle=bundle,
                summary=bundle.summary,
                metadata={
                    "mission_operation": resolved.operation,
                    "workspace": resolved.workspace,
                    "error": str(exc),
                },
            )

    def _resolve_request(self, request: RuntimeRequest) -> MissionIngressResolution:
        metadata = dict(request.metadata or {})
        invocation_metadata = dict(request.invocation.metadata or {})
        workspace = str(
            metadata.get("workspace")
            or invocation_metadata.get("workspace")
            or invocation_metadata.get("workspace_root")
            or "."
        ).strip() or "."
        operation = str(
            metadata.get("mission_operation")
            or invocation_metadata.get("mission_operation")
            or self._infer_operation(request.invocation.user_text)
        ).strip().lower() or "create"
        payload = dict(metadata.get("mission_payload") or {})
        if not payload:
            payload = self._default_payload(request, operation)
        return MissionIngressResolution(operation=operation, payload=payload, workspace=workspace)

    def _default_payload(self, request: RuntimeRequest, operation: str) -> dict[str, Any]:
        metadata = dict(request.metadata or {})
        invocation_metadata = dict(request.invocation.metadata or {})
        user_text = str(request.invocation.user_text or "").strip()
        if operation == "create":
            explicit_mission = metadata.get("mission") or invocation_metadata.get("mission")
            if isinstance(explicit_mission, Mapping):
                return {"mission": dict(explicit_mission)}
            template_id = str(metadata.get("template_id") or invocation_metadata.get("template_id") or "").strip()
            if template_id:
                return {
                    "template_id": template_id,
                    "template_inputs": dict(
                        metadata.get("template_inputs") or invocation_metadata.get("template_inputs") or {}
                    ),
                }
            body = self._extract_create_body(user_text)
            title = self._truncate_title(body or user_text)
            goal = str(body or user_text).strip()
            return {
                "mission": {
                    "mission_type": "talk_ingress",
                    "title": title,
                    "goal": goal,
                    "nodes": [{"node_id": "talk_ingress", "kind": "talk_ingress", "title": title}],
                    "metadata": {
                        "created_from": "ChatMissionIngress",
                        "source_invocation_id": request.invocation.invocation_id,
                    },
                }
            }
        mission_id = str(
            metadata.get("mission_id")
            or invocation_metadata.get("mission_id")
            or self._extract_mission_id(user_text)
            or ""
        ).strip()
        if operation == "control":
            return {
                "mission_id": mission_id,
                "action": str(
                    metadata.get("action")
                    or invocation_metadata.get("action")
                    or self._extract_control_action(user_text)
                    or "pause"
                ).strip().lower()
                or "pause",
            }
        if operation == "feedback":
            feedback = str(
                metadata.get("feedback")
                or invocation_metadata.get("feedback")
                or self._extract_feedback_text(user_text)
                or user_text
            ).strip()
            return {
                "mission_id": mission_id,
                "feedback": feedback,
            }
        return {"mission_id": mission_id}

    def _build_route_projection(self, request: RuntimeRequest, resolved: MissionIngressResolution) -> RouteProjection:
        mode = ""
        if request.delivery_session is not None:
            mode = str(request.delivery_session.mode or "").strip()
        return RouteProjection(
            route_key="mission_ingress",
            workflow_kind="mission",
            target_agent_id=(request.agent_spec.agent_id if request.agent_spec is not None else "butler.mission_ingress"),
            delivery_mode=mode,
            reason=f"mission_operation={resolved.operation}",
            metadata={"workspace": resolved.workspace},
        )

    def _build_workflow_projection(
        self,
        request: RuntimeRequest,
        route: RouteProjection,
        status_payload: Mapping[str, Any],
        operation: str,
    ) -> WorkflowProjection:
        workflow_id = str(status_payload.get("mission_id") or "").strip()
        current_step_id = ""
        nodes = status_payload.get("nodes")
        if isinstance(nodes, list):
            for node in nodes:
                if not isinstance(node, Mapping):
                    continue
                status = str(node.get("status") or "").strip()
                if status in {"ready", "running", "repairing", "awaiting_judge"}:
                    current_step_id = str(node.get("node_id") or "").strip()
                    break
        return WorkflowProjection(
            workflow_id=workflow_id,
            workflow_kind="mission",
            invocation_id=request.invocation.invocation_id,
            status=str(status_payload.get("status") or "pending").strip() or "pending",
            route=route,
            agent_id=request.agent_spec.agent_id if request.agent_spec is not None else "butler.mission_ingress",
            agent_spec_id=request.agent_spec.spec_id if request.agent_spec is not None else "",
            current_step_id=current_step_id,
            metadata={"mission_operation": operation},
        )

    def _build_output_bundle(self, status_payload: Mapping[str, Any], operation: str) -> OutputBundle:
        mission_id = str(status_payload.get("mission_id") or "").strip()
        status = str(status_payload.get("status") or "pending").strip() or "pending"
        title = str(status_payload.get("title") or "").strip()
        node_count = len(status_payload.get("nodes") or []) if isinstance(status_payload.get("nodes"), list) else 0
        summary = f"mission {operation}: {title or mission_id or 'unknown'} [{status}]"
        text = "\n".join(
            [
                f"operation: {operation}",
                f"mission_id: {mission_id or '(pending)'}",
                f"title: {title or '(untitled)'}",
                f"status: {status}",
                f"nodes: {node_count}",
            ]
        )
        return OutputBundle(
            summary=summary,
            text_blocks=[TextBlock(text=text)],
            metadata={"mission_id": mission_id, "mission_operation": operation, "status": status},
        )

    @staticmethod
    def _infer_operation(user_text: str) -> str:
        lowered = str(user_text or "").strip().lower()
        if lowered.startswith("/mission status") or lowered.startswith("mission:status"):
            return "status"
        if lowered.startswith("查询编排任务") or lowered.startswith("查看编排任务"):
            return "status"
        if (
            lowered.startswith("/mission pause")
            or lowered.startswith("/mission resume")
            or lowered.startswith("/mission cancel")
            or lowered.startswith("mission:control")
            or lowered.startswith("暂停编排任务")
            or lowered.startswith("继续编排任务")
            or lowered.startswith("恢复编排任务")
            or lowered.startswith("取消编排任务")
        ):
            return "control"
        if (
            lowered.startswith("/mission feedback")
            or lowered.startswith("mission:feedback")
            or lowered.startswith("补充编排反馈")
        ):
            return "feedback"
        return "create"

    @staticmethod
    def _truncate_title(user_text: str) -> str:
        title = " ".join(str(user_text or "").strip().split())
        if not title:
            return "Talk mission"
        return title[:80]

    @staticmethod
    def _extract_mission_id(text: str) -> str:
        raw = str(text or "").strip()
        matched = _MISSION_ID_RE.search(raw)
        if matched:
            return str(matched.group(1) or "").strip()
        matched = _MISSION_TOKEN_RE.search(raw)
        if matched:
            return str(matched.group(1) or "").strip()
        return ""

    @staticmethod
    def _extract_create_body(text: str) -> str:
        raw = str(text or "").strip()
        for prefix in ("/mission create", "mission:create", "放进编排", "创建编排任务", "新建编排任务"):
            if raw.lower().startswith(prefix.lower()):
                return ButlerMissionOrchestrator._strip_leading_punctuation(raw[len(prefix):])
        return raw

    @staticmethod
    def _extract_control_action(text: str) -> str:
        lowered = str(text or "").strip().lower()
        if lowered.startswith("/mission pause") or lowered.startswith("暂停编排任务"):
            return "pause"
        if lowered.startswith("/mission resume") or lowered.startswith("继续编排任务") or lowered.startswith("恢复编排任务"):
            return "resume"
        if lowered.startswith("/mission cancel") or lowered.startswith("取消编排任务"):
            return "cancel"
        return ""

    @staticmethod
    def _extract_feedback_text(text: str) -> str:
        raw = str(text or "").strip()
        lowered = raw.lower()
        for prefix in ("/mission feedback", "mission:feedback", "补充编排反馈"):
            if lowered.startswith(prefix.lower()):
                body = ButlerMissionOrchestrator._strip_leading_punctuation(raw[len(prefix):])
                body = _MISSION_ID_RE.sub("", body)
                return ButlerMissionOrchestrator._strip_leading_punctuation(body)
        return ""

    @staticmethod
    def _strip_leading_punctuation(text: str) -> str:
        return str(text or "").strip().lstrip("：:，,；;。.- ").strip()


__all__ = ["ButlerMissionOrchestrator", "MissionIngressResolution"]
