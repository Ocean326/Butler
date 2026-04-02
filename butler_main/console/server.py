from __future__ import annotations

import argparse
import json
import mimetypes
from pathlib import Path
import posixpath
import re
from typing import Any, Iterable
from urllib.parse import parse_qs, unquote
from wsgiref.simple_server import WSGIRequestHandler, WSGIServer, make_server

from .service import ConsoleControlService, ConsoleQueryService
from .types import ControlActionRequest


_ACCESS_RE = re.compile(r"^/console/api/access/?$")
_GLOBAL_BOARD_RE = re.compile(r"^/console/api/global/board/?$")
_CAMPAIGN_GRAPH_RE = re.compile(r"^/console/api/campaigns/([^/]+)/graph/?$")
_CAMPAIGN_BOARD_RE = re.compile(r"^/console/api/campaigns/([^/]+)/board/?$")
_CAMPAIGN_AGENT_DETAIL_RE = re.compile(r"^/console/api/campaigns/([^/]+)/agents/([^/]+)/detail/?$")
_CAMPAIGN_AGENT_PROMPT_SURFACE_RE = re.compile(r"^/console/api/campaigns/([^/]+)/agents/([^/]+)/prompt-surface/?$")
_CAMPAIGN_CONTROL_PLANE_RE = re.compile(r"^/console/api/campaigns/([^/]+)/control-plane/?$")
_CAMPAIGN_TRANSITION_OPTIONS_RE = re.compile(r"^/console/api/campaigns/([^/]+)/transition-options/?$")
_CAMPAIGN_RECOVERY_CANDIDATES_RE = re.compile(r"^/console/api/campaigns/([^/]+)/recovery-candidates/?$")
_CAMPAIGN_AUDIT_ACTIONS_RE = re.compile(r"^/console/api/campaigns/([^/]+)/audit-actions/?$")
_CAMPAIGN_AUDIT_ACTION_DETAIL_RE = re.compile(r"^/console/api/campaigns/([^/]+)/audit-actions/([^/]+)/?$")
_CAMPAIGN_PROMPT_SURFACE_RE = re.compile(r"^/console/api/campaigns/([^/]+)/prompt-surface/?$")
_CAMPAIGN_WORKFLOW_AUTHORING_RE = re.compile(r"^/console/api/campaigns/([^/]+)/workflow-authoring/?$")
_CAMPAIGN_DETAIL_RE = re.compile(r"^/console/api/campaigns/([^/]+)/?$")
_CAMPAIGN_EVENTS_RE = re.compile(r"^/console/api/campaigns/([^/]+)/events/?$")
_CAMPAIGN_EVENTS_STREAM_RE = re.compile(r"^/console/api/campaigns/([^/]+)/events/stream/?$")
_CAMPAIGN_ACTIONS_RE = re.compile(r"^/console/api/campaigns/([^/]+)/actions/?$")
_CAMPAIGN_ARTIFACT_PREVIEW_RE = re.compile(r"^/console/api/campaigns/([^/]+)/artifacts/([^/]+)/preview/?$")
_DRAFT_DETAIL_RE = re.compile(r"^/console/api/drafts/([^/]+)/?$")
_DRAFT_LAUNCH_RE = re.compile(r"^/console/api/drafts/([^/]+)/launch/?$")
_DRAFT_WORKFLOW_AUTHORING_RE = re.compile(r"^/console/api/drafts/([^/]+)/workflow-authoring/?$")
_DRAFT_COMPILE_PREVIEW_RE = re.compile(r"^/console/api/drafts/([^/]+)/compile-preview/?$")
_SKILL_COLLECTION_DETAIL_RE = re.compile(r"^/console/api/skills/collections/([^/]+)/?$")
_SKILL_FAMILY_DETAIL_RE = re.compile(r"^/console/api/skills/families/([^/]+)/?$")
_CHANNEL_SUMMARY_RE = re.compile(r"^/console/api/channels/([^/]+)/?$")

DEFAULT_CONSOLE_HOST = "127.0.0.1"
DEFAULT_CONSOLE_PORT = 8765
DEFAULT_CONSOLE_STALE_SECONDS = 120


def create_console_wsgi_app(
    *,
    workspace: str = ".",
    webapp_root: str | Path | None = None,
    stale_seconds: int = 120,
    host: str = DEFAULT_CONSOLE_HOST,
    port: int = DEFAULT_CONSOLE_PORT,
) -> "ConsoleWSGIApplication":
    return ConsoleWSGIApplication(
        workspace=workspace,
        webapp_root=webapp_root,
        stale_seconds=stale_seconds,
        host=host,
        port=port,
    )


def create_console_http_server(
    host: str = "127.0.0.1",
    port: int = 8765,
    *,
    workspace: str = ".",
    webapp_root: str | Path | None = None,
    stale_seconds: int = 120,
) -> WSGIServer:
    app = create_console_wsgi_app(
        workspace=workspace,
        webapp_root=webapp_root,
        stale_seconds=stale_seconds,
        host=host,
        port=port,
    )
    return make_server(
        host,
        int(port),
        app,
        server_class=WSGIServer,
        handler_class=ConsoleRequestHandler,
    )


def run_console_http_server(
    host: str = "127.0.0.1",
    port: int = 8765,
    *,
    workspace: str = ".",
    webapp_root: str | Path | None = None,
    stale_seconds: int = 120,
) -> int:
    with create_console_http_server(
        host,
        int(port),
        workspace=workspace,
        webapp_root=webapp_root,
        stale_seconds=stale_seconds,
    ) as httpd:
        print(f"Butler console serving on http://{host}:{int(port)}/console/")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:  # pragma: no cover - manual local shutdown
            return 0
    return 0


class ConsoleRequestHandler(WSGIRequestHandler):
    def log_message(self, format: str, *args: object) -> None:  # pragma: no cover - keep local UI output quiet
        return


class ConsoleWSGIApplication:
    _HTML_ASSET_PREFIXES: tuple[tuple[bytes, bytes], ...] = (
        (b'src="/assets/', b'src="/console/assets/'),
        (b"src='/assets/", b"src='/console/assets/"),
        (b'href="/assets/', b'href="/console/assets/'),
        (b"href='/assets/", b"href='/console/assets/"),
    )

    def __init__(
        self,
        *,
        workspace: str = ".",
        webapp_root: str | Path | None = None,
        stale_seconds: int = 120,
        host: str = DEFAULT_CONSOLE_HOST,
        port: int = DEFAULT_CONSOLE_PORT,
    ) -> None:
        self._workspace = str(workspace or ".").strip() or "."
        self._webapp_root = self._resolve_webapp_root(webapp_root)
        self._stale_seconds = max(10, int(stale_seconds or 120))
        self._query = ConsoleQueryService(console_host=host, console_port=port)
        self._control = ConsoleControlService()

    @staticmethod
    def _resolve_webapp_root(webapp_root: str | Path | None) -> Path:
        base_root = Path(webapp_root or (Path(__file__).resolve().parent / "webapp")).resolve()
        dist_root = base_root / "dist"
        if dist_root.exists() and dist_root.is_dir():
            return dist_root.resolve()
        return base_root

    def __call__(self, environ: dict[str, Any], start_response) -> Iterable[bytes]:
        method = str(environ.get("REQUEST_METHOD") or "GET").upper()
        path = posixpath.normpath(str(environ.get("PATH_INFO") or "/"))
        if str(environ.get("PATH_INFO") or "").endswith("/") and not path.endswith("/"):
            path = f"{path}/"
        try:
            if path in {"", "/"}:
                return self._redirect(start_response, "/console/")
            if path.startswith("/console/api/"):
                return self._handle_api(environ, start_response, method, path)
            if path == "/console":
                return self._redirect(start_response, "/console/")
            if path.startswith("/console/"):
                relative_path = path[len("/console/") :]
                if not relative_path:
                    relative_path = "index.html"
                return self._serve_static(relative_path, start_response)
            return self._json_response(start_response, "404 Not Found", {"error": "not_found", "path": path})
        except KeyError as exc:
            return self._json_response(start_response, "404 Not Found", {"error": str(exc)})
        except RuntimeError as exc:
            return self._json_response(start_response, "409 Conflict", {"error": str(exc)})
        except ValueError as exc:
            return self._json_response(start_response, "400 Bad Request", {"error": str(exc)})
        except Exception as exc:  # pragma: no cover - defensive guard for local server
            return self._json_response(start_response, "500 Internal Server Error", {"error": str(exc)})

    def _handle_api(self, environ: dict[str, Any], start_response, method: str, path: str) -> Iterable[bytes]:
        params = parse_qs(str(environ.get("QUERY_STRING") or ""), keep_blank_values=True)
        workspace = self._workspace_value(params)
        if method == "GET" and path == "/console/api/runtime":
            stale_seconds = self._int_param(params, "stale_seconds", self._stale_seconds)
            payload = self._query.get_runtime_status(workspace, stale_seconds=stale_seconds)
            payload["is_stale"] = str(payload.get("process_state") or "").strip().lower() == "stale"
            return self._json_response(start_response, "200 OK", payload)
        if method == "GET" and path == "/console/api/campaigns":
            payload = self._query.list_campaigns(
                workspace,
                status=self._text_param(params, "status"),
                limit=self._int_param(params, "limit", 20),
            )
            return self._json_response(start_response, "200 OK", payload)
        if method == "GET" and path == "/console/api/drafts":
            payload = [item.to_dict() for item in self._query.list_drafts(workspace, limit=self._int_param(params, "limit", 20))]
            return self._json_response(start_response, "200 OK", payload)
        if method == "GET" and path == "/console/api/skills/collections":
            payload = self._query.list_skill_collections(workspace)
            return self._json_response(start_response, "200 OK", payload)
        if method == "GET" and path == "/console/api/skills/search":
            payload = self._query.search_skills(
                workspace,
                query=self._text_param(params, "query"),
                collection_id=self._text_param(params, "collection_id"),
            )
            return self._json_response(start_response, "200 OK", payload)
        if method == "GET" and path == "/console/api/skills/diagnostics":
            payload = self._query.get_skill_diagnostics(workspace)
            return self._json_response(start_response, "200 OK", payload)
        if method == "GET" and _ACCESS_RE.match(path):
            payload = self._query.get_access_diagnostics(workspace).to_dict()
            return self._json_response(start_response, "200 OK", payload)
        if method == "GET" and _GLOBAL_BOARD_RE.match(path):
            payload = self._query.build_global_scheduler_board(workspace, limit=self._int_param(params, "limit", 12)).to_dict()
            return self._json_response(start_response, "200 OK", payload)

        match = _CAMPAIGN_GRAPH_RE.match(path)
        if method == "GET" and match:
            campaign_id = unquote(match.group(1))
            payload = self._query.build_campaign_graph_snapshot(workspace, campaign_id).to_dict()
            return self._json_response(start_response, "200 OK", payload)

        match = _CAMPAIGN_CONTROL_PLANE_RE.match(path)
        if method == "GET" and match:
            campaign_id = unquote(match.group(1))
            payload = self._query.get_campaign_control_plane(workspace, campaign_id)
            return self._json_response(start_response, "200 OK", payload)

        match = _CAMPAIGN_TRANSITION_OPTIONS_RE.match(path)
        if method == "GET" and match:
            campaign_id = unquote(match.group(1))
            payload = self._query.get_campaign_transition_options(workspace, campaign_id)
            return self._json_response(start_response, "200 OK", payload)

        match = _CAMPAIGN_RECOVERY_CANDIDATES_RE.match(path)
        if method == "GET" and match:
            campaign_id = unquote(match.group(1))
            payload = self._query.get_campaign_recovery_candidates(workspace, campaign_id)
            return self._json_response(start_response, "200 OK", payload)

        match = _CAMPAIGN_BOARD_RE.match(path)
        if method == "GET" and match:
            campaign_id = unquote(match.group(1))
            payload = self._query.build_project_board(workspace, campaign_id).to_dict()
            return self._json_response(start_response, "200 OK", payload)

        match = _CAMPAIGN_AGENT_DETAIL_RE.match(path)
        if method == "GET" and match:
            campaign_id = unquote(match.group(1))
            node_id = unquote(match.group(2))
            payload = self._query.build_agent_detail(workspace, campaign_id, node_id).to_dict()
            return self._json_response(start_response, "200 OK", payload)

        match = _CAMPAIGN_AGENT_PROMPT_SURFACE_RE.match(path)
        if method in {"GET", "PATCH"} and match:
            campaign_id = unquote(match.group(1))
            node_id = unquote(match.group(2))
            if method == "GET":
                payload = self._query.get_prompt_surface(workspace, campaign_id, node_id=node_id)
            else:
                body = self._read_json_body(environ)
                payload = self._query.patch_prompt_surface(workspace, campaign_id, patch=body, node_id=node_id)
            return self._json_response(start_response, "200 OK", payload)

        match = _CAMPAIGN_PROMPT_SURFACE_RE.match(path)
        if method in {"GET", "PATCH"} and match:
            campaign_id = unquote(match.group(1))
            if method == "GET":
                payload = self._query.get_prompt_surface(workspace, campaign_id)
            else:
                body = self._read_json_body(environ)
                payload = self._query.patch_prompt_surface(workspace, campaign_id, patch=body)
            return self._json_response(start_response, "200 OK", payload)

        match = _CAMPAIGN_WORKFLOW_AUTHORING_RE.match(path)
        if method in {"GET", "PATCH"} and match:
            campaign_id = unquote(match.group(1))
            if method == "GET":
                payload = self._query.get_campaign_workflow_authoring(workspace, campaign_id)
            else:
                body = self._read_json_body(environ)
                payload = self._query.patch_campaign_workflow_authoring(workspace, campaign_id, body)
            return self._json_response(start_response, "200 OK", payload)

        match = _CAMPAIGN_ARTIFACT_PREVIEW_RE.match(path)
        if method == "GET" and match:
            campaign_id = unquote(match.group(1))
            artifact_id = unquote(match.group(2))
            payload = self._query.build_artifact_preview(workspace, campaign_id, artifact_id).to_dict()
            return self._json_response(start_response, "200 OK", payload)

        match = _CAMPAIGN_EVENTS_STREAM_RE.match(path)
        if method == "GET" and match:
            campaign_id = unquote(match.group(1))
            events = self._query.list_campaign_events(workspace, campaign_id, limit=self._int_param(params, "limit", 20))
            return self._sse_response(start_response, events)

        match = _CAMPAIGN_EVENTS_RE.match(path)
        if method == "GET" and match:
            campaign_id = unquote(match.group(1))
            payload = [item.to_dict() for item in self._query.list_campaign_events(workspace, campaign_id, limit=self._int_param(params, "limit", 20))]
            return self._json_response(start_response, "200 OK", payload)

        match = _CAMPAIGN_AUDIT_ACTION_DETAIL_RE.match(path)
        if method == "GET" and match:
            campaign_id = unquote(match.group(1))
            action_id = unquote(match.group(2))
            payload = self._query.get_audit_action_detail(workspace, campaign_id, action_id)
            return self._json_response(start_response, "200 OK", payload)

        match = _CAMPAIGN_AUDIT_ACTIONS_RE.match(path)
        if method == "GET" and match:
            campaign_id = unquote(match.group(1))
            payload = self._query.list_audit_actions(workspace, campaign_id, limit=self._int_param(params, "limit", 50))
            return self._json_response(start_response, "200 OK", payload)

        match = _CAMPAIGN_ACTIONS_RE.match(path)
        if method == "POST" and match:
            campaign_id = unquote(match.group(1))
            body = self._read_json_body(environ)
            request = ControlActionRequest(
                action=str(body.get("action") or "").strip(),
                target_kind=str(body.get("target_kind") or "campaign").strip() or "campaign",
                target_id=campaign_id,
                target_scope=str(body.get("target_scope") or "campaign").strip() or "campaign",
                target_node_id=str(body.get("target_node_id") or "").strip(),
                transition_to=str(body.get("transition_to") or "").strip(),
                resume_from=str(body.get("resume_from") or "").strip(),
                check_ids=[str(item).strip() for item in body.get("check_ids") or [] if str(item).strip()],
                feedback=str(body.get("feedback") or "").strip(),
                prompt_patch=dict(body.get("prompt_patch") or {}),
                workflow_patch=dict(body.get("workflow_patch") or {}),
                reason=str(body.get("reason") or "").strip(),
                operator_reason=str(body.get("operator_reason") or "").strip(),
                policy_source=str(body.get("policy_source") or "").strip(),
                payload=dict(body.get("payload") or {}),
                operator_id=str(body.get("operator_id") or "").strip(),
                source_surface=str(body.get("source_surface") or "console").strip() or "console",
            )
            result = self._control.apply(workspace, request)
            if not result.ok:
                status = "409 Conflict" if "stale" in str(result.result_summary).lower() else "400 Bad Request"
                return self._json_response(start_response, status, result.to_dict())
            return self._json_response(start_response, "200 OK", result.to_dict())

        match = _CAMPAIGN_DETAIL_RE.match(path)
        if method == "GET" and match:
            campaign_id = unquote(match.group(1))
            payload = self._query.get_campaign_detail(workspace, campaign_id)
            return self._json_response(start_response, "200 OK", payload)

        match = _DRAFT_LAUNCH_RE.match(path)
        if method == "POST" and match:
            draft_id = unquote(match.group(1))
            payload = self._query.launch_draft(workspace, draft_id).to_dict()
            return self._json_response(start_response, "200 OK", payload)

        match = _DRAFT_WORKFLOW_AUTHORING_RE.match(path)
        if method in {"GET", "PATCH"} and match:
            draft_id = unquote(match.group(1))
            if method == "GET":
                payload = self._query.get_draft_workflow_authoring(workspace, draft_id)
            else:
                body = self._read_json_body(environ)
                payload = self._query.patch_draft_workflow_authoring(workspace, draft_id, body)
            return self._json_response(start_response, "200 OK", payload)

        match = _DRAFT_COMPILE_PREVIEW_RE.match(path)
        if method in {"GET", "POST"} and match:
            draft_id = unquote(match.group(1))
            if method == "POST":
                body = self._read_json_body(environ)
                if body:
                    self._query.patch_draft_workflow_authoring(workspace, draft_id, body)
            payload = self._query.get_draft_compile_preview(workspace, draft_id)
            return self._json_response(start_response, "200 OK", payload)

        match = _SKILL_COLLECTION_DETAIL_RE.match(path)
        if method == "GET" and match:
            collection_id = unquote(match.group(1))
            payload = self._query.get_skill_collection_detail(workspace, collection_id)
            if payload is None:
                return self._json_response(start_response, "404 Not Found", {"error": "collection_not_found", "collection_id": collection_id})
            return self._json_response(start_response, "200 OK", payload)

        match = _SKILL_FAMILY_DETAIL_RE.match(path)
        if method == "GET" and match:
            family_id = unquote(match.group(1))
            payload = self._query.get_skill_family_detail(
                workspace,
                family_id=family_id,
                collection_id=self._text_param(params, "collection_id"),
            )
            if payload is None:
                return self._json_response(start_response, "404 Not Found", {"error": "family_not_found", "family_id": family_id})
            return self._json_response(start_response, "200 OK", payload)

        match = _DRAFT_DETAIL_RE.match(path)
        if method == "GET" and match:
            draft_id = unquote(match.group(1))
            payload = self._query.get_draft(workspace, draft_id)
            if payload is None:
                return self._json_response(start_response, "404 Not Found", {"error": "draft_not_found", "draft_id": draft_id})
            return self._json_response(start_response, "200 OK", payload.to_dict())
        if method == "PATCH" and match:
            draft_id = unquote(match.group(1))
            payload = self._query.patch_draft(workspace, draft_id, self._read_json_body(environ)).to_dict()
            return self._json_response(start_response, "200 OK", payload)

        match = _CHANNEL_SUMMARY_RE.match(path)
        if method == "GET" and match:
            session_id = unquote(match.group(1))
            payload = self._query.get_channel_thread_summary(workspace, session_id).to_dict()
            return self._json_response(start_response, "200 OK", payload)

        return self._json_response(start_response, "404 Not Found", {"error": "not_found", "path": path})

    def _serve_static(self, relative_path: str, start_response) -> Iterable[bytes]:
        normalized = posixpath.normpath(relative_path).lstrip("/")
        if normalized in {"", "."}:
            normalized = "index.html"
        file_path = (self._webapp_root / normalized).resolve()
        if self._webapp_root not in file_path.parents and file_path != self._webapp_root:
            return self._json_response(start_response, "403 Forbidden", {"error": "forbidden"})
        if not file_path.exists() or not file_path.is_file():
            return self._json_response(start_response, "404 Not Found", {"error": "asset_not_found", "path": normalized})
        content_type, _ = mimetypes.guess_type(str(file_path))
        payload = file_path.read_bytes()
        if normalized == "index.html":
            payload = self._rewrite_index_asset_paths(payload)
        start_response(
            "200 OK",
            [
                ("Content-Type", content_type or "application/octet-stream"),
                ("Content-Length", str(len(payload))),
                ("Cache-Control", "no-store"),
            ],
        )
        return [payload]

    @classmethod
    def _rewrite_index_asset_paths(cls, payload: bytes) -> bytes:
        rewritten = payload
        for source, target in cls._HTML_ASSET_PREFIXES:
            rewritten = rewritten.replace(source, target)
        return rewritten

    def _redirect(self, start_response, location: str) -> Iterable[bytes]:
        start_response("302 Found", [("Location", location), ("Content-Length", "0")])
        return [b""]

    @staticmethod
    def _json_response(start_response, status: str, payload: Any) -> Iterable[bytes]:
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        start_response(
            status,
            [
                ("Content-Type", "application/json; charset=utf-8"),
                ("Content-Length", str(len(body))),
                ("Cache-Control", "no-store"),
            ],
        )
        return [body]

    @staticmethod
    def _sse_response(start_response, events: list[Any]) -> Iterable[bytes]:
        chunks: list[str] = [": butler-console-event-stream\n\n"]
        for item in events:
            payload = item.to_dict() if hasattr(item, "to_dict") else dict(item)
            chunks.append(f"id: {payload.get('event_id', '')}\n")
            # Use the default EventSource "message" channel so the SPA can
            # subscribe once and still receive every Butler event type.
            chunks.append("event: message\n")
            chunks.append(f"data: {json.dumps(payload, ensure_ascii=False)}\n\n")
        body = "".join(chunks).encode("utf-8")
        start_response(
            "200 OK",
            [
                ("Content-Type", "text/event-stream; charset=utf-8"),
                ("Cache-Control", "no-cache"),
                ("Content-Length", str(len(body))),
            ],
        )
        return [body]

    @staticmethod
    def _read_json_body(environ: dict[str, Any]) -> dict[str, Any]:
        try:
            content_length = int(environ.get("CONTENT_LENGTH") or 0)
        except Exception:
            content_length = 0
        stream = environ.get("wsgi.input")
        if content_length <= 0 or not stream:
            return {}
        raw = stream.read(content_length)
        if not raw:
            return {}
        payload = json.loads(raw.decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("request body must be a JSON object")
        return dict(payload)

    def _workspace_value(self, params: dict[str, list[str]]) -> str:
        value = self._text_param(params, "workspace")
        return value or self._workspace

    @staticmethod
    def _text_param(params: dict[str, list[str]], key: str, default: str = "") -> str:
        values = params.get(key) or []
        value = str(values[0] if values else default).strip()
        return value

    @staticmethod
    def _int_param(params: dict[str, list[str]], key: str, default: int) -> int:
        try:
            value = int((params.get(key) or [default])[0])
        except Exception:
            value = default
        return max(1, value)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the Butler visual console server.")
    parser.add_argument("--config", default="", help="Optional config JSON path")
    parser.add_argument("--workspace", default="")
    parser.add_argument("--host", default="")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--stale-seconds", type=int, default=0)
    args = parser.parse_args(argv)

    config = _load_console_config(args.config)
    workspace = str(args.workspace or config.get("workspace") or ".").strip() or "."
    host = str(args.host or config.get("host") or DEFAULT_CONSOLE_HOST).strip() or DEFAULT_CONSOLE_HOST
    port = int(args.port or config.get("port") or DEFAULT_CONSOLE_PORT)
    stale_seconds = int(args.stale_seconds or config.get("stale_seconds") or DEFAULT_CONSOLE_STALE_SECONDS)

    return run_console_http_server(
        host,
        int(port),
        workspace=workspace,
        stale_seconds=stale_seconds,
    )


def _load_console_config(config_path: str) -> dict[str, Any]:
    path_text = str(config_path or "").strip()
    if not path_text:
        return {}
    path = Path(path_text).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"console config not found: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return {}
    console = payload.get("console")
    if isinstance(console, dict):
        return dict(console)
    return {}


if __name__ == "__main__":
    raise SystemExit(main())
