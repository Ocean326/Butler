from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
ORCHESTRATOR_DIR = CURRENT_DIR.parent
BUTLER_MAIN_DIR = ORCHESTRATOR_DIR.parent
REPO_ROOT = BUTLER_MAIN_DIR.parent
BUTLER_BOT_DIR = REPO_ROOT / "butler_main" / "butler_bot_code" / "butler_bot"
for candidate in (str(REPO_ROOT), str(BUTLER_MAIN_DIR), str(BUTLER_BOT_DIR)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

from .query_service import OrchestratorQueryService


def _print_json(payload: object) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2))
    sys.stdout.write("\n")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Inspect orchestrator runtime and workflow observation windows")
    subparsers = parser.add_subparsers(dest="command", required=True)

    runtime = subparsers.add_parser("runtime", help="show runtime state")
    runtime.add_argument("--workspace", default=".")
    runtime.add_argument("--stale-seconds", type=int, default=120)

    missions = subparsers.add_parser("missions", help="list mission overview")
    missions.add_argument("--workspace", default=".")
    missions.add_argument("--status", default="")
    missions.add_argument("--limit", type=int, default=20)

    mission = subparsers.add_parser("mission", help="show one mission summary")
    mission.add_argument("--workspace", default=".")
    mission.add_argument("--mission-id", required=True)

    campaigns = subparsers.add_parser("campaigns", help="list campaign overview")
    campaigns.add_argument("--workspace", default=".")
    campaigns.add_argument("--status", default="")
    campaigns.add_argument("--limit", type=int, default=20)

    campaign = subparsers.add_parser("campaign", help="show one campaign summary")
    campaign.add_argument("--workspace", default=".")
    campaign.add_argument("--campaign-id", required=True)

    campaign_artifacts = subparsers.add_parser("campaign-artifacts", help="list campaign artifacts")
    campaign_artifacts.add_argument("--workspace", default=".")
    campaign_artifacts.add_argument("--campaign-id", required=True)

    campaign_events = subparsers.add_parser("campaign-events", help="list campaign events")
    campaign_events.add_argument("--workspace", default=".")
    campaign_events.add_argument("--campaign-id", required=True)
    campaign_events.add_argument("--event-type", default="")
    campaign_events.add_argument("--limit", type=int, default=20)

    campaign_window = subparsers.add_parser("campaign-window", help="show campaign observation window")
    campaign_window.add_argument("--workspace", default=".")
    campaign_window.add_argument("--campaign-id", required=True)
    campaign_window.add_argument("--event-limit", type=int, default=20)
    campaign_window.add_argument("--stale-seconds", type=int, default=120)

    branch = subparsers.add_parser("branch", help="show one branch summary")
    branch.add_argument("--workspace", default=".")
    branch.add_argument("--branch-id", required=True)

    session = subparsers.add_parser("session", help="show one workflow session summary")
    session.add_argument("--workspace", default=".")
    session.add_argument("--session-id", required=True)

    events = subparsers.add_parser("events", help="list recent delivery events")
    events.add_argument("--workspace", default=".")
    events.add_argument("--mission-id", default="")
    events.add_argument("--node-id", default="")
    events.add_argument("--branch-id", default="")
    events.add_argument("--event-type", default="")
    events.add_argument("--limit", type=int, default=20)

    codex = subparsers.add_parser("codex", help="show codex debug window")
    codex.add_argument("--workspace", default=".")
    codex.add_argument("--limit", type=int, default=10)

    window = subparsers.add_parser("window", help="show startup observation window")
    window.add_argument("--workspace", default=".")
    window.add_argument("--mission-limit", type=int, default=8)
    window.add_argument("--branch-limit", type=int, default=8)
    window.add_argument("--event-limit", type=int, default=20)
    window.add_argument("--stale-seconds", type=int, default=120)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    query = OrchestratorQueryService()

    if args.command == "runtime":
        payload = query.get_runtime_status(args.workspace, stale_seconds=args.stale_seconds)
    elif args.command == "missions":
        payload = query.list_missions(args.workspace, status=args.status, limit=args.limit)
    elif args.command == "mission":
        payload = query.get_mission_status(args.workspace, args.mission_id)
    elif args.command == "campaigns":
        payload = query.list_campaigns(args.workspace, status=args.status, limit=args.limit)
    elif args.command == "campaign":
        payload = query.get_campaign_status(args.workspace, args.campaign_id)
    elif args.command == "campaign-artifacts":
        payload = query.list_campaign_artifacts(args.workspace, args.campaign_id)
    elif args.command == "campaign-events":
        payload = query.list_campaign_events(
            args.workspace,
            args.campaign_id,
            event_type=args.event_type,
            limit=args.limit,
        )
    elif args.command == "campaign-window":
        payload = query.get_campaign_observation_window(
            args.workspace,
            args.campaign_id,
            event_limit=args.event_limit,
            stale_seconds=args.stale_seconds,
        )
    elif args.command == "branch":
        payload = query.get_branch_status(args.workspace, args.branch_id)
    elif args.command == "session":
        payload = query.get_workflow_session_status(args.workspace, args.session_id)
    elif args.command == "events":
        payload = query.list_recent_events(
            args.workspace,
            mission_id=args.mission_id,
            node_id=args.node_id,
            branch_id=args.branch_id,
            event_type=args.event_type,
            limit=args.limit,
        )
    elif args.command == "codex":
        payload = query.get_codex_debug_status(args.workspace, limit=args.limit)
    else:
        payload = query.get_startup_observation_window(
            args.workspace,
            mission_limit=args.mission_limit,
            branch_limit=args.branch_limit,
            event_limit=args.event_limit,
            stale_seconds=args.stale_seconds,
        )
    _print_json(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
