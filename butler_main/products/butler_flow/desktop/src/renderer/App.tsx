import { KeyboardEvent, startTransition, useEffect, useState } from "react";
import { useAtom } from "jotai";
import { useQueryClient } from "@tanstack/react-query";
import { AlertCircle, FolderSearch, RefreshCcw } from "lucide-react";
import type { SingleFlowPayload, SurfaceMetaDTO } from "../shared/dto";
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

function normalizeConfigPath(value: string): string {
  return String(value || "").trim();
}

function surfaceTitle(meta: SurfaceMetaDTO | undefined, fallback: string): string {
  return String(meta?.display_title || meta?.title || fallback).trim() || fallback;
}

function HomeView({
  homeTitle,
  flowTitle,
  selectedFlowId,
  onOpenWorkbench,
  summary
}: {
  homeTitle: string;
  flowTitle: string;
  selectedFlowId: string;
  onOpenWorkbench: () => void;
  summary?: SingleFlowPayload["navigator_summary"];
}) {
  return (
    <div className="home-shell">
      <section className="hero-panel">
        <div>
          <p className="panel-kicker">{homeTitle}</p>
          <h2>{summary?.goal || "Focus the next live flow"}</h2>
          <p className="topbar-copy">
            Butler Desktop keeps the contract, latest accepted progress, and recovery cues visible. Pick a flow on the left,
            then open the run console when you want the live execution lane.
          </p>
        </div>
        <button className="ui-button ui-button-primary" disabled={!selectedFlowId} onClick={onOpenWorkbench} type="button">
          Open {flowTitle}
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
              <p className="panel-kicker">Projection Rules</p>
              <h2>Truth-first surface</h2>
            </div>
          </header>
          <ul className="manage-list-plain">
            <li>Renderer reads only the bridge output, never raw sidecars.</li>
            <li>Contract, receipt, and recovery truth stay canonical; the UI stays projection-only.</li>
            <li>Actions route back through the foreground runtime, then the run console refreshes.</li>
          </ul>
        </div>
      </section>
    </div>
  );
}

export default function App() {
  const queryClient = useQueryClient();
  const [manualConfigPath, setManualConfigPath] = useState("");
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
  const homeTitle = surfaceTitle(homeQuery.data?.surface_meta, "Mission Index");
  const flowTitle = surfaceTitle(flowQuery.data?.surface_meta, "Run Console");
  const manageTitle = surfaceTitle(manageQuery.data?.surface_meta, "Contract Studio");

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
    try {
      const result = await electronApi.chooseConfigPath();
      if (result.canceled || !result.configPath) {
        setStatusMessage("Native config picker canceled or unavailable.");
        return;
      }
      const nextConfigPath = normalizeConfigPath(result.configPath);
      window.localStorage.setItem(STORAGE_KEY, nextConfigPath);
      setConfigPath(nextConfigPath);
      setManualConfigPath(nextConfigPath);
      setStatusMessage(`Config attached: ${nextConfigPath}`);
      void queryClient.invalidateQueries({ queryKey: ["desktop"] });
    } catch (error) {
      setStatusMessage(`Config picker failed: ${String((error as Error)?.message || error)}`);
    }
  }

  async function attachConfigPath(pathValue: string): Promise<void> {
    const nextConfigPath = normalizeConfigPath(pathValue);
    if (!nextConfigPath) {
      setStatusMessage("Config path cannot be empty.");
      return;
    }
    window.localStorage.setItem(STORAGE_KEY, nextConfigPath);
    setConfigPath(nextConfigPath);
    setManualConfigPath(nextConfigPath);
    setStatusMessage(`Config attached: ${nextConfigPath}`);
    await queryClient.invalidateQueries({ queryKey: ["desktop"] });
  }

  function onManualConfigKeyDown(event: KeyboardEvent<HTMLInputElement>): void {
    if (event.key !== "Enter") {
      return;
    }
    event.preventDefault();
    void attachConfigPath(manualConfigPath);
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
        flowTitle={flowTitle}
        manageTitle={manageTitle}
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
            <strong>{configPath || "Select a config to start the desktop runtime."}</strong>
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
                The desktop runtime reads live mission-index, run-console, and contract-studio payloads through the Python bridge. Select a
                `butler_bot.json` or equivalent config to continue.
              </p>
              <button className="ui-button ui-button-primary" onClick={() => void chooseConfig()} type="button">
                Select Butler Config
              </button>
              <div className="manual-config-panel">
                <label className="manual-config-label" htmlFor="manual-config-path">
                  Config Path Fallback
                </label>
                <p className="manual-config-copy">
                  If the native file dialog is blocked by your environment, paste the absolute config path here and attach it directly.
                </p>
                <div className="manual-config-form">
                  <input
                    id="manual-config-path"
                    className="action-input"
                    placeholder="/abs/path/to/butler_bot.json"
                    value={manualConfigPath}
                    onChange={(event) => setManualConfigPath(event.target.value)}
                    onKeyDown={onManualConfigKeyDown}
                  />
                  <button
                    className="ui-button ui-button-secondary"
                    disabled={!manualConfigPath.trim()}
                    onClick={() => void attachConfigPath(manualConfigPath)}
                    type="button"
                  >
                    Attach Path
                  </button>
                </div>
              </div>
            </div>
          </section>
        ) : null}

        {configPath && activePage === "home" ? (
          <HomeView
            homeTitle={homeTitle}
            flowTitle={flowTitle}
            selectedFlowId={selectedFlowId}
            onOpenWorkbench={() => setActivePage("flow")}
            summary={selectedSummary}
          />
        ) : null}

        {configPath && activePage === "flow" ? (
          <WorkbenchShell
            payload={flowQuery.data}
            loading={flowQuery.isLoading}
            surfaceTitle={flowTitle}
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
            surfaceTitle={manageTitle}
          />
        ) : null}

        {homeQuery.error ? <div className="status-toast error">Home load failed: {String(homeQuery.error.message)}</div> : null}
        {flowQuery.error ? <div className="status-toast error">Flow load failed: {String(flowQuery.error.message)}</div> : null}
        {statusMessage ? <div className="status-toast">{statusMessage}</div> : null}
      </main>
    </div>
  );
}
