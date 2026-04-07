import { useDeferredValue, useState } from "react";
import type { WorkspacePayload } from "../../../shared/dto";
import type { DesktopPage } from "../../state/atoms/ui";

interface FlowRailProps {
  activePage: DesktopPage;
  configPath: string;
  flowTitle: string;
  manageTitle: string;
  payload?: WorkspacePayload;
  selectedFlowId: string;
  onPageChange: (page: DesktopPage) => void;
  onSelectFlow: (flowId: string) => void;
  onChooseConfig: () => void;
}

function text(value: unknown, fallback = "—"): string {
  const raw = String(value ?? "").trim();
  return raw || fallback;
}

export function FlowRail({
  activePage,
  configPath,
  flowTitle,
  manageTitle,
  payload,
  selectedFlowId,
  onPageChange,
  onSelectFlow,
  onChooseConfig
}: FlowRailProps) {
  const [search, setSearch] = useState("");
  const deferredSearch = useDeferredValue(search);
  const rows = (payload?.flows.items || []).filter((row) => {
    const query = deferredSearch.trim().toLowerCase();
    if (!query) {
      return true;
    }
    return [row.flow_id, row.goal, row.effective_phase, row.active_role_id]
      .map((value) => String(value ?? "").toLowerCase())
      .some((value) => value.includes(query));
  });
  const preflight = payload?.preflight || {};

  return (
    <aside className="rail-shell">
      <div className="rail-brand">
        <p className="rail-kicker">Butler Flow Desktop</p>
        <h1>Mission Console Runtime</h1>
        <p className="rail-copy">
          Keep mission truth visible, keep the bridge thin, and keep every action anchored to the Python surface.
        </p>
      </div>

      <div className="rail-toolbar">
        <button className="ui-button ui-button-primary" onClick={onChooseConfig} type="button">
          {configPath ? "Switch Config" : "Select Config"}
        </button>
        <div className="rail-config">
          <span>Config</span>
          <strong title={configPath}>{configPath ? text(configPath) : "not selected"}</strong>
        </div>
      </div>

      <nav className="rail-nav">
        {[
          ["home", String(payload?.surface_meta?.display_title || "Mission Index")],
          ["flow", flowTitle],
          ["manage", manageTitle]
        ].map(([page, label]) => (
          <button
            key={page}
            className={`rail-nav-button ${activePage === page ? "is-active" : ""}`}
            onClick={() => onPageChange(page as DesktopPage)}
            type="button"
          >
            {label}
          </button>
        ))}
      </nav>

      <div className="rail-section">
        <div className="rail-section-header">
          <span>Flows</span>
          <strong>{rows.length}</strong>
        </div>
        <input
          className="rail-search"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="Search flow, phase, role"
        />
        <div className="rail-list">
          {rows.length === 0 ? (
            <div className="rail-empty">No missions are available for the current config.</div>
          ) : (
            rows.map((row) => {
              const flowId = text(row.flow_id, "");
              const isActive = flowId === selectedFlowId;
              return (
                <button
                  key={flowId}
                  className={`flow-chip ${isActive ? "is-active" : ""}`}
                  onClick={() => onSelectFlow(flowId)}
                  type="button"
                >
                  <span className="flow-chip-title">{flowId}</span>
                  <span className="flow-chip-meta">
                    {text(row.effective_status)} · {text(row.effective_phase)}
                  </span>
                  <span className="flow-chip-goal">{text(row.goal)}</span>
                </button>
              );
            })
          )}
        </div>
      </div>

      <div className="rail-footer">
        <div className="rail-footer-block">
          <span>Execution Root</span>
          <strong title={String(preflight.workspace_root || "")}>{text(preflight.workspace_root)}</strong>
        </div>
        <div className="rail-footer-block">
          <span>Launch Surface</span>
          <strong>{text(preflight.launch_mode || "shared")}</strong>
        </div>
      </div>
    </aside>
  );
}
