from __future__ import annotations

import sys
from collections.abc import Callable


ROOT_HELP = """Butler CLI

If no command is specified, arguments are forwarded to the chat CLI.

Usage: butler [CHAT_OPTIONS]
       butler [COMMAND] [ARGS]

Commands:
  chat         Run the Butler chat CLI
  list         List managed Butler services
  status       Show managed Butler service status
  start        Start a managed Butler service
  stop         Stop a managed Butler service
  restart      Restart a managed Butler service
  core         Run the Butler chat core service
  help         Print this message

Foreground flow has moved to the dedicated `butler-flow` CLI.

Examples:
  butler
  butler status
"""

CHAT_ALIASES = {"chat"}
CORE_ALIASES = {"core"}
MANAGER_COMMANDS = {"list", "status", "start", "stop", "restart"}
HELP_ALIASES = {"help", "-h", "--help"}
FLOW_DEPRECATED = {"workflow", "-workflow", "--workflow", "codex-guard"}

FLOW_MIGRATION_HINT = (
    "foreground flow has moved to the dedicated butler-flow CLI.\n"
    "use: butler-flow <command>\n"
    "example: butler-flow run --kind project_loop --goal \"Close the feature gap\"\n"
)


def _chat_main(argv: list[str]) -> int:
    from butler_main.products.chat.cli.bootstrap import main as chat_main

    return chat_main(argv)


def _manager_main(argv: list[str]) -> int:
    from butler_main.platform.host_runtime import manager

    return manager.main(argv)


def _core_main(argv: list[str]) -> int:
    from butler_main.products.chat import core

    return core.main(argv)


def _normalized_command(argv: list[str]) -> tuple[str, list[str]]:
    args = list(argv)
    if not args:
        return "chat", []
    head = str(args[0] or "").strip()
    if head in HELP_ALIASES:
        return "help", args[1:]
    if head in FLOW_DEPRECATED:
        return "flow_deprecated", args[1:]
    if head in CHAT_ALIASES:
        return "chat", args[1:]
    if head in CORE_ALIASES:
        return "core", args[1:]
    if head in MANAGER_COMMANDS:
        return "manager", args
    return "chat", args


def _dispatch_table() -> dict[str, Callable[[list[str]], int]]:
    return {
        "chat": _chat_main,
        "manager": _manager_main,
        "core": _core_main,
    }


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    command, remainder = _normalized_command(args)
    if command == "help":
        sys.stdout.write(ROOT_HELP)
        if not ROOT_HELP.endswith("\n"):
            sys.stdout.write("\n")
        sys.stdout.flush()
        return 0
    if command == "flow_deprecated":
        sys.stderr.write(FLOW_MIGRATION_HINT)
        sys.stderr.flush()
        return 2
    handler = _dispatch_table().get(command)
    if handler is None:
        sys.stderr.write(f"unknown butler command: {command}\n")
        sys.stderr.flush()
        return 2
    return handler(remainder)


if __name__ == "__main__":
    raise SystemExit(main())
