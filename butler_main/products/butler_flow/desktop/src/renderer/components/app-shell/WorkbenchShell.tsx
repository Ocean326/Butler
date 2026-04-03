import type { QueryObserverResult, RefetchOptions } from "@tanstack/react-query";
import type { SingleFlowPayload } from "../../../shared/dto";
import type { DetailTab } from "../../state/atoms/ui";
import { DetailDrawer } from "../workbench/DetailDrawer";
import { SupervisorStream } from "../workbench/SupervisorStream";
import { WorkflowStrip } from "../workbench/WorkflowStrip";

interface WorkbenchShellProps {
  payload?: SingleFlowPayload;
  loading: boolean;
  actionDraft: string;
  onActionDraftChange: (value: string) => void;
  onAppendInstruction: () => void;
  onPause: () => void;
  onResume: () => void;
  onRetry: () => void;
  onRefresh: (options?: RefetchOptions) => Promise<QueryObserverResult<SingleFlowPayload, Error>>;
  detailTab: DetailTab;
  onDetailTabChange: (tab: DetailTab) => void;
  onOpenArtifact: (target: string) => void;
}

export function WorkbenchShell({
  payload,
  loading,
  actionDraft,
  onActionDraftChange,
  onAppendInstruction,
  onPause,
  onResume,
  onRetry,
  onRefresh,
  detailTab,
  onDetailTabChange,
  onOpenArtifact
}: WorkbenchShellProps) {
  const summary = payload?.navigator_summary;
  const status = String(summary?.effective_status || "unknown");
  const canPause = status === "running";
  const canResume = status === "paused";

  return (
    <div className="workbench-shell">
      <header className="workbench-topbar">
        <div>
          <p className="panel-kicker">Flow Workbench</p>
          <h2>{summary?.goal || payload?.flow_id || "Select a flow"}</h2>
          <p className="topbar-copy">
            {summary?.guard_condition || "The shared surface drives this workbench. Actions route back through the Python foreground runtime."}
          </p>
        </div>
        <div className="topbar-actions">
          <button className="ui-button ui-button-secondary" onClick={() => void onRefresh()} type="button">
            Refresh
          </button>
          <button className="ui-button ui-button-secondary" disabled={!canPause} onClick={onPause} type="button">
            Pause
          </button>
          <button className="ui-button ui-button-secondary" disabled={!canResume} onClick={onResume} type="button">
            Resume
          </button>
          <button className="ui-button ui-button-secondary" disabled={!canResume} onClick={onRetry} type="button">
            Retry
          </button>
        </div>
      </header>

      <div className="action-rack">
        <input
          className="action-input"
          placeholder="Append an operator instruction for the next supervisor turn"
          value={actionDraft}
          onChange={(event) => onActionDraftChange(event.target.value)}
        />
        <button className="ui-button ui-button-primary" disabled={!actionDraft.trim()} onClick={onAppendInstruction} type="button">
          Send Instruction
        </button>
      </div>

      {loading ? <div className="empty-panel shell-loading">Loading flow workbench…</div> : null}

      <div className="workbench-grid">
        <div className="workbench-main">
          <SupervisorStream view={payload?.supervisor_view} />
          <WorkflowStrip payload={payload} />
        </div>
        <DetailDrawer
          payload={payload}
          selectedTab={detailTab}
          onTabChange={onDetailTabChange}
          onOpenArtifact={onOpenArtifact}
        />
      </div>
    </div>
  );
}
