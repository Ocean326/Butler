from __future__ import annotations

import argparse
import sys

from butler_main.agents_os.execution.cli_runner import run_prompt_receipt

from .app import FlowApp
from .constants import (
    DEFAULT_CATALOG_FLOW_ID,
    DEFAULT_EXECUTION_LEVEL,
    DEFAULT_LAUNCH_MODE,
    EXECUTION_LEVEL_HIGH,
    EXECUTION_LEVEL_MEDIUM,
    EXECUTION_LEVEL_SIMPLE,
    FREE_CATALOG_FLOW_ID,
    LAUNCH_MODE_FLOW,
    LAUNCH_MODE_SINGLE,
    MANAGED_FLOW_KIND,
    PROJECT_LOOP_KIND,
    ROLE_PACK_CODING_FLOW,
    ROLE_PACK_RESEARCH_FLOW,
    SINGLE_GOAL_KIND,
)
from .tui import run_textual_flow_tui, textual_tui_support
from .version import BUTLER_FLOW_VERSION


class _FlowArgumentParser(argparse.ArgumentParser):
    def format_help(self) -> str:
        text = super().format_help()
        filtered = [line for line in text.splitlines() if "==SUPPRESS==" not in line]
        normalized = "\n".join(filtered)
        for original, replacement in (
            ("  {tui,new,run,resume,exec,status,list,flows,preflight,action}", "  {new,resume,exec}"),
            ("{new,run,resume}", "{new,resume}"),
        ):
            normalized = normalized.replace(original, replacement)
        return normalized + ("\n" if text.endswith("\n") else "")


def _common_parser() -> argparse.ArgumentParser:
    parser = _FlowArgumentParser(add_help=False)
    parser.add_argument("--config", "-c", help="Path to Butler config json")
    return parser


def _add_new_arguments(parser: argparse.ArgumentParser, *, include_plain: bool) -> None:
    parser.add_argument("--mode", dest="launch_mode", choices=(LAUNCH_MODE_SINGLE, LAUNCH_MODE_FLOW), help="Launch mode")
    parser.add_argument("--level", dest="execution_level", choices=(EXECUTION_LEVEL_SIMPLE, EXECUTION_LEVEL_MEDIUM, EXECUTION_LEVEL_HIGH), help="Execution level for flow mode")
    parser.add_argument("--flow", dest="catalog_flow_id", help="Built-in flow id or `free`")
    parser.add_argument("--goal", help="Primary goal for the new flow")
    parser.add_argument("--guard-condition", help="Guard condition for the run")
    parser.add_argument("--max-attempts", type=int, help="Maximum total attempts before stopping")
    parser.add_argument("--max-phase-attempts", type=int, help="Maximum attempts within one project_loop phase")
    parser.add_argument("--no-stream", action="store_true", help="Disable foreground Codex streaming")
    parser.add_argument("--kind", choices=(SINGLE_GOAL_KIND, PROJECT_LOOP_KIND, MANAGED_FLOW_KIND), help=argparse.SUPPRESS)
    parser.add_argument("--execution-mode", choices=(EXECUTION_LEVEL_SIMPLE, EXECUTION_LEVEL_MEDIUM, EXECUTION_LEVEL_HIGH), help=argparse.SUPPRESS)
    parser.add_argument("--role-pack", choices=(ROLE_PACK_CODING_FLOW, ROLE_PACK_RESEARCH_FLOW), help=argparse.SUPPRESS)
    parser.set_defaults(
        kind=SINGLE_GOAL_KIND,
        launch_mode=DEFAULT_LAUNCH_MODE,
        execution_level=DEFAULT_EXECUTION_LEVEL,
        catalog_flow_id=DEFAULT_CATALOG_FLOW_ID,
    )
    if include_plain:
        parser.add_argument("--plain", action="store_true", help="Use the plain setup/attached UI instead of Textual")


def _add_resume_arguments(parser: argparse.ArgumentParser, *, include_plain: bool) -> None:
    parser.add_argument("--flow-id", help="Local flow id")
    parser.add_argument("--workflow-id", help=argparse.SUPPRESS)
    parser.add_argument("--last", action="store_true", help="Resume the most recent local flow state")
    parser.add_argument("--codex-session-id", help="Existing Codex session/thread id")
    parser.add_argument("--mode", dest="launch_mode", choices=(LAUNCH_MODE_SINGLE, LAUNCH_MODE_FLOW), help=argparse.SUPPRESS)
    parser.add_argument("--level", dest="execution_level", choices=(EXECUTION_LEVEL_SIMPLE, EXECUTION_LEVEL_MEDIUM, EXECUTION_LEVEL_HIGH), help=argparse.SUPPRESS)
    parser.add_argument("--flow", dest="catalog_flow_id", help=argparse.SUPPRESS)
    parser.add_argument("--goal", help="Primary goal when deriving a flow from a Codex session id")
    parser.add_argument("--guard-condition", help="Guard condition")
    parser.add_argument("--max-attempts", type=int, help="Maximum total attempts before stopping")
    parser.add_argument("--max-phase-attempts", type=int, help="Maximum attempts within one project_loop phase")
    parser.add_argument("--no-stream", action="store_true", help="Disable foreground Codex streaming")
    parser.add_argument("--kind", choices=(SINGLE_GOAL_KIND, PROJECT_LOOP_KIND, MANAGED_FLOW_KIND), help=argparse.SUPPRESS)
    parser.add_argument("--execution-mode", choices=(EXECUTION_LEVEL_SIMPLE, EXECUTION_LEVEL_MEDIUM, EXECUTION_LEVEL_HIGH), help=argparse.SUPPRESS)
    parser.add_argument("--role-pack", choices=(ROLE_PACK_CODING_FLOW, ROLE_PACK_RESEARCH_FLOW), help=argparse.SUPPRESS)
    if include_plain:
        parser.add_argument("--plain", action="store_true", help="Use the plain attached UI instead of Textual")


def _flow_subcommand_from_argv(argv: list[str]) -> str:
    skip_next = False
    for raw_token in list(argv or []):
        token = str(raw_token or "").strip()
        if not token:
            continue
        if skip_next:
            skip_next = False
            continue
        if token in {"-c", "--config"}:
            skip_next = True
            continue
        if token in {"-h", "--help"}:
            return ""
        if token.startswith("-"):
            continue
        return token
    return ""


def _stdin_is_interactive() -> bool:
    probe = getattr(sys.stdin, "isatty", None)
    try:
        return bool(callable(probe) and probe())
    except Exception:
        return False


def _stdout_is_interactive() -> bool:
    probe = getattr(sys.stdout, "isatty", None)
    try:
        return bool(callable(probe) and probe())
    except Exception:
        return False


def _interactive_textual_tui_support(*, force: bool = False) -> tuple[bool, str]:
    supported, reason = textual_tui_support(force=force)
    if supported:
        return True, ""
    if force:
        return supported, reason
    if str(reason or "").strip() == "TERM=dumb does not support the TUI shell":
        if _stdin_is_interactive() and _stdout_is_interactive():
            return textual_tui_support(force=True)
    return supported, reason


def build_arg_parser() -> argparse.ArgumentParser:
    parser = _FlowArgumentParser(
        prog="butler-flow",
        usage="butler-flow [-h] [--version] {new,resume,exec} ...",
        description="Butler Flow CLI (foreground new, resume, and scripted exec)",
        epilog=(
            "No subcommand on an interactive terminal opens the flow launcher.\n\n"
            "Examples:\n"
            "  butler-flow\n"
            "  butler-flow new\n"
            "  butler-flow new --plain\n"
            "  butler-flow resume --last\n"
            "  butler-flow exec new --mode flow --level medium --flow project_loop --goal \"Ship the flow CLI\"\n"
            "  butler-flow exec resume --last\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {BUTLER_FLOW_VERSION}")
    common = _common_parser()
    subparsers = parser.add_subparsers(dest="command")

    tui_parser = subparsers.add_parser("tui", parents=[common], help=argparse.SUPPRESS)
    tui_parser.add_argument("--flow-id", help=argparse.SUPPRESS)
    tui_parser.add_argument("--last", action="store_true", help=argparse.SUPPRESS)

    new_parser = subparsers.add_parser("new", parents=[common], help="Create a new Butler Flow through the guided setup")
    _add_new_arguments(new_parser, include_plain=True)

    run_parser = subparsers.add_parser("run", parents=[common], help=argparse.SUPPRESS)
    _add_new_arguments(run_parser, include_plain=True)

    resume_parser = subparsers.add_parser("resume", parents=[common], help="Resume a flow by flow id or Codex session id")
    _add_resume_arguments(resume_parser, include_plain=True)

    exec_parser = subparsers.add_parser("exec", help="Run a non-TUI full-flow execution that emits JSONL")
    exec_subparsers = exec_parser.add_subparsers(dest="exec_command")
    exec_new_parser = exec_subparsers.add_parser("new", parents=[common], help="Execute a new flow and emit JSONL")
    _add_new_arguments(exec_new_parser, include_plain=False)
    exec_run_parser = exec_subparsers.add_parser("run", parents=[common], help=argparse.SUPPRESS)
    _add_new_arguments(exec_run_parser, include_plain=False)
    exec_resume_parser = exec_subparsers.add_parser("resume", parents=[common], help="Resume a flow and emit JSONL")
    _add_resume_arguments(exec_resume_parser, include_plain=False)

    status_parser = subparsers.add_parser("status", parents=[common], help=argparse.SUPPRESS)
    status_parser.add_argument("--flow-id", help="Local flow id")
    status_parser.add_argument("--workflow-id", help=argparse.SUPPRESS)
    status_parser.add_argument("--last", action="store_true", help="Inspect the most recent local flow state")
    status_parser.add_argument("--json", action="store_true", help="Print full status payload as JSON")

    list_parser = subparsers.add_parser("list", parents=[common], help=argparse.SUPPRESS)
    list_parser.add_argument("--limit", type=int, default=10, help="Maximum rows to show")
    list_parser.add_argument("--json", action="store_true", help="Print the list as JSON")

    flows_parser = subparsers.add_parser("flows", parents=[common], help=argparse.SUPPRESS)
    flows_parser.add_argument("--limit", type=int, default=10, help=argparse.SUPPRESS)
    flows_parser.add_argument("--json", action="store_true", help=argparse.SUPPRESS)
    flows_parser.add_argument("--manage", help=argparse.SUPPRESS)
    flows_parser.add_argument("--goal", help=argparse.SUPPRESS)
    flows_parser.add_argument("--guard-condition", help=argparse.SUPPRESS)
    flows_parser.add_argument("--instruction", help=argparse.SUPPRESS)
    flows_parser.add_argument("--execution-mode", choices=(EXECUTION_LEVEL_SIMPLE, EXECUTION_LEVEL_MEDIUM, EXECUTION_LEVEL_HIGH), help=argparse.SUPPRESS)
    flows_parser.add_argument("--role-pack", choices=(ROLE_PACK_CODING_FLOW, ROLE_PACK_RESEARCH_FLOW), help=argparse.SUPPRESS)

    preflight_parser = subparsers.add_parser("preflight", parents=[common], help=argparse.SUPPRESS)
    preflight_parser.add_argument("--json", action="store_true", help="Print preflight payload as JSON")

    action_parser = subparsers.add_parser("action", parents=[common], help=argparse.SUPPRESS)
    action_parser.add_argument("--flow-id", help="Local flow id")
    action_parser.add_argument("--workflow-id", help=argparse.SUPPRESS)
    action_parser.add_argument("--last", action="store_true", help="Target the most recent local flow state")
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
            "unbind_repo_contract",
            "abort",
        ),
        help="Operator action type",
    )
    action_parser.add_argument("--instruction", help="Instruction payload for append_instruction")
    action_parser.add_argument("--repo-contract-path", help="Explicit repo contract path for bind_repo_contract")

    return parser


def _new_tui_mode(command: str) -> str:
    token = str(command or "").strip().lower()
    if token == "flows":
        return "manage"
    if token == "resume":
        return "resume"
    return "new"


def main(argv: list[str] | None = None) -> int:
    raw_argv = list(sys.argv[1:] if argv is None else argv)
    if any(str(token or "").strip() == "--version" for token in raw_argv):
        try:
            build_arg_parser().parse_args(raw_argv)
        except SystemExit as exc:
            return int(exc.code or 0)
        return 0
    if not _flow_subcommand_from_argv(raw_argv):
        parser = build_arg_parser()
        if any(str(token or "").strip() in {"-h", "--help"} for token in raw_argv):
            parser.print_help()
            return 0
        if not _stdin_is_interactive():
            parser.print_help()
            return 0
        launcher_parser = _common_parser()
        launcher_args = launcher_parser.parse_args(raw_argv)
        supported, _ = _interactive_textual_tui_support(force=False)
        if supported:
            return run_textual_flow_tui(run_prompt_receipt_fn=run_prompt_receipt, args=launcher_args, mode="launcher")
        app = FlowApp(run_prompt_receipt_fn=run_prompt_receipt, input_fn=input)
        try:
            return app.launcher(launcher_args)
        except KeyboardInterrupt:
            app._display.write("[butler-flow] interrupted", err=True)
            return 130
        except Exception as exc:
            app._display.write(f"[butler-flow] error: {type(exc).__name__}: {exc}", err=True)
            return 1
    parser = build_arg_parser()
    args = parser.parse_args(raw_argv)
    if not getattr(args, "command", ""):
        parser.print_help()
        return 0
    app = FlowApp(run_prompt_receipt_fn=run_prompt_receipt, input_fn=input)
    try:
        if args.command == "tui":
            supported, reason = textual_tui_support(force=True)
            if not supported:
                app._display.write(f"[butler-flow] error: {reason}", err=True)
                return 1
            return run_textual_flow_tui(run_prompt_receipt_fn=run_prompt_receipt, args=args, mode="launcher")
        if args.command == "exec":
            exec_command = str(getattr(args, "exec_command", "") or "").strip()
            if exec_command in {"new", "run"}:
                if not getattr(args, "launch_mode", None):
                    args.launch_mode = DEFAULT_LAUNCH_MODE if exec_command == "new" else DEFAULT_LAUNCH_MODE
                if not getattr(args, "execution_level", None):
                    args.execution_level = DEFAULT_EXECUTION_LEVEL
                if not getattr(args, "catalog_flow_id", None):
                    args.catalog_flow_id = DEFAULT_CATALOG_FLOW_ID
                return app.exec_run(args)
            if exec_command == "resume":
                return app.exec_resume(args)
            parser.print_help()
            return 2
        if args.command == "flows":
            if not _stdout_is_interactive():
                app._display.write("[butler-flow] flows is deprecated. Use `butler-flow list` or `/manage` in the TUI.", err=True)
                return 2
            supported, reason = _interactive_textual_tui_support(force=False)
            if not supported:
                app._display.write(f"[butler-flow] error: {reason}", err=True)
                return 1
            return run_textual_flow_tui(run_prompt_receipt_fn=run_prompt_receipt, args=args, mode="manage")
        if args.command in {"new", "run"}:
            if not bool(getattr(args, "plain", False)) and _stdout_is_interactive():
                supported, _ = _interactive_textual_tui_support(force=False)
                if supported:
                    return run_textual_flow_tui(run_prompt_receipt_fn=run_prompt_receipt, args=args, mode=_new_tui_mode(args.command))
                args.plain = True
            if not _stdout_is_interactive():
                args.launch_mode = getattr(args, "launch_mode", None) or DEFAULT_LAUNCH_MODE
                args.execution_level = getattr(args, "execution_level", None) or DEFAULT_EXECUTION_LEVEL
                args.catalog_flow_id = getattr(args, "catalog_flow_id", None) or DEFAULT_CATALOG_FLOW_ID
            return app.run_new(args)
        if args.command == "resume":
            if not bool(getattr(args, "plain", False)) and _stdout_is_interactive():
                supported, _ = _interactive_textual_tui_support(force=False)
                if supported:
                    return run_textual_flow_tui(run_prompt_receipt_fn=run_prompt_receipt, args=args, mode="resume")
            return app.resume(args)
        if args.command == "preflight":
            return app.preflight(args)
        if args.command == "list":
            return app.list_flows(args)
        if args.command == "status":
            return app.status(args)
        if args.command == "action":
            return app.action(args)
    except KeyboardInterrupt:
        app._display.write("[butler-flow] interrupted", err=True)
        return 130
    except Exception as exc:
        app._display.write(f"[butler-flow] error: {type(exc).__name__}: {exc}", err=True)
        return 1
    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
