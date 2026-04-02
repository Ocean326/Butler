from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from agents_os.contracts import DeliveryResult, DeliverySession, OutputBundle

from .official import (
    WEIXIN_ITEM_TYPE_FILE,
    WEIXIN_ITEM_TYPE_IMAGE,
    WEIXIN_ITEM_TYPE_VIDEO,
    build_media_sendmessage_request,
    build_sendmessage_request,
    bundle_to_text,
    new_client_id,
)


_SUPPORTED_DELIVERY_MODES = {"reply", "update", "push"}


@dataclass(slots=True, frozen=True)
class WeixinMessageOperation:
    action: str
    delivery_mode: str
    endpoint: str
    request_body: dict[str, Any]
    summary: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class WeixinDeliveryPlan:
    session: DeliverySession
    operations: list[WeixinMessageOperation] = field(default_factory=list)
    rendered_text: str = ""
    official_requests: list[dict[str, Any]] = field(default_factory=list)


@dataclass(slots=True)
class WeixinReplySession:
    session: DeliverySession
    message_id: str = ""
    context_token: str = ""
    account_id: str = ""

    def create(self, bundle: OutputBundle) -> WeixinDeliveryPlan:
        return self._build_plan(action="create", bundle=bundle, delivery_mode=self.session.mode or "reply")

    def update(self, bundle: OutputBundle, *, revision_token: str = "") -> WeixinDeliveryPlan:
        return self._build_plan(
            action="update",
            bundle=bundle,
            delivery_mode="update",
            extra_metadata={"revision_token": str(revision_token or "").strip()},
        )

    def finalize(self, bundle: OutputBundle, *, final_state: str = "completed") -> WeixinDeliveryPlan:
        return self._build_plan(
            action="finalize",
            bundle=bundle,
            delivery_mode=self.session.mode or "reply",
            extra_metadata={"final_state": str(final_state or "completed")},
        )

    def _build_plan(
        self,
        *,
        action: str,
        bundle: OutputBundle,
        delivery_mode: str,
        extra_metadata: dict[str, Any] | None = None,
    ) -> WeixinDeliveryPlan:
        operations: list[WeixinMessageOperation] = []
        official_requests: list[dict[str, Any]] = []
        rendered_text = bundle_to_text(bundle)
        base_metadata = dict(extra_metadata or {})
        conversation_key = str(self.session.metadata.get("weixin.conversation_key") or "").strip()
        if conversation_key:
            base_metadata["weixin.conversation_key"] = conversation_key
        chat_type = str(self.session.metadata.get("weixin.chat_type") or "").strip()
        if chat_type:
            base_metadata["weixin.chat_type"] = chat_type
        if rendered_text:
            request = build_sendmessage_request(
                session=self.session,
                text=rendered_text,
                context_token=self.context_token,
                client_id=new_client_id("butler-weixin-text"),
            )
            operations.append(
                WeixinMessageOperation(
                    action=action,
                    delivery_mode=delivery_mode,
                    endpoint="ilink/bot/sendmessage",
                    request_body=request,
                    summary=f"weixin {action} text",
                    metadata=dict(base_metadata),
                )
            )
            official_requests.append(request)
        for image in bundle.images:
            path = str(image.path or "").strip()
            if not path:
                continue
            request = build_media_sendmessage_request(
                session=self.session,
                item_type=WEIXIN_ITEM_TYPE_IMAGE,
                local_path=path,
                context_token=self.context_token,
                client_id=new_client_id("butler-weixin-image"),
            )
            operations.append(
                WeixinMessageOperation(
                    action=action,
                    delivery_mode=delivery_mode,
                    endpoint="ilink/bot/sendmessage",
                    request_body=request,
                    summary=f"weixin {action} image",
                    metadata={"local_path": path, **dict(base_metadata)},
                )
            )
            official_requests.append(request)
        for asset in bundle.files:
            path = str(asset.path or "").strip()
            if not path:
                continue
            request = build_media_sendmessage_request(
                session=self.session,
                item_type=_infer_media_item_type(path),
                local_path=path,
                context_token=self.context_token,
                client_id=new_client_id("butler-weixin-file"),
            )
            operations.append(
                WeixinMessageOperation(
                    action=action,
                    delivery_mode=delivery_mode,
                    endpoint="ilink/bot/sendmessage",
                    request_body=request,
                    summary=f"weixin {action} file",
                    metadata={"local_path": path, **dict(base_metadata)},
                )
            )
            official_requests.append(request)
        return WeixinDeliveryPlan(
            session=self.session,
            operations=operations,
            rendered_text=rendered_text,
            official_requests=official_requests,
        )


class WeixinDeliveryAdapter:
    """Translate OutputBundle into Weixin bridge HTTP/JSON requests."""

    platform = "weixin"

    def __init__(
        self,
        *,
        send_request_fn: Callable[[dict[str, Any]], bool] | None = None,
    ) -> None:
        self._send_request_fn = send_request_fn

    def open_session(self, session: DeliverySession) -> WeixinReplySession:
        if str(session.platform or "").strip().lower() not in {"", self.platform, "weixi", "wechat"}:
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
        return WeixinReplySession(
            session=normalized,
            message_id=str(metadata.get("weixin.message_id") or metadata.get("message_id") or "").strip(),
            context_token=str(metadata.get("weixin.context_token") or "").strip(),
            account_id=str(metadata.get("weixin.account_id") or "").strip(),
        )

    def create(self, session: DeliverySession, bundle: OutputBundle) -> WeixinDeliveryPlan:
        return self.open_session(session).create(bundle)

    def update(self, session: DeliverySession, bundle: OutputBundle, *, revision_token: str = "") -> WeixinDeliveryPlan:
        return self.open_session(session).update(bundle, revision_token=revision_token)

    def finalize(self, session: DeliverySession, bundle: OutputBundle, *, final_state: str = "completed") -> WeixinDeliveryPlan:
        return self.open_session(session).finalize(bundle, final_state=final_state)

    def deliver(self, session: DeliverySession, bundle: OutputBundle, *, action: str = "create") -> DeliveryResult:
        action_name = str(action or "create").strip().lower() or "create"
        if action_name == "update":
            plan = self.update(session, bundle)
        elif action_name == "finalize":
            plan = self.finalize(session, bundle)
        else:
            plan = self.create(session, bundle)
        log = [operation.summary for operation in plan.operations]
        if self._send_request_fn is None:
            log.append("transport_not_connected: send_request_fn missing")
            return DeliveryResult(
                delivered=False,
                session=plan.session,
                log=log,
                artifact_refs=list(bundle.artifacts),
                error="transport_not_connected",
                metadata={"official_requests": list(plan.official_requests)},
            )
        for request in plan.official_requests:
            if not self._send_request_fn(request):
                log.append("request_delivery_failed")
                return DeliveryResult(
                    delivered=False,
                    session=plan.session,
                    log=log,
                    artifact_refs=list(bundle.artifacts),
                    error="request_delivery_failed",
                    metadata={"official_requests": list(plan.official_requests)},
                )
        log.append(f"requests_delivered:{len(plan.official_requests)}")
        return DeliveryResult(
            delivered=True,
            session=plan.session,
            log=log,
            artifact_refs=list(bundle.artifacts),
            metadata={"official_requests": list(plan.official_requests)},
        )


def _infer_media_item_type(path: str) -> int:
    normalized = str(path or "").strip().lower()
    if normalized.endswith((".mp4", ".mov", ".avi", ".mkv", ".webm")):
        return WEIXIN_ITEM_TYPE_VIDEO
    if normalized.endswith((".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp")):
        return WEIXIN_ITEM_TYPE_IMAGE
    return WEIXIN_ITEM_TYPE_FILE


__all__ = [
    "WeixinDeliveryAdapter",
    "WeixinDeliveryPlan",
    "WeixinMessageOperation",
    "WeixinReplySession",
]
