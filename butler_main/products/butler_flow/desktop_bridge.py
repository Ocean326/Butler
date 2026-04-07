from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Callable

from butler_main.butler_flow.app import FlowApp
from butler_main.butler_flow.surface import (
    detail_payload,
    manage_center_payload,
    single_flow_payload,
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


def _command_home(args: argparse.Namespace) -> dict[str, Any]:
    return workspace_payload(config=args.config, limit=args.limit)


def _command_flow(args: argparse.Namespace) -> dict[str, Any]:
    return single_flow_payload(config=args.config, flow_id=args.flow_id)


def _command_detail(args: argparse.Namespace) -> dict[str, Any]:
    return detail_payload(config=args.config, flow_id=args.flow_id)


def _command_manage(args: argparse.Namespace) -> dict[str, Any]:
    return manage_center_payload(config=args.config, limit=args.limit)


def _command_preflight(args: argparse.Namespace) -> dict[str, Any]:
    workspace = workspace_payload(config=args.config, limit=1)
    return dict(workspace.get("preflight") or {})


def _command_action(args: argparse.Namespace) -> dict[str, Any]:
    return _build_action_payload(args=args)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m butler_main.butler_flow.desktop_bridge",
        description="Desktop bridge for Butler Flow surface payloads.",
    )
    parser.add_argument("--config", "-c", help="Path to Butler config json")
    subparsers = parser.add_subparsers(dest="command", required=True)

    home_parser = subparsers.add_parser("home", help="Return mission-index payload")
    home_parser.add_argument("--limit", type=int, default=20)
    home_parser.set_defaults(handler=_command_home)

    flow_parser = subparsers.add_parser("flow", help="Return run-console payload")
    flow_parser.add_argument("--flow-id", required=True)
    flow_parser.set_defaults(handler=_command_flow)

    detail_parser = subparsers.add_parser("detail", help="Return detail payload")
    detail_parser.add_argument("--flow-id", required=True)
    detail_parser.set_defaults(handler=_command_detail)

    manage_parser = subparsers.add_parser("manage", help="Return contract-studio payload")
    manage_parser.add_argument("--limit", type=int, default=20)
    manage_parser.set_defaults(handler=_command_manage)

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
