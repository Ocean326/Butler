import { startTransition, useEffect } from "react";
import { useAtom } from "jotai";
import { useQueryClient } from "@tanstack/react-query";
import { AlertCircle, FolderSearch, RefreshCcw } from "lucide-react";
import type { SingleFlowPayload } from "../shared/dto";
import { electronApi } from "./lib/electron-api";
import { WorkbenchShell } from "./components/app-shell/WorkbenchShell";
import { ManageCenterShell } from "./components/manage/ManageCenterShell";
import { FlowRail } from "./components/navigation/FlowRail";
import { activePageAtom, actionDraftAtom, detailTabAtom, statusMessageAtom } from "./state/atoms/ui";
import { selectedManageAssetIdAtom } from "./state/atoms/manage";
import { configPathAtom, selectedFlowIdAtom } from "./state/atoms/workbench";
import { useFlow } from "./state/queries/use-flow";
import { useHome } from "./state/queries/use-home";
import { useManage } from "./state/queries/use-manage";

const STORAGE_KEY = "butler.desktop.configPath";

function HomeView({
  selectedFlowId,
  onOpenWorkbench,
  summary
}: {
  selectedFlowId: string;
  onOpenWorkbench: () => void;
  summary?: SingleFlowPayload["navigator_summary"];
}) {
  return (
    <div className="home-shell">
      <section className="hero-panel">
        <div>
          <p className="panel-kicker">Workspace Surface</p>
          <h2>{summary?.goal || "Focus the next live flow"}</h2>
          <p className="topbar-copy">
            Butler Desktop keeps the live supervisor lane in front and pushes detail to the edges. Pick a flow on the left,
            then drill down into the workbench.
          </p>
        </div>
        <button className="ui-button ui-button-primary" disabled={!selectedFlowId} onClick={onOpenWorkbench} type="button">
          Open Workbench
        </button>
      </section>

      <section className="home-grid">
        <div className="panel-shell">
          <header className="panel-header compact">
            <div>
              <p className="panel-kicker">Current Focus</p>
              <h2>{summary?.flow_id || "No flow selected"}</h2>
            </div>
          </header>
          <div className="drawer-stack">
            <div className="kv-row">
              <span>Status</span>
              <strong>{summary?.effective_status || "—"}</strong>
            </div>
            <div className="kv-row">
              <span>Phase</span>
              <strong>{summary?.effective_phase || "—"}</strong>
            </div>
            <div className="kv-row">
              <span>Active Role</span>
              <strong>{summary?.active_role_id || "—"}</strong>
            </div>
            <div className="kv-row">
              <span>Approval</span>
              <strong>{summary?.approval_state || "—"}</strong>
            </div>
          </div>
        </div>
        <div className="panel-shell">
          <header className="panel-header compact">
            <div>
              <p className="panel-kicker">Workbench Rules</p>
              <h2>Shared surface only</h2>
            </div>
          </header>
          <ul className="manage-list-plain">
            <li>Renderer reads only the bridge output, never raw sidecars.</li>
            <li>Supervisor decisions stay in the center lane; runtime detail goes to the drawer.</li>
            <li>Actions route back through the foreground runtime, then the workbench refreshes.</li>
          </ul>
        </div>
      </section>
    </div>
  );
}

export default function App() {
  const queryClient = useQueryClient();
  const [activePage, setActivePage] = useAtom(activePageAtom);
  const [detailTab, setDetailTab] = useAtom(detailTabAtom);
  const [actionDraft, setActionDraft] = useAtom(actionDraftAtom);
  const [statusMessage, setStatusMessage] = useAtom(statusMessageAtom);
  const [configPath, setConfigPath] = useAtom(configPathAtom);
  const [selectedFlowId, setSelectedFlowId] = useAtom(selectedFlowIdAtom);
  const [selectedManageAssetId, setSelectedManageAssetId] = useAtom(selectedManageAssetIdAtom);

  useEffect(() => {
    const savedConfig = window.localStorage.getItem(STORAGE_KEY) || "";
    if (savedConfig) {
      setConfigPath(savedConfig);
    }
  }, [setConfigPath]);

  const homeQuery = useHome(configPath);
  const flowQuery = useFlow(configPath, selectedFlowId);
  const manageQuery = useManage(configPath, activePage === "manage");

  useEffect(() => {
    const firstFlowId = String(homeQuery.data?.flows.items?.[0]?.flow_id || "").trim();
    if (!selectedFlowId && firstFlowId) {
      setSelectedFlowId(firstFlowId);
    }
  }, [homeQuery.data, selectedFlowId, setSelectedFlowId]);

  useEffect(() => {
    const firstAssetId = String(manageQuery.data?.assets.items?.[0]?.asset_id || manageQuery.data?.assets.items?.[0]?.id || "").trim();
    if (!selectedManageAssetId && firstAssetId) {
      setSelectedManageAssetId(firstAssetId);
    }
  }, [manageQuery.data, selectedManageAssetId, setSelectedManageAssetId]);

  async function chooseConfig(): Promise<void> {
    const result = await electronApi.chooseConfigPath();
    if (result.canceled || !result.configPath) {
      return;
    }
    window.localStorage.setItem(STORAGE_KEY, result.configPath);
    setConfigPath(result.configPath);
    setStatusMessage(`Config attached: ${result.configPath}`);
    void queryClient.invalidateQueries({ queryKey: ["desktop"] });
  }

  async function refreshAll(): Promise<void> {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["desktop", "home"] }),
      queryClient.invalidateQueries({ queryKey: ["desktop", "flow"] }),
      queryClient.invalidateQueries({ queryKey: ["desktop", "manage"] })
    ]);
  }

  async function performAction(type: string, instruction?: string): Promise<void> {
    if (!selectedFlowId) {
      return;
    }
    const payload = await electronApi.performAction({
      configPath,
      flowId: selectedFlowId,
      type,
      instruction
    });
    setStatusMessage(`Action applied: ${String(payload.action_type || type)}`);
    if (instruction) {
      setActionDraft("");
    }
    await refreshAll();
  }

  async function openArtifact(target: string): Promise<void> {
    const result = await electronApi.openArtifact({ target });
    if (!result.opened) {
      setStatusMessage(`Artifact open failed: ${result.reason || "unknown"}`);
    }
  }

  const selectedSummary = flowQuery.data?.navigator_summary;

  return (
    <div className="desktop-root">
      <FlowRail
        activePage={activePage}
        configPath={configPath}
        payload={homeQuery.data}
        selectedFlowId={selectedFlowId}
        onPageChange={(page) =>
          startTransition(() => {
            setActivePage(page);
          })
        }
        onSelectFlow={(flowId) =>
          startTransition(() => {
            setSelectedFlowId(flowId);
            setActivePage("flow");
          })
        }
        onChooseConfig={() => void chooseConfig()}
      />

      <main className="desktop-main">
        <header className="global-header">
          <div className="global-header-copy">
            <span>Runtime visible</span>
            <strong>{configPath || "Select a config to start the desktop surface."}</strong>
          </div>
          <div className="global-header-actions">
            <button className="ui-button ui-button-secondary" onClick={() => void chooseConfig()} type="button">
              <FolderSearch size={16} />
              Config
            </button>
            <button className="ui-button ui-button-secondary" onClick={() => void refreshAll()} type="button">
              <RefreshCcw size={16} />
              Refresh
            </button>
          </div>
        </header>

        {!configPath ? (
          <section className="empty-state-shell">
            <div className="empty-state-card">
              <AlertCircle size={34} />
              <h2>Attach a Butler config first</h2>
              <p>
                The desktop workbench reads live workspace, flow, and manage-center payloads through the Python bridge. Select a
                `butler_bot.json` or equivalent config to continue.
              </p>
              <button className="ui-button ui-button-primary" onClick={() => void chooseConfig()} type="button">
                Select Butler Config
              </button>
            </div>
          </section>
        ) : null}

        {configPath && activePage === "home" ? (
          <HomeView
            selectedFlowId={selectedFlowId}
            onOpenWorkbench={() => setActivePage("flow")}
            summary={selectedSummary}
          />
        ) : null}

        {configPath && activePage === "flow" ? (
          <WorkbenchShell
            payload={flowQuery.data}
            loading={flowQuery.isLoading}
            actionDraft={actionDraft}
            onActionDraftChange={setActionDraft}
            onAppendInstruction={() => void performAction("append_instruction", actionDraft)}
            onPause={() => void performAction("pause")}
            onResume={() => void performAction("resume")}
            onRetry={() => void performAction("retry_current_phase")}
            onRefresh={(options) => flowQuery.refetch(options)}
            detailTab={detailTab}
            onDetailTabChange={setDetailTab}
            onOpenArtifact={(target) => void openArtifact(target)}
          />
        ) : null}

        {configPath && activePage === "manage" ? (
          <ManageCenterShell
            payload={manageQuery.data}
            selectedAssetId={selectedManageAssetId}
            onSelectAsset={setSelectedManageAssetId}
          />
        ) : null}

        {homeQuery.error ? <div className="status-toast error">Home load failed: {String(homeQuery.error.message)}</div> : null}
        {flowQuery.error ? <div className="status-toast error">Flow load failed: {String(flowQuery.error.message)}</div> : null}
        {statusMessage ? <div className="status-toast">{statusMessage}</div> : null}
      </main>
    </div>
  );
}
