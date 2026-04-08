import { KeyboardEvent, startTransition, useEffect, useState } from "react";
import { useAtom } from "jotai";
import { useQueryClient } from "@tanstack/react-query";
import { AlertCircle, FolderSearch, RefreshCcw } from "lucide-react";
import { electronApi } from "./lib/electron-api";
import { WorkbenchShell } from "./components/app-shell/WorkbenchShell";
import { FlowRail } from "./components/navigation/FlowRail";
import { selectedManageAssetIdAtom } from "./state/atoms/manage";
import { actionDraftAtom, conversationLensAtom, statusMessageAtom } from "./state/atoms/ui";
import { configPathAtom, selectedFlowIdAtom } from "./state/atoms/workbench";
import { useFlow } from "./state/queries/use-flow";
import { useHome } from "./state/queries/use-home";
import { useManage } from "./state/queries/use-manage";

const STORAGE_KEY = "butler.desktop.configPath";

function normalizeConfigPath(value: string): string {
  return String(value || "").trim();
}

function firstToken(value: string): string {
  return String(value || "")
    .trim()
    .split(/\s+/)[0]
    .toLowerCase();
}

export default function App() {
  const queryClient = useQueryClient();
  const [manualConfigPath, setManualConfigPath] = useState("");
  const [actionDraft, setActionDraft] = useAtom(actionDraftAtom);
  const [statusMessage, setStatusMessage] = useAtom(statusMessageAtom);
  const [lens, setLens] = useAtom(conversationLensAtom);
  const [configPath, setConfigPath] = useAtom(configPathAtom);
  const [selectedFlowId, setSelectedFlowId] = useAtom(selectedFlowIdAtom);
  const [selectedManageAssetId, setSelectedManageAssetId] = useAtom(selectedManageAssetIdAtom);

  useEffect(() => {
    const savedConfig = window.localStorage.getItem(STORAGE_KEY) || "";
    if (savedConfig) {
      setConfigPath(savedConfig);
      setManualConfigPath(savedConfig);
    }
  }, [setConfigPath]);

  const homeQuery = useHome(configPath);
  const flowQuery = useFlow(configPath, selectedFlowId);
  const manageQuery = useManage(configPath, Boolean(configPath));

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
      queryClient.invalidateQueries({ queryKey: ["desktop", "manage"] }),
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
      instruction,
    });
    setStatusMessage(`Action applied: ${String(payload.action_type || type)}`);
    setActionDraft("");
    await refreshAll();
  }

  async function openArtifact(target: string): Promise<void> {
    const result = await electronApi.openArtifact({ target });
    if (!result.opened) {
      setStatusMessage(`Artifact open failed: ${result.reason || "unknown"}`);
      return;
    }
    setStatusMessage(`Artifact opened: ${target}`);
  }

  async function submitComposer(): Promise<void> {
    const draft = actionDraft.trim();
    if (!draft) {
      return;
    }
    const command = firstToken(draft);
    if (command.startsWith("/")) {
      switch (command) {
        case "/pause":
          await performAction("pause");
          return;
        case "/resume":
          await performAction("resume");
          return;
        case "/retry":
          await performAction("retry_current_phase");
          return;
        case "/studio":
          setLens("studio");
          setActionDraft("");
          setStatusMessage("Studio lens activated in the Manager thread.");
          return;
        case "/recovery":
          setLens("recovery");
          setActionDraft("");
          setStatusMessage("Recovery lens activated in the Manager thread.");
          return;
        case "/mission":
          setLens("mission");
          setActionDraft("");
          setStatusMessage("Mission lens activated in the Manager thread.");
          return;
        case "/open": {
          const target = String(flowQuery.data?.latest_artifact_ref || "").trim();
          if (!target) {
            setStatusMessage("There is no latest artifact to open yet.");
            return;
          }
          setActionDraft("");
          await openArtifact(target);
          return;
        }
        default:
          setStatusMessage("Unknown command. Try /pause, /resume, /retry, /studio, /recovery, /mission, or /open.");
          return;
      }
    }
    await performAction("append_instruction", draft);
  }

  return (
    <div className="desktop-root">
      <FlowRail
        configPath={configPath}
        payload={homeQuery.data}
        selectedFlowId={selectedFlowId}
        onSelectFlow={(flowId) =>
          startTransition(() => {
            setSelectedFlowId(flowId);
            setLens("mission");
          })
        }
        onChooseConfig={() => void chooseConfig()}
      />

      <main className="desktop-main">
        <header className="global-header">
          <div className="global-header-copy">
            <span>Desktop Runtime</span>
            <strong>{configPath || "Select a config to attach the Manager-thread runtime."}</strong>
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
                Butler Desktop renders mission threads through the Python bridge. Attach a `butler_bot.json` or equivalent config to load the
                Manager-thread shell.
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
        ) : (
          <WorkbenchShell
            payload={flowQuery.data}
            managePayload={manageQuery.data}
            loading={flowQuery.isLoading}
            lens={lens}
            actionDraft={actionDraft}
            selectedAssetId={selectedManageAssetId}
            onActionDraftChange={setActionDraft}
            onSubmitComposer={() => void submitComposer()}
            onPause={() => void performAction("pause")}
            onResume={() => void performAction("resume")}
            onRetry={() => void performAction("retry_current_phase")}
            onRefresh={(options) => flowQuery.refetch(options)}
            onLensChange={setLens}
            onSelectAsset={setSelectedManageAssetId}
            onOpenArtifact={(target) => void openArtifact(target)}
          />
        )}

        {homeQuery.error ? <div className="status-toast error">Home load failed: {String(homeQuery.error.message)}</div> : null}
        {flowQuery.error ? <div className="status-toast error">Flow load failed: {String(flowQuery.error.message)}</div> : null}
        {manageQuery.error ? <div className="status-toast error">Studio load failed: {String(manageQuery.error.message)}</div> : null}
        {statusMessage ? <div className="status-toast">{statusMessage}</div> : null}
      </main>
    </div>
  );
}
