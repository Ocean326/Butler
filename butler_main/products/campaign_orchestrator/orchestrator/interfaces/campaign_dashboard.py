from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from typing import Any, Mapping

from ..workspace import resolve_orchestrator_root
from .query_service import OrchestratorQueryService


def _text(value: Any) -> str:
    return str(value or "").strip()


def _as_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _as_list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _pretty_json(value: Any) -> str:
    return html.escape(json.dumps(value, ensure_ascii=False, indent=2))


def _phase_badge(phase: str) -> str:
    normalized = _text(phase).lower() or "unknown"
    return f'<span class="phase-badge phase-{html.escape(normalized)}">{html.escape(normalized)}</span>'


class CampaignDashboardService:
    """Render a single-campaign read-only dashboard from query service payloads."""

    def __init__(self, *, query_service: OrchestratorQueryService | None = None) -> None:
        self._query = query_service or OrchestratorQueryService()

    def build_payload(
        self,
        workspace: str,
        campaign_id: str,
        *,
        stale_seconds: int = 120,
        event_limit: int = 20,
    ) -> dict[str, Any]:
        return self._query.get_campaign_observation_window(
            workspace,
            campaign_id,
            stale_seconds=stale_seconds,
            event_limit=event_limit,
        )

    def render_dashboard(
        self,
        workspace: str,
        campaign_id: str,
        *,
        stale_seconds: int = 120,
        event_limit: int = 20,
    ) -> str:
        payload = self.build_payload(
            workspace,
            campaign_id,
            stale_seconds=stale_seconds,
            event_limit=event_limit,
        )
        return render_campaign_dashboard_html(payload)

    def write_dashboard(
        self,
        workspace: str,
        campaign_id: str,
        *,
        output_path: str = "",
        stale_seconds: int = 120,
        event_limit: int = 20,
    ) -> Path:
        target = Path(output_path).resolve() if output_path else self.default_output_path(workspace, campaign_id)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            self.render_dashboard(
                workspace,
                campaign_id,
                stale_seconds=stale_seconds,
                event_limit=event_limit,
            ),
            encoding="utf-8",
        )
        return target

    @staticmethod
    def default_output_path(workspace: str, campaign_id: str) -> Path:
        orchestrator_root = Path(resolve_orchestrator_root(workspace))
        return orchestrator_root / "campaigns" / str(campaign_id or "").strip() / "dashboard.html"


def build_campaign_dashboard_payload(
    workspace: str,
    campaign_id: str,
    *,
    query_service: OrchestratorQueryService | None = None,
    stale_seconds: int = 120,
    event_limit: int = 20,
) -> dict[str, Any]:
    return CampaignDashboardService(query_service=query_service).build_payload(
        workspace,
        campaign_id,
        stale_seconds=stale_seconds,
        event_limit=event_limit,
    )


def write_campaign_dashboard(
    *,
    workspace: str,
    campaign_id: str,
    output_path: str = "",
    query_service: OrchestratorQueryService | None = None,
    stale_seconds: int = 120,
    event_limit: int = 20,
) -> Path:
    return CampaignDashboardService(query_service=query_service).write_dashboard(
        workspace,
        campaign_id,
        output_path=output_path,
        stale_seconds=stale_seconds,
        event_limit=event_limit,
    )


def write_campaign_dashboard_html(
    *,
    workspace: str,
    campaign_id: str,
    output_path: str = "",
    query_service: OrchestratorQueryService | None = None,
    stale_seconds: int = 120,
    event_limit: int = 20,
) -> Path:
    return write_campaign_dashboard(
        workspace=workspace,
        campaign_id=campaign_id,
        output_path=output_path,
        query_service=query_service,
        stale_seconds=stale_seconds,
        event_limit=event_limit,
    )


def render_campaign_dashboard_html(payload: Mapping[str, Any]) -> str:
    campaign = _as_dict(payload.get("campaign"))
    campaign_view = _as_dict(payload.get("campaign_view"))
    session_view = _as_dict(payload.get("session_view"))
    verdict_summary = _as_dict(payload.get("verdict_summary"))
    campaign_evidence = _as_dict(payload.get("campaign_evidence"))
    session_evidence = _as_dict(payload.get("session_evidence"))
    phase_timeline = [_as_dict(item) for item in _as_list(payload.get("phase_timeline"))]
    artifacts = [_as_dict(item) for item in _as_list(payload.get("artifacts"))]
    events = [_as_dict(item) for item in _as_list(payload.get("campaign_events"))]
    contract_revisions = [_as_dict(item) for item in _as_list(payload.get("contract_revisions"))]
    runtime = _as_dict(payload.get("runtime"))

    artifact_cards = "".join(
        (
            "<article class='list-card'>"
            f"<header><strong>{html.escape(_text(item.get('label') or item.get('kind')))}</strong>{_phase_badge(_text(item.get('phase')))}</header>"
            f"<p>iteration {int(item.get('iteration') or 0)} · {html.escape(_text(item.get('kind')))}</p>"
            f"<code>{html.escape(_text(item.get('ref')))}</code>"
            "</article>"
        )
        for item in artifacts[:8]
    ) or "<p class='muted'>No artifacts recorded.</p>"

    event_rows = "".join(
        (
            "<tr>"
            f"<td>{html.escape(_text(item.get('created_at')))}</td>"
            f"<td>{html.escape(_text(item.get('event_type')))}</td>"
            f"<td>{html.escape(_text(item.get('phase')))}</td>"
            f"<td>{int(item.get('iteration') or 0)}</td>"
            "</tr>"
        )
        for item in events[:12]
    ) or "<tr><td colspan='4' class='muted'>No events recorded.</td></tr>"

    revision_cards = "".join(
        (
            "<article class='list-card'>"
            f"<header><strong>v{int(item.get('version') or 0)}</strong>{_phase_badge(_text(item.get('last_verdict_decision')) or 'continue')}</header>"
            f"<p>{html.escape(_text(item.get('working_goal')))}</p>"
            f"<p class='muted'>rewrite_count={int(item.get('rewrite_count') or 0)}</p>"
            "</article>"
        )
        for item in contract_revisions
    ) or "<p class='muted'>No contract revisions recorded.</p>"

    timeline_cards = "".join(
        (
            "<article class='list-card'>"
            f"<header><strong>{html.escape(_text(item.get('phase')))}</strong>{_phase_badge(_text(item.get('status')))}</header>"
            f"<p>iteration {int(item.get('iteration') or 0)} -> {html.escape(_text(item.get('next_phase')))}</p>"
            "</article>"
        )
        for item in phase_timeline
    ) or "<p class='muted'>No phase timeline available.</p>"
    session_snapshot = {
        "session_view": session_view,
        "session_evidence": session_evidence,
        "campaign_evidence": campaign_evidence,
        "runtime": {
            "is_stale": runtime.get("is_stale"),
            "last_activity_at": runtime.get("last_activity_at"),
            "runner_state": runtime.get("run_state_payload"),
        },
    }

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Campaign Dashboard · {html.escape(_text(campaign_view.get("title") or campaign.get("campaign_title") or campaign.get("campaign_id")))}</title>
  <style>
    :root {{
      --bg: #f6f0e6;
      --panel: rgba(255, 252, 247, 0.86);
      --panel-strong: #fffaf2;
      --ink: #1f2b2c;
      --muted: #67767a;
      --line: rgba(51, 89, 104, 0.16);
      --accent: #125d79;
      --warm: #c67642;
      --ok: #2f7d53;
      --warn: #b96b1b;
      --danger: #9b3d35;
      --shadow: 0 18px 42px rgba(31, 43, 44, 0.08);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Segoe UI", "PingFang SC", sans-serif;
      color: var(--ink);
      background:
        radial-gradient(circle at top left, rgba(18, 93, 121, 0.14), transparent 30%),
        radial-gradient(circle at top right, rgba(198, 118, 66, 0.14), transparent 24%),
        linear-gradient(180deg, #f7f2ea 0%, var(--bg) 100%);
    }}
    .shell {{
      max-width: 1380px;
      margin: 0 auto;
      padding: 24px 18px 48px;
    }}
    .hero, .panel {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 24px;
      box-shadow: var(--shadow);
      backdrop-filter: blur(6px);
    }}
    .hero {{
      padding: 28px;
      display: grid;
      gap: 18px;
    }}
    .hero-top {{
      display: flex;
      flex-wrap: wrap;
      justify-content: space-between;
      gap: 16px;
      align-items: start;
    }}
    h1, h2 {{
      margin: 0;
      font-family: Georgia, "Noto Serif SC", serif;
      letter-spacing: 0.01em;
    }}
    .subtitle, .muted {{ color: var(--muted); }}
    .metric-grid {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 14px;
    }}
    .metric {{
      background: var(--panel-strong);
      border: 1px solid var(--line);
      border-radius: 18px;
      padding: 16px;
    }}
    .metric strong {{
      display: block;
      font-size: 1.6rem;
      margin-top: 6px;
    }}
    .layout {{
      display: grid;
      grid-template-columns: minmax(0, 2.1fr) minmax(320px, 0.9fr);
      gap: 18px;
      margin-top: 18px;
    }}
    .stack {{
      display: grid;
      gap: 18px;
    }}
    .panel {{
      padding: 20px;
    }}
    .panel header {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: baseline;
      margin-bottom: 14px;
    }}
    .list-grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
    }}
    .list-card {{
      background: var(--panel-strong);
      border: 1px solid var(--line);
      border-radius: 16px;
      padding: 14px;
      display: grid;
      gap: 8px;
    }}
    .list-card header {{
      margin: 0;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }}
    .phase-badge {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-height: 28px;
      padding: 0 10px;
      border-radius: 999px;
      font-size: 0.82rem;
      border: 1px solid var(--line);
      background: rgba(18, 93, 121, 0.08);
      color: var(--accent);
    }}
    .phase-completed, .phase-converge {{ color: var(--ok); background: rgba(47, 125, 83, 0.1); }}
    .phase-recover, .phase-awaiting {{ color: var(--danger); background: rgba(155, 61, 53, 0.1); }}
    .phase-implement, .phase-active, .phase-continue {{ color: var(--accent); }}
    .phase-iterate, .phase-stopped, .phase-warning {{ color: var(--warn); background: rgba(185, 107, 27, 0.12); }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 0.95rem;
    }}
    th, td {{
      text-align: left;
      padding: 10px 8px;
      border-bottom: 1px solid var(--line);
      vertical-align: top;
    }}
    pre {{
      margin: 0;
      white-space: pre-wrap;
      word-break: break-word;
      font-size: 0.86rem;
      background: rgba(16, 29, 34, 0.04);
      border-radius: 14px;
      padding: 14px;
      border: 1px solid var(--line);
      max-height: 360px;
      overflow: auto;
    }}
    code {{
      display: inline-block;
      padding: 2px 6px;
      border-radius: 10px;
      background: rgba(16, 29, 34, 0.06);
    }}
    @media (max-width: 980px) {{
      .metric-grid, .layout, .list-grid {{
        grid-template-columns: 1fr;
      }}
      .shell {{
        padding: 16px 12px 28px;
      }}
      .hero, .panel {{
        border-radius: 18px;
      }}
    }}
  </style>
</head>
<body>
  <main class="shell">
    <section class="hero">
      <div class="hero-top">
        <div>
          <p class="subtitle">Campaign MVP Dashboard</p>
          <h1>{html.escape(_text(campaign_view.get("title") or campaign.get("campaign_title") or campaign.get("campaign_id")))}</h1>
          <p class="subtitle">{html.escape(_text(campaign.get("top_level_goal")))}</p>
          <p class="subtitle">campaign_id: {html.escape(_text(campaign_view.get("campaign_id") or campaign.get("campaign_id")))}</p>
        </div>
        <div>
          {_phase_badge(_text(campaign_view.get("status")) or "unknown")}
          {_phase_badge(_text(campaign_view.get("current_phase")) or "unknown")}
        </div>
      </div>
      <div class="metric-grid">
        <article class="metric"><span class="muted">Iteration</span><strong>{int(campaign_view.get("current_iteration") or 0)}</strong></article>
        <article class="metric"><span class="muted">Artifacts</span><strong>{int(campaign_view.get("artifact_count") or 0)}</strong></article>
        <article class="metric"><span class="muted">Verdicts</span><strong>{int(verdict_summary.get("count") or 0)}</strong></article>
        <article class="metric"><span class="muted">Session Events</span><strong>{int(session_evidence.get("session_event_count") or 0)}</strong></article>
      </div>
    </section>

    <section class="layout">
      <div class="stack">
        <section class="panel">
          <header>
            <h2>Phase Timeline</h2>
            <span class="muted">next: {html.escape(_text(campaign_view.get("next_phase")))}</span>
          </header>
          <div class="list-grid">{timeline_cards}</div>
        </section>

        <section class="panel">
          <header>
            <h2>Artifacts</h2>
            <span class="muted">tracked by campaign artifact index</span>
          </header>
          <div class="list-grid">{artifact_cards}</div>
        </section>

        <section class="panel">
          <header>
            <h2>Event Timeline</h2>
            <span class="muted">{len(events)} campaign events</span>
          </header>
          <table>
            <thead><tr><th>Time</th><th>Event</th><th>Phase</th><th>Iteration</th></tr></thead>
            <tbody>{event_rows}</tbody>
          </table>
        </section>
      </div>

      <aside class="stack">
        <section class="panel">
          <header><h2>Verdict</h2><span class="muted">{html.escape(_text(verdict_summary.get("reviewer_role_id")))}</span></header>
          <p>{_phase_badge(_text(verdict_summary.get("latest_decision")) or "pending")}</p>
          <pre>{_pretty_json(verdict_summary.get("latest") or {})}</pre>
        </section>

        <section class="panel">
          <header><h2>Contract Revisions</h2><span class="muted">{len(contract_revisions)} revision(s)</span></header>
          <div class="stack">{revision_cards}</div>
        </section>

        <section class="panel">
          <header><h2>Session Snapshot</h2><span class="muted">{html.escape(_text(session_view.get("workflow_session_id")))}</span></header>
          <pre>{_pretty_json(session_snapshot)}</pre>
        </section>
      </aside>
    </section>
  </main>
</body>
</html>"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Render a read-only Campaign dashboard to local HTML")
    parser.add_argument("--workspace", default=".")
    parser.add_argument("--campaign-id", required=True)
    parser.add_argument("--output", default="", help="optional explicit html output path")
    parser.add_argument("--event-limit", type=int, default=20)
    parser.add_argument("--stale-seconds", type=int, default=120)
    parser.add_argument("--stdout", action="store_true", help="print HTML to stdout instead of writing a file")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    service = CampaignDashboardService()
    if args.stdout:
        print(
            service.render_dashboard(
                args.workspace,
                args.campaign_id,
                stale_seconds=args.stale_seconds,
                event_limit=args.event_limit,
            )
        )
        return 0
    output = service.write_dashboard(
        args.workspace,
        args.campaign_id,
        output_path=args.output,
        stale_seconds=args.stale_seconds,
        event_limit=args.event_limit,
    )
    print(json.dumps({"output_path": str(output)}, ensure_ascii=False, indent=2))
    return 0


__all__ = [
    "CampaignDashboardService",
    "build_campaign_dashboard_payload",
    "build_parser",
    "main",
    "render_campaign_dashboard_html",
    "write_campaign_dashboard",
    "write_campaign_dashboard_html",
]
