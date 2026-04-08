import { useDeferredValue, useMemo, useState } from "react";
import type { WorkspacePayload } from "../../../shared/dto";

interface FlowRailProps {
  configPath: string;
  payload?: WorkspacePayload;
  selectedFlowId: string;
  onSelectFlow: (flowId: string) => void;
  onChooseConfig: () => void;
}

interface ThreadRow {
  flowId: string;
  goal: string;
  status: string;
  phase: string;
  activeRole: string;
  recoveryState: string;
  latestReceipt: string;
  updatedAt: string;
}

function text(value: unknown, fallback = "—"): string {
  const raw = String(value ?? "").trim();
  return raw || fallback;
}

function record(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : {};
}

function threadRows(payload?: WorkspacePayload): ThreadRow[] {
  return (payload?.flows.items || [])
    .map((row) => {
      const flowId = String(row.flow_id || "").trim();
      const taskContractSummary = record(row.task_contract_summary);
      const latestReceiptSummary = record(row.latest_receipt_summary);
      return {
        flowId,
        goal: text(taskContractSummary.goal || row.goal || flowId, "Untitled mission"),
        status: text(row.effective_status, "unknown"),
        phase: text(row.effective_phase, "idle"),
        activeRole: text(row.active_role_id, "manager"),
        recoveryState: text(row.recovery_state, "tracking"),
        latestReceipt: text(
          latestReceiptSummary.summary || latestReceiptSummary.title || latestReceiptSummary.receipt_kind || latestReceiptSummary.receipt_id,
          "No accepted receipt yet"
        ),
        updatedAt: text(row.updated_at, "")
      };
    })
    .filter((row) => row.flowId)
    .sort((left, right) => String(right.updatedAt).localeCompare(String(left.updatedAt)));
}

export function FlowRail({ configPath, payload, selectedFlowId, onSelectFlow, onChooseConfig }: FlowRailProps) {
  const [search, setSearch] = useState("");
  const deferredSearch = useDeferredValue(search);
  const preflight = payload?.preflight || {};
  const rows = useMemo(() => threadRows(payload), [payload]);
  const filteredRows = rows.filter((row) => {
    const query = deferredSearch.trim().toLowerCase();
    if (!query) {
      return true;
    }
    return [row.flowId, row.goal, row.status, row.phase, row.activeRole, row.recoveryState, row.latestReceipt]
      .map((value) => value.toLowerCase())
      .some((value) => value.includes(query));
  });

  return (
    <aside className="rail-shell">
      <div className="rail-brand">
        <p className="rail-kicker">Butler Desktop</p>
        <h1>Manager Threads</h1>
        <p className="rail-copy">
          One mission, one continuous Manager thread. History stays in the thread list; deeper agent streams stay hidden until you ask for them.
        </p>
      </div>

      <div className="rail-toolbar">
        <button className="ui-button ui-button-primary" onClick={onChooseConfig} type="button">
          {configPath ? "Switch Config" : "Select Config"}
        </button>
        <div className="rail-config">
          <span>Runtime Config</span>
          <strong title={configPath}>{configPath ? text(configPath) : "not selected"}</strong>
        </div>
      </div>

      <div className="rail-section">
        <div className="rail-section-header">
          <span>Mission Threads</span>
          <strong>{filteredRows.length}</strong>
        </div>
        <input
          className="rail-search"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="Search goal, phase, role, receipt"
        />
        <div className="rail-list">
          {filteredRows.length === 0 ? (
            <div className="rail-empty">No manager threads are available for the current config.</div>
          ) : (
            filteredRows.map((row) => {
              const isActive = row.flowId === selectedFlowId;
              return (
                <button
                  key={row.flowId}
                  className={`flow-chip ${isActive ? "is-active" : ""}`}
                  onClick={() => onSelectFlow(row.flowId)}
                  type="button"
                >
                  <div className="flow-chip-topline">
                    <span className="flow-chip-title">{row.goal}</span>
                    <span className="flow-chip-updated">{row.updatedAt || row.flowId}</span>
                  </div>
                  <span className="flow-chip-meta">
                    {row.status} · {row.phase} · {row.activeRole}
                  </span>
                  <span className="flow-chip-goal">{row.latestReceipt}</span>
                  <span className="flow-chip-foot">Recovery: {row.recoveryState}</span>
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
          <strong>{text(preflight.launch_mode || "manager-thread")}</strong>
        </div>
      </div>
    </aside>
  );
}
