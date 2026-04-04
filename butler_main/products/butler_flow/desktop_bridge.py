from __future__ import annotations

import argparse
import io
import json
import sys
from typing import Any, Callable

from butler_main.agents_os.execution.cli_runner import run_prompt_receipt
from butler_main.butler_flow.app import FlowApp
from butler_main.butler_flow.state import (
    append_manage_turn,
    clear_manage_pending_action,
    now_text,
    read_manage_draft,
    read_manage_session,
    write_manage_draft,
    write_manage_session,
)
from butler_main.butler_flow.surface import (
    agent_focus_payload,
    detail_payload,
    manager_thread_payload,
    manage_center_payload,
    single_flow_payload,
    supervisor_thread_payload,
    template_team_payload,
    thread_home_payload,
    workspace_payload,
)


def _emit_json(payload: Any) -> int:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    return 0


def _build_action_payload(*, args: argparse.Namespace) -> dict[str, Any]:
    app = FlowApp(
        run_prompt_receipt_fn=lambda *a, **k: None,
        input_fn=lambda prompt: "",
        stdout=sys.stdout,
        stderr=sys.stderr,
    )
    return app.apply_action_payload(args)


def _invoke_app_json(method_name: str, *, args: argparse.Namespace) -> dict[str, Any]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    app = FlowApp(
        run_prompt_receipt_fn=run_prompt_receipt,
        input_fn=lambda prompt: "",
        stdout=stdout,
        stderr=stderr,
    )
    payload_args = argparse.Namespace(**vars(args), json=True)
    handler = getattr(app, method_name)
    exit_code = int(handler(payload_args) or 0)
    content = stdout.getvalue().strip()
    if exit_code != 0 and not content:
        raise RuntimeError(stderr.getvalue().strip() or f"{method_name} failed")
    try:
        decoded = json.loads(content or "{}")
    except Exception as exc:
        raise RuntimeError(f"{method_name} returned invalid json: {exc}") from exc
    return decoded if isinstance(decoded, dict) else {}


def _workspace_root_from_config(*, config: str | None) -> str:
    app = FlowApp(
        run_prompt_receipt_fn=lambda *a, **k: None,
        input_fn=lambda prompt: "",
        stdout=io.StringIO(),
        stderr=io.StringIO(),
    )
    preflight = app.build_preflight_payload(argparse.Namespace(config=config, json=False))
    return str(dict(preflight or {}).get("workspace_root") or "").strip()


def _sync_manager_session_after_launch(
    *,
    config: str | None,
    manager_session_id: str,
    chat_payload: dict[str, Any],
    launched_flow: dict[str, Any],
) -> None:
    flow_id = str(launched_flow.get("flow_id") or "").strip()
    if not manager_session_id or not flow_id:
        return
    workspace_root = _workspace_root_from_config(config=config)
    if not workspace_root:
        return
    next_target = f"instance:{flow_id}"
    current_session = read_manage_session(workspace_root, manager_session_id)
    current_draft = read_manage_draft(workspace_root, manager_session_id)
    next_session = {
        **current_session,
        "manager_session_id": manager_session_id,
        "active_manage_target": next_target,
        "manager_stage": "launch",
        "confirmation_scope": "",
        "updated_at": now_text(),
    }
    write_manage_session(workspace_root, manager_session_id, next_session)
    next_draft = {
        **current_draft,
        "manage_target": next_target,
    }
    write_manage_draft(workspace_root, manager_session_id, next_draft)
    clear_manage_pending_action(workspace_root, manager_session_id)
    append_manage_turn(
        workspace_root,
        manager_session_id,
        {
            "created_at": now_text(),
            "manage_target": next_target,
            "instruction": str(chat_payload.get("action_instruction") or "").strip(),
            "response": _format_launch_summary(launched_flow),
            "parse_status": "ok",
            "raw_reply": "",
            "error_text": "",
            "session_recovery": {},
            "manager_stage": "launch",
            "draft": next_draft,
            "pending_action": {},
            "action_ready": False,
            "launched_flow": launched_flow,
        },
    )


def _format_launch_summary(payload: dict[str, Any]) -> str:
    flow_id = str(payload.get("flow_id") or "").strip()
    asset_id = str(payload.get("asset_id") or "").strip()
    summary = str(payload.get("summary") or "").strip()
    if summary:
        return summary
    if flow_id:
        return f"Flow created and handed off to Supervisor: {flow_id}"
    if asset_id:
        return f"Asset updated: {asset_id}"
    return "Manager action completed."


def _command_home(args: argparse.Namespace) -> dict[str, Any]:
    return workspace_payload(config=args.config, limit=args.limit)


def _command_flow(args: argparse.Namespace) -> dict[str, Any]:
    return single_flow_payload(config=args.config, flow_id=args.flow_id)


def _command_detail(args: argparse.Namespace) -> dict[str, Any]:
    return detail_payload(config=args.config, flow_id=args.flow_id)


def _command_manage(args: argparse.Namespace) -> dict[str, Any]:
    return manage_center_payload(config=args.config, limit=args.limit)


def _command_thread_home(args: argparse.Namespace) -> dict[str, Any]:
    return thread_home_payload(config=args.config, limit=args.limit)


def _command_manager_thread(args: argparse.Namespace) -> dict[str, Any]:
    return manager_thread_payload(config=args.config, manager_session_id=args.manager_session_id)


def _command_supervisor_thread(args: argparse.Namespace) -> dict[str, Any]:
    return supervisor_thread_payload(config=args.config, flow_id=args.flow_id)


def _command_agent_focus(args: argparse.Namespace) -> dict[str, Any]:
    return agent_focus_payload(config=args.config, flow_id=args.flow_id, role_id=args.role_id)


def _command_template_team(args: argparse.Namespace) -> dict[str, Any]:
    return template_team_payload(config=args.config, asset_id=args.asset_id)


def _command_preflight(args: argparse.Namespace) -> dict[str, Any]:
    workspace = workspace_payload(config=args.config, limit=1)
    return dict(workspace.get("preflight") or {})


def _command_action(args: argparse.Namespace) -> dict[str, Any]:
    return _build_action_payload(args=args)


def _command_manager_message(args: argparse.Namespace) -> dict[str, Any]:
    chat_payload = _invoke_app_json(
        "manage_chat",
        args=argparse.Namespace(
            config=args.config,
            manage=args.manage,
            instruction=args.instruction,
            manager_session_id=args.manager_session_id,
        ),
    )
    launched_flow: dict[str, Any] = {}
    if (
        str(chat_payload.get("action") or "").strip().lower() == "manage_flow"
        and bool(chat_payload.get("action_ready"))
        and str(chat_payload.get("action_manage_target") or "").strip()
        and str(chat_payload.get("action_instruction") or "").strip()
    ):
        launched_flow = _invoke_app_json(
            "manage_flow",
            args=argparse.Namespace(
                config=args.config,
                manage=str(chat_payload.get("action_manage_target") or "").strip(),
                goal=str(chat_payload.get("action_goal") or "").strip(),
                guard_condition=str(chat_payload.get("action_guard_condition") or "").strip(),
                instruction=str(chat_payload.get("action_instruction") or "").strip(),
                stage=str(chat_payload.get("action_stage") or "").strip(),
                builtin_mode=str(chat_payload.get("action_builtin_mode") or "").strip(),
                draft_payload=dict(chat_payload.get("action_draft") or {}),
            ),
        )
        try:
            # Launch already succeeded; best-effort manager-session sync should not mask that result.
            _sync_manager_session_after_launch(
                config=args.config,
                manager_session_id=str(chat_payload.get("manager_session_id") or "").strip(),
                chat_payload=chat_payload,
                launched_flow=launched_flow,
            )
        except Exception:
            pass
    manager_session_id = str(chat_payload.get("manager_session_id") or args.manager_session_id).strip()
    thread = manager_thread_payload(config=args.config, manager_session_id=manager_session_id)
    return {
        "ok": True,
        "manager_session_id": manager_session_id,
        "message": chat_payload,
        "thread": thread,
        "launched_flow": launched_flow,
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m butler_main.butler_flow.desktop_bridge",
        description="Desktop bridge for Butler Flow surface payloads.",
    )
    parser.add_argument("--config", "-c", help="Path to Butler config json")
    subparsers = parser.add_subparsers(dest="command", required=True)

    home_parser = subparsers.add_parser("home", help="Return workspace payload")
    home_parser.add_argument("--limit", type=int, default=20)
    home_parser.set_defaults(handler=_command_home)

    flow_parser = subparsers.add_parser("flow", help="Return single flow payload")
    flow_parser.add_argument("--flow-id", required=True)
    flow_parser.set_defaults(handler=_command_flow)

    detail_parser = subparsers.add_parser("detail", help="Return detail payload")
    detail_parser.add_argument("--flow-id", required=True)
    detail_parser.set_defaults(handler=_command_detail)

    manage_parser = subparsers.add_parser("manage", help="Return manage-center payload")
    manage_parser.add_argument("--limit", type=int, default=20)
    manage_parser.set_defaults(handler=_command_manage)

    thread_home_parser = subparsers.add_parser("thread-home", help="Return thread-first desktop home payload")
    thread_home_parser.add_argument("--limit", type=int, default=20)
    thread_home_parser.set_defaults(handler=_command_thread_home)

    manager_thread_parser = subparsers.add_parser("manager-thread", help="Return manager thread payload")
    manager_thread_parser.add_argument("--manager-session-id", default="")
    manager_thread_parser.set_defaults(handler=_command_manager_thread)

    supervisor_thread_parser = subparsers.add_parser("supervisor-thread", help="Return supervisor thread payload")
    supervisor_thread_parser.add_argument("--flow-id", required=True)
    supervisor_thread_parser.set_defaults(handler=_command_supervisor_thread)

    agent_focus_parser = subparsers.add_parser("agent-focus", help="Return focused agent stream payload")
    agent_focus_parser.add_argument("--flow-id", required=True)
    agent_focus_parser.add_argument("--role-id", required=True)
    agent_focus_parser.set_defaults(handler=_command_agent_focus)

    template_team_parser = subparsers.add_parser("template-team", help="Return template team payload")
    template_team_parser.add_argument("--asset-id", default="")
    template_team_parser.set_defaults(handler=_command_template_team)

    preflight_parser = subparsers.add_parser("preflight", help="Return preflight payload")
    preflight_parser.set_defaults(handler=_command_preflight)

    action_parser = subparsers.add_parser("action", help="Apply an operator action")
    action_parser.add_argument("--flow-id", required=True)
    action_parser.add_argument(
        "--type",
        required=True,
        choices=(
            "pause",
            "resume",
            "append_instruction",
            "retry_current_phase",
            "shrink_packet",
            "broaden_packet",
            "force_gate",
            "force_doctor",
            "bind_repo_contract",
            "abort",
        ),
    )
    action_parser.add_argument("--instruction", default="")
    action_parser.add_argument("--repo-contract-path", default="")
    action_parser.add_argument("--workflow-id", default="")
    action_parser.add_argument("--last", action="store_true")
    action_parser.set_defaults(handler=_command_action)

    manager_message_parser = subparsers.add_parser("manager-message", help="Send a manager-thread message")
    manager_message_parser.add_argument("--manage", default="new")
    manager_message_parser.add_argument("--instruction", required=True)
    manager_message_parser.add_argument("--manager-session-id", default="")
    manager_message_parser.set_defaults(handler=_command_manager_message)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    handler: Callable[[argparse.Namespace], dict[str, Any]] = args.handler
    try:
        payload = handler(args)
    except Exception as exc:
        sys.stderr.write(
            json.dumps(
                {
                    "ok": False,
                    "error_type": exc.__class__.__name__,
                    "message": str(exc),
                },
                ensure_ascii=False,
            )
            + "\n"
        )
        return 1
    return _emit_json(payload)


if __name__ == "__main__":
    raise SystemExit(main())
