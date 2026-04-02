from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agents_os.contracts import ArtifactRef, DeliveryResult, DeliverySession, OutputBundle


_SUPPORTED_DELIVERY_MODES = {"reply", "update", "push"}


@dataclass(slots=True, frozen=True)
class FeishuMessageOperation:
    action: str
    delivery_mode: str
    msg_type: str
    payload: dict[str, Any] = field(default_factory=dict)
    summary: str = ""


@dataclass(slots=True, frozen=True)
class FeishuDeliveryPlan:
    session: DeliverySession
    operations: list[FeishuMessageOperation] = field(default_factory=list)
    rendered_text: str = ""
    artifacts: list[str] = field(default_factory=list)


@dataclass(slots=True)
class FeishuReplySession:
    """Session-shaped delivery abstraction for future create/update/finalize support."""

    session: DeliverySession
    message_id: str = ""
    revision_token: str = ""
    metadata: dict[str, str] = field(default_factory=dict)

    def create(self, bundle: OutputBundle) -> FeishuDeliveryPlan:
        return self._build_plan(action="create", bundle=bundle, delivery_mode=self.session.mode or "reply")

    def update(self, bundle: OutputBundle, *, revision_token: str = "") -> FeishuDeliveryPlan:
        token = str(revision_token or self.revision_token).strip()
        return self._build_plan(
            action="update",
            bundle=bundle,
            delivery_mode="update",
            extra_payload={"revision_token": token},
        )

    def finalize(self, bundle: OutputBundle, *, final_state: str = "completed") -> FeishuDeliveryPlan:
        return self._build_plan(
            action="finalize",
            bundle=bundle,
            delivery_mode=self.session.mode or "reply",
            extra_payload={"final_state": str(final_state or "completed")},
        )

    def _build_plan(
        self,
        *,
        action: str,
        bundle: OutputBundle,
        delivery_mode: str,
        extra_payload: dict[str, Any] | None = None,
    ) -> FeishuDeliveryPlan:
        rendered_text = _render_bundle_text(bundle)
        operation = FeishuMessageOperation(
            action=action,
            delivery_mode=delivery_mode,
            msg_type=_select_message_type(bundle),
            payload={
                "session_target": self.session.target,
                "target_type": self.session.target_type,
                "message_id": self.message_id,
                "text": rendered_text,
                "card_count": len(bundle.cards),
                "image_count": len(bundle.images),
                "file_count": len(bundle.files),
                **dict(extra_payload or {}),
            },
            summary=f"feishu {action} plan for {delivery_mode}",
        )
        artifacts = [artifact.uri for artifact in bundle.artifacts if str(artifact.uri or "").strip()]
        return FeishuDeliveryPlan(
            session=self.session,
            operations=[operation],
            rendered_text=rendered_text,
            artifacts=artifacts,
        )


class FeishuDeliveryAdapter:
    """Translate OutputBundle into Feishu session plans and optionally execute them."""

    platform = "feishu"

    def __init__(
        self,
        *,
        send_reply_text_fn: Callable[[str, str, bool], bool] | None = None,
        send_push_text_fn: Callable[[str, str, str], bool] | None = None,
        upload_image_fn: Callable[[str], str] | None = None,
        reply_image_fn: Callable[[str, str], bool] | None = None,
        push_image_fn: Callable[[str, str, str], bool] | None = None,
        upload_file_fn: Callable[[str], str] | None = None,
        reply_file_fn: Callable[[str, str], bool] | None = None,
        push_file_fn: Callable[[str, str, str], bool] | None = None,
    ) -> None:
        self._send_reply_text_fn = send_reply_text_fn
        self._send_push_text_fn = send_push_text_fn
        self._upload_image_fn = upload_image_fn
        self._reply_image_fn = reply_image_fn
        self._push_image_fn = push_image_fn
        self._upload_file_fn = upload_file_fn
        self._reply_file_fn = reply_file_fn
        self._push_file_fn = push_file_fn

    def open_session(self, session: DeliverySession) -> FeishuReplySession:
        if str(session.platform or "").strip().lower() not in {"", self.platform}:
            raise ValueError(f"unsupported delivery platform: {session.platform}")
        mode = str(session.mode or "reply").strip().lower() or "reply"
        if mode not in _SUPPORTED_DELIVERY_MODES:
            raise ValueError(f"unsupported delivery mode: {mode}")
        metadata = dict(session.metadata or {})
        normalized = DeliverySession(
            platform=self.platform,
            mode=mode,
            target=session.target,
            target_type=session.target_type,
            session_id=session.session_id,
            thread_id=session.thread_id,
            metadata=metadata,
        )
        message_id = str(metadata.get("feishu.message_id") or metadata.get("message_id") or "").strip()
        return FeishuReplySession(session=normalized, message_id=message_id)

    def create(self, session: DeliverySession, bundle: OutputBundle) -> FeishuDeliveryPlan:
        return self.open_session(session).create(bundle)

    def update(
        self,
        session: DeliverySession,
        bundle: OutputBundle,
        *,
        revision_token: str = "",
    ) -> FeishuDeliveryPlan:
        reply_session = self.open_session(session)
        reply_session.revision_token = str(revision_token or "").strip()
        return reply_session.update(bundle, revision_token=revision_token)

    def finalize(
        self,
        session: DeliverySession,
        bundle: OutputBundle,
        *,
        final_state: str = "completed",
    ) -> FeishuDeliveryPlan:
        return self.open_session(session).finalize(bundle, final_state=final_state)

    def deliver(
        self,
        session: DeliverySession,
        bundle: OutputBundle,
        *,
        action: str = "create",
    ) -> DeliveryResult:
        action_name = str(action or "create").strip().lower() or "create"
        if action_name == "update":
            plan = self.update(session, bundle)
        elif action_name == "finalize":
            plan = self.finalize(session, bundle)
        else:
            plan = self.create(session, bundle)
        log = [operation.summary for operation in plan.operations]
        any_sent = False
        message_id = str(plan.operations[0].payload.get("message_id") or "").strip() if plan.operations else ""
        rendered_text = str(plan.rendered_text or "").strip()

        if rendered_text:
            text_ok = self._deliver_text(plan.session, rendered_text, message_id=message_id, include_card_actions=bool(bundle.cards), log=log)
            any_sent = any_sent or text_ok
            if not text_ok:
                return DeliveryResult(
                    delivered=False,
                    session=plan.session,
                    log=log,
                    artifact_refs=list(bundle.artifacts),
                    error=self._resolve_failure_error(log, "text_delivery_failed"),
                )

        image_ok, image_sent = self._deliver_images(plan.session, bundle, message_id=message_id, log=log)
        any_sent = any_sent or image_sent
        if not image_ok:
            return DeliveryResult(
                delivered=False,
                session=plan.session,
                log=log,
                artifact_refs=list(bundle.artifacts),
                error=self._resolve_failure_error(log, "image_delivery_failed"),
            )

        file_ok, file_sent = self._deliver_files(plan.session, bundle, message_id=message_id, log=log)
        any_sent = any_sent or file_sent
        if not file_ok:
            return DeliveryResult(
                delivered=False,
                session=plan.session,
                log=log,
                artifact_refs=list(bundle.artifacts),
                error=self._resolve_failure_error(log, "file_delivery_failed"),
            )

        if not any_sent:
            log.append("transport_not_connected: no transport callback could send this bundle")
            return DeliveryResult(
                delivered=False,
                session=plan.session,
                log=log,
                artifact_refs=list(bundle.artifacts),
                error="transport_not_connected",
            )

        return DeliveryResult(
            delivered=True,
            session=plan.session,
            log=log,
            artifact_refs=list(bundle.artifacts),
            metadata={"rendered_text": rendered_text, "message_id": message_id},
        )

    @staticmethod
    def _resolve_failure_error(log: list[str], default_error: str) -> str:
        for entry in reversed(list(log or [])):
            text = str(entry or "")
            if "transport_missing" in text or "upload_missing" in text:
                return "transport_not_connected"
        return default_error

    def _deliver_text(
        self,
        session: DeliverySession,
        rendered_text: str,
        *,
        message_id: str,
        include_card_actions: bool,
        log: list[str],
    ) -> bool:
        mode = str(session.mode or "reply").strip().lower() or "reply"
        if mode in {"reply", "update"} and message_id and self._send_reply_text_fn is not None:
            if self._send_reply_text_fn(message_id, rendered_text, include_card_actions):
                log.append(f"text_delivered:reply:{message_id}")
                return True
            log.append(f"text_delivery_failed:reply:{message_id}")
            return False
        if self._send_push_text_fn is not None:
            if self._send_push_text_fn(session.target, rendered_text, session.target_type):
                log.append(f"text_delivered:push:{session.target}")
                return True
            log.append(f"text_delivery_failed:push:{session.target}")
            return False
        log.append("text_transport_missing")
        return False

    def _deliver_images(
        self,
        session: DeliverySession,
        bundle: OutputBundle,
        *,
        message_id: str,
        log: list[str],
    ) -> tuple[bool, bool]:
        if not bundle.images:
            return True, False
        if self._upload_image_fn is None:
            log.append("image_upload_missing")
            return False, False
        any_sent = False
        for asset in bundle.images:
            path = str(asset.path or "").strip()
            if not path:
                continue
            image_key = str(self._upload_image_fn(path) or "").strip()
            if not image_key:
                log.append(f"image_upload_failed:{path}")
                return False, any_sent
            mode = str(session.mode or "reply").strip().lower() or "reply"
            if mode in {"reply", "update"} and message_id and self._reply_image_fn is not None:
                if not self._reply_image_fn(message_id, image_key):
                    log.append(f"image_reply_failed:{path}")
                    return False, any_sent
                log.append(f"image_delivered:reply:{path}")
                any_sent = True
                continue
            if self._push_image_fn is not None:
                if not self._push_image_fn(session.target, image_key, session.target_type):
                    log.append(f"image_push_failed:{path}")
                    return False, any_sent
                log.append(f"image_delivered:push:{path}")
                any_sent = True
                continue
            log.append(f"image_transport_missing:{path}")
            return False, any_sent
        return True, any_sent

    def _deliver_files(
        self,
        session: DeliverySession,
        bundle: OutputBundle,
        *,
        message_id: str,
        log: list[str],
    ) -> tuple[bool, bool]:
        if not bundle.files:
            return True, False
        if self._upload_file_fn is None:
            log.append("file_upload_missing")
            return False, False
        any_sent = False
        for asset in bundle.files:
            path = str(asset.path or "").strip()
            if not path:
                continue
            file_key = str(self._upload_file_fn(path) or "").strip()
            if not file_key:
                log.append(f"file_upload_failed:{path}")
                return False, any_sent
            mode = str(session.mode or "reply").strip().lower() or "reply"
            if mode in {"reply", "update"} and message_id and self._reply_file_fn is not None:
                if not self._reply_file_fn(message_id, file_key):
                    log.append(f"file_reply_failed:{path}")
                    return False, any_sent
                log.append(f"file_delivered:reply:{path}")
                any_sent = True
                continue
            if self._push_file_fn is not None:
                if not self._push_file_fn(session.target, file_key, session.target_type):
                    log.append(f"file_push_failed:{path}")
                    return False, any_sent
                log.append(f"file_delivered:push:{path}")
                any_sent = True
                continue
            log.append(f"file_transport_missing:{path}")
            return False, any_sent
        return True, any_sent


def _render_bundle_text(bundle: OutputBundle) -> str:
    lines: list[str] = []
    for block in bundle.text_blocks:
        text = str(block.text or "").strip()
        if text:
            lines.append(text)
    for card in bundle.cards:
        title = str(card.title or "").strip()
        body = str(card.body or "").strip()
        if title and body:
            lines.append(f"{title}\n{body}")
        elif title:
            lines.append(title)
        elif body:
            lines.append(body)
    for link in bundle.doc_links:
        url = str(link.url or "").strip()
        title = str(link.title or "").strip()
        if title and url:
            lines.append(f"{title}: {url}")
        elif url:
            lines.append(url)
    if not lines:
        return ""
    return "\n\n".join(lines).strip()


def _select_message_type(bundle: OutputBundle) -> str:
    if bundle.cards:
        return "interactive"
    if bundle.files or bundle.images:
        return "post"
    return "text"


__all__ = [
    "FeishuDeliveryAdapter",
    "FeishuDeliveryPlan",
    "FeishuMessageOperation",
    "FeishuReplySession",
]
