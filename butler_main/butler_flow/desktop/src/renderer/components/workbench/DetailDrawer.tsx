import type { SingleFlowPayload } from "../../../shared/dto";
import type { DetailTab } from "../../state/atoms/ui";

interface DetailDrawerProps {
  payload?: SingleFlowPayload;
  selectedTab: DetailTab;
  onTabChange: (tab: DetailTab) => void;
  onOpenArtifact: (target: string) => void;
}

function KeyValue({ label, value }: { label: string; value: unknown }) {
  return (
    <div className="kv-row">
      <span>{label}</span>
      <strong>{String(value ?? "—") || "—"}</strong>
    </div>
  );
}

export function DetailDrawer({ payload, selectedTab, onTabChange, onOpenArtifact }: DetailDrawerProps) {
  const summary = payload?.navigator_summary;
  const artifacts = payload?.artifacts || [];
  const inspector = payload?.inspector || {};
  const runtime = (inspector.runtime as Record<string, unknown> | undefined) || {};
  const roleStrip = payload?.role_strip;

  return (
    <aside className="panel-shell panel-drawer">
      <header className="panel-header compact">
        <div>
          <p className="panel-kicker">Detail Drawer</p>
          <h2>Decision, runtime, artifacts</h2>
        </div>
      </header>

      <div className="tab-row">
        {(["summary", "artifacts", "runtime", "roles"] as DetailTab[]).map((tab) => (
          <button
            key={tab}
            className={`tab-button ${selectedTab === tab ? "is-active" : ""}`}
            onClick={() => onTabChange(tab)}
            type="button"
          >
            {tab}
          </button>
        ))}
      </div>

      {selectedTab === "summary" ? (
        <div className="drawer-stack">
          <KeyValue label="Goal" value={summary?.goal} />
          <KeyValue label="Guard" value={summary?.guard_condition} />
          <KeyValue label="Status" value={summary?.effective_status} />
          <KeyValue label="Phase" value={summary?.effective_phase} />
          <KeyValue label="Approval" value={summary?.approval_state} />
          <KeyValue label="Execution Mode" value={summary?.execution_mode} />
          <KeyValue label="Session Strategy" value={summary?.session_strategy} />
          <KeyValue label="Active Role" value={summary?.active_role_id} />
        </div>
      ) : null}

      {selectedTab === "artifacts" ? (
        <div className="drawer-stack">
          {artifacts.length === 0 ? (
            <div className="empty-panel">No artifacts registered yet.</div>
          ) : (
            artifacts.map((artifact, index) => {
              const target = String(artifact.absolute_path || artifact.path || artifact.artifact_ref || "").trim();
              return (
                <div className="artifact-row" key={`${target}-${index}`}>
                  <div>
                    <span>{String(artifact.phase || "runtime")}</span>
                    <strong>{String(artifact.artifact_ref || target || "artifact")}</strong>
                  </div>
                  <button className="ui-button ui-button-secondary" disabled={!target} onClick={() => onOpenArtifact(target)} type="button">
                    Open
                  </button>
                </div>
              );
            })
          )}
        </div>
      ) : null}

      {selectedTab === "runtime" ? (
        <div className="drawer-stack">
          <KeyValue label="Plan Stage" value={(runtime.runtime_plan as Record<string, unknown> | undefined)?.plan_stage} />
          <KeyValue label="Plan Summary" value={(runtime.runtime_plan as Record<string, unknown> | undefined)?.summary} />
          <KeyValue label="Strategy Trace" value={(runtime.strategy_trace as unknown[] | undefined)?.length ?? 0} />
          <KeyValue label="Prompt Packets" value={(runtime.prompt_packets as unknown[] | undefined)?.length ?? 0} />
          <KeyValue label="Mutations" value={(runtime.mutations as unknown[] | undefined)?.length ?? 0} />
        </div>
      ) : null}

      {selectedTab === "roles" ? (
        <div className="drawer-stack">
          <div className="role-chip-row">
            {(roleStrip?.role_chips || []).map((chip, index) => (
              <div className={`role-tile ${chip.is_active ? "is-active" : ""}`} key={`${String(chip.role_id)}-${index}`}>
                <span>{String(chip.state || "idle")}</span>
                <strong>{String(chip.role_id || "unknown")}</strong>
              </div>
            ))}
          </div>
          <KeyValue label="Pending Handoffs" value={roleStrip?.pending_handoffs.length} />
          <KeyValue label="Recent Handoffs" value={roleStrip?.recent_handoffs.length} />
          <KeyValue label="Latest Handoff" value={roleStrip?.latest_handoff_summary.summary} />
        </div>
      ) : null}
    </aside>
  );
}
