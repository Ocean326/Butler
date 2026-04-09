import { FormEvent, KeyboardEvent, startTransition, useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { electronApi, isDesktopBridgeAvailable } from "./lib/electron-api";
import {
  AgentDetailSheet,
  BridgeMissingState,
  DesktopRail,
  EmptyAttachState,
  MissionShell,
  type MissionStatusTone
} from "./components/mission-shell/MissionShell";
import {
  autoResizeTextarea,
  buildManagerThreads,
  composerLabel,
  composerPlaceholder,
  formatValue,
  isHistoricalStatus,
  normalizeConfigPath,
  type ConversationMode
} from "./lib/mission-shell";
import {
  useAgentFocus,
  useManagerThread,
  useSupervisorThread,
  useTemplateTeam,
  useThreadHome
} from "./state/queries/use-thread-workbench";

const CONFIG_STORAGE_KEY = "butler.desktop.configPath";
const THEME_STORAGE_KEY = "butler.desktop.theme";

type DetailState =
  | { kind: "none" }
  | { kind: "agent"; flowId: string; roleId: string };

function queryErrorText(scope: string, error: unknown): string {
  const token = String((error as Error)?.message || error || "").trim();
  return token ? `${scope} failed: ${token}` : `${scope} failed.`;
}

export default function App() {
  const queryClient = useQueryClient();
  const composerRef = useRef<HTMLTextAreaElement>(null);
  const [manualConfigPath, setManualConfigPath] = useState("");
  const [configPath, setConfigPath] = useState("");
  const [theme, setTheme] = useState<"day" | "night">("night");
  const [managerSessionId, setManagerSessionId] = useState("");
  const [isComposingNewThread, setIsComposingNewThread] = useState(false);
  const [mode, setMode] = useState<ConversationMode>("mission");
  const [templateAssetId, setTemplateAssetId] = useState("");
  const [detailState, setDetailState] = useState<DetailState>({ kind: "none" });
  const [messageDraft, setMessageDraft] = useState("");
  const [statusMessage, setStatusMessage] = useState("");
  const [sendingManagerMessage, setSendingManagerMessage] = useState(false);
  const [expandedBlocks, setExpandedBlocks] = useState<Record<string, boolean>>({});
  const bridgeAvailable = isDesktopBridgeAvailable();

  useEffect(() => {
    const savedConfig = window.localStorage.getItem(CONFIG_STORAGE_KEY) || "";
    if (savedConfig) {
      setConfigPath(savedConfig);
      setManualConfigPath(savedConfig);
    }
    const savedTheme = window.localStorage.getItem(THEME_STORAGE_KEY);
    if (savedTheme === "day" || savedTheme === "night") {
      setTheme(savedTheme);
    }
  }, []);

  useEffect(() => {
    autoResizeTextarea(composerRef.current);
  }, [messageDraft, mode, isComposingNewThread]);

  const homeQuery = useThreadHome(configPath, bridgeAvailable);
  const activeManagerSessionId = isComposingNewThread ? "" : managerSessionId;
  const managerQuery = useManagerThread(configPath, activeManagerSessionId, bridgeAvailable);
  const linkedFlowId = String(managerQuery.data?.linked_flow_id || managerQuery.data?.thread.flow_id || "").trim();
  const queriedFlowId = detailState.kind === "agent" ? detailState.flowId : linkedFlowId;
  const supervisorQuery = useSupervisorThread(configPath, queriedFlowId, bridgeAvailable && Boolean(queriedFlowId));
  const agentQuery = useAgentFocus(
    configPath,
    detailState.kind === "agent" ? detailState.flowId : "",
    detailState.kind === "agent" ? detailState.roleId : "",
    bridgeAvailable && detailState.kind === "agent"
  );
  const templateQuery = useTemplateTeam(configPath, templateAssetId, bridgeAvailable && mode === "studio" && Boolean(templateAssetId));

  useEffect(() => {
    if (isComposingNewThread || managerSessionId) {
      return;
    }
    const defaultManagerSessionId = String(homeQuery.data?.manager_entry.default_manager_session_id || "").trim();
    if (defaultManagerSessionId) {
      setManagerSessionId(defaultManagerSessionId);
    }
  }, [homeQuery.data, isComposingNewThread, managerSessionId]);

  useEffect(() => {
    if (templateAssetId) {
      return;
    }
    const firstTemplate = homeQuery.data?.templates?.[0];
    const firstTemplateId = String(firstTemplate?.thread_id || "").replace(/^template:/, "");
    if (firstTemplateId) {
      setTemplateAssetId(firstTemplateId);
    }
  }, [homeQuery.data, templateAssetId]);

  async function invalidateDesktopQueries(): Promise<void> {
    await queryClient.invalidateQueries({ queryKey: ["desktop"] });
  }

  async function applyConfigAttachment(nextConfigPath: string, notice: string): Promise<void> {
    window.localStorage.setItem(CONFIG_STORAGE_KEY, nextConfigPath);
    startTransition(() => {
      setConfigPath(nextConfigPath);
      setManualConfigPath(nextConfigPath);
      setManagerSessionId("");
      setIsComposingNewThread(false);
      setMode("mission");
      setTemplateAssetId("");
      setDetailState({ kind: "none" });
      setMessageDraft("");
      setExpandedBlocks({});
    });
    setStatusMessage(notice);
    await invalidateDesktopQueries();
  }

  function currentBlockExpanded(blockId: string, expandedByDefault: boolean): boolean {
    if (blockId in expandedBlocks) {
      return Boolean(expandedBlocks[blockId]);
    }
    return expandedByDefault;
  }

  function toggleBlock(blockId: string): void {
    setExpandedBlocks((current) => ({
      ...current,
      [blockId]: !(blockId in current ? current[blockId] : true)
    }));
  }

  async function chooseConfig(): Promise<void> {
    if (!bridgeAvailable) {
      setStatusMessage("Desktop bridge unavailable. Launch this shell from Electron.");
      return;
    }
    try {
      const result = await electronApi.chooseConfigPath();
      if (result.canceled || !result.configPath) {
        setStatusMessage("Native config picker canceled or unavailable.");
        return;
      }
      const nextConfigPath = normalizeConfigPath(result.configPath);
      await applyConfigAttachment(nextConfigPath, `Config attached: ${nextConfigPath}`);
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
    try {
      await applyConfigAttachment(nextConfigPath, `Config attached: ${nextConfigPath}`);
    } catch (error) {
      setStatusMessage(`Attach path failed: ${String((error as Error)?.message || error)}`);
    }
  }

  function onManualConfigKeyDown(event: KeyboardEvent<HTMLInputElement>): void {
    if (event.key !== "Enter") {
      return;
    }
    event.preventDefault();
    void attachConfigPath(manualConfigPath);
  }

  async function refreshAll(): Promise<void> {
    if (!bridgeAvailable) {
      setStatusMessage("Desktop bridge unavailable. Refresh is disabled in browser-only mode.");
      return;
    }
    try {
      await invalidateDesktopQueries();
      setStatusMessage("Mission shell refreshed.");
    } catch (error) {
      setStatusMessage(`Refresh failed: ${String((error as Error)?.message || error)}`);
    }
  }

  async function performFlowAction(type: string): Promise<void> {
    if (!bridgeAvailable) {
      setStatusMessage("Desktop bridge unavailable. Runtime actions require Electron.");
      return;
    }
    if (!linkedFlowId) {
      return;
    }
    try {
      const payload = await electronApi.performAction({
        configPath,
        flowId: linkedFlowId,
        type
      });
      await invalidateDesktopQueries();
      setStatusMessage(`Action applied: ${String(payload.action_type || type)}`);
    } catch (error) {
      setStatusMessage(`Runtime action failed: ${String((error as Error)?.message || error)}`);
    }
  }

  async function openArtifact(target: string): Promise<void> {
    if (!bridgeAvailable) {
      setStatusMessage("Desktop bridge unavailable. Artifact open requires Electron.");
      return;
    }
    try {
      const result = await electronApi.openArtifact({ target });
      if (!result.opened) {
        setStatusMessage(`Artifact open failed: ${result.reason || "unknown"}`);
      }
    } catch (error) {
      setStatusMessage(`Artifact open failed: ${String((error as Error)?.message || error)}`);
    }
  }

  function openThread(nextManagerThread: { manager_session_id: string }): void {
    const targetManagerSessionId = String(nextManagerThread.manager_session_id || "").trim();
    if (!targetManagerSessionId) {
      return;
    }
    startTransition(() => {
      setIsComposingNewThread(false);
      setManagerSessionId(targetManagerSessionId);
      setMode("mission");
      setDetailState({ kind: "none" });
      setMessageDraft("");
      setExpandedBlocks({});
    });
    setStatusMessage("");
  }

  function openNewThread(): void {
    startTransition(() => {
      setIsComposingNewThread(true);
      setManagerSessionId("");
      setMode("mission");
      setDetailState({ kind: "none" });
      setMessageDraft("");
      setExpandedBlocks({});
    });
    setStatusMessage("");
  }

  function handleActionTarget(target: string): void {
    const token = String(target || "").trim();
    if (!token) {
      return;
    }
    if (token.startsWith("flow:")) {
      startTransition(() => {
        setMode("runtime");
      });
      return;
    }
    if (token.startsWith("role:") && linkedFlowId) {
      const roleId = token.slice("role:".length);
      startTransition(() => {
        setMode("runtime");
        setDetailState({ kind: "agent", flowId: linkedFlowId, roleId });
      });
      return;
    }
    if (token.startsWith("artifact:")) {
      void openArtifact(token.slice("artifact:".length));
      return;
    }
    if (token.startsWith("template:")) {
      startTransition(() => {
        setTemplateAssetId(token.slice("template:".length));
        setMode("studio");
      });
    }
  }

  async function sendManagerMessage(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    const instruction = messageDraft.trim();
    if (!bridgeAvailable) {
      setStatusMessage("Desktop bridge unavailable. Manager message can only be sent from Electron.");
      return;
    }
    if (!instruction || !configPath) {
      return;
    }
    setSendingManagerMessage(true);
    try {
      const result = await electronApi.sendManagerMessage({
        configPath,
        instruction,
        managerSessionId: isComposingNewThread ? "" : managerSessionId,
        manageTarget: isComposingNewThread ? "new" : undefined
      });
      const nextManagerSessionId = String(result.manager_session_id || "").trim();
      await invalidateDesktopQueries();
      startTransition(() => {
        if (nextManagerSessionId) {
          setManagerSessionId(nextManagerSessionId);
          setIsComposingNewThread(false);
        }
        setMessageDraft("");
      });
      const launchedFlowId = String(result.launched_flow?.flow_id || "").trim();
      if (launchedFlowId) {
        startTransition(() => {
          setMode("runtime");
        });
        setStatusMessage(`Mission started: ${launchedFlowId}`);
      } else {
        setStatusMessage(formatValue(result.message?.response || "Manager updated."));
      }
    } catch (error) {
      setStatusMessage(`Manager message failed: ${String((error as Error)?.message || error)}`);
    } finally {
      setSendingManagerMessage(false);
    }
  }

  function switchTheme(): void {
    const nextTheme = theme === "day" ? "night" : "day";
    setTheme(nextTheme);
    window.localStorage.setItem(THEME_STORAGE_KEY, nextTheme);
  }

  const threadRows = buildManagerThreads(homeQuery.data);
  const activeThreads = threadRows.filter((summary) => !isHistoricalStatus(summary.status));
  const historyThreads = threadRows.filter((summary) => isHistoricalStatus(summary.status));
  const currentThread = managerQuery.data?.thread;
  const currentTitle = isComposingNewThread
    ? "New mission"
    : currentThread?.title || threadRows.find((summary) => summary.manager_session_id === managerSessionId)?.title || "Manager";
  const currentSubtitle = isComposingNewThread
    ? "Start with Manager, then let the runtime take over when you are ready."
    : mode === "runtime"
      ? supervisorQuery.data?.thread.subtitle || currentThread?.subtitle || "Runtime updates stay inside the same conversation."
      : mode === "studio"
        ? templateQuery.data?.thread.subtitle || "Edit contract and policy without leaving the mission thread."
        : currentThread?.subtitle || "The mission stays continuous through one Manager thread.";
  const runtimeAvailable = Boolean(linkedFlowId);
  const studioAvailable = Boolean(templateAssetId || homeQuery.data?.templates?.length);
  const currentThreadStatus = currentThread?.status || (isComposingNewThread ? "draft" : "active");
  const managerBlocks = managerQuery.data?.blocks || [];
  const runtimeBlocks = supervisorQuery.data?.blocks || [];
  const studioBlocks = templateQuery.data?.blocks || [];
  const runtimeStatus = String(supervisorQuery.data?.summary.effective_status || "").trim();
  const runtimePhase = String(supervisorQuery.data?.summary.effective_phase || "").trim();
  const activeRole = String(supervisorQuery.data?.summary.active_role_id || "").trim();
  const canPause = runtimeAvailable && runtimeStatus === "running";
  const canResume = runtimeAvailable && runtimeStatus === "paused";
  const managerLabel = composerLabel(mode, isComposingNewThread);
  const managerPlaceholder = composerPlaceholder(mode, isComposingNewThread);
  const workspaceRoot = String(homeQuery.data?.preflight.workspace_root || "").trim();
  const templateCount = homeQuery.data?.templates?.length || 0;
  const surfaceBusy =
    homeQuery.isFetching ||
    managerQuery.isFetching ||
    (mode === "runtime" && supervisorQuery.isFetching) ||
    (mode === "studio" && templateQuery.isFetching) ||
    (detailState.kind === "agent" && agentQuery.isFetching);

  const surfaceErrorMessage =
    [
      homeQuery.error ? queryErrorText("Thread home", homeQuery.error) : "",
      managerQuery.error ? queryErrorText("Manager thread", managerQuery.error) : "",
      mode === "runtime" && supervisorQuery.error ? queryErrorText("Runtime surface", supervisorQuery.error) : "",
      mode === "studio" && templateQuery.error ? queryErrorText("Studio surface", templateQuery.error) : "",
      detailState.kind === "agent" && agentQuery.error ? queryErrorText("Agent detail", agentQuery.error) : ""
    ].find(Boolean) || "";

  const shellStatusMessage = surfaceErrorMessage || statusMessage;
  const shellStatusTone: MissionStatusTone = surfaceErrorMessage ? "danger" : "info";

  function renderMainContent() {
    if (!bridgeAvailable) {
      return <BridgeMissingState />;
    }
    if (!configPath) {
      return (
        <EmptyAttachState
          manualConfigPath={manualConfigPath}
          onAttachPath={() => void attachConfigPath(manualConfigPath)}
          onChooseConfig={() => void chooseConfig()}
          onManualConfigChange={setManualConfigPath}
          onManualConfigKeyDown={onManualConfigKeyDown}
        />
      );
    }
    return (
      <MissionShell
        activeRole={activeRole}
        canPause={canPause}
        canResume={canResume}
        composerLabel={managerLabel}
        composerPlaceholder={managerPlaceholder}
        composerRef={composerRef}
        currentBlockExpanded={(block) => currentBlockExpanded(block.block_id, Boolean(block.expanded_by_default))}
        currentSubtitle={currentSubtitle}
        currentThreadStatus={currentThreadStatus}
        currentTitle={currentTitle}
        isComposingNewThread={isComposingNewThread}
        linkedFlowId={linkedFlowId}
        managerBlocks={managerBlocks}
        managerStage={String(managerQuery.data?.manager_stage || "").trim()}
        messageDraft={messageDraft}
        mode={mode}
        onActionTarget={handleActionTarget}
        onChooseConfig={() => void chooseConfig()}
        onMessageDraftChange={setMessageDraft}
        onModeChange={(nextMode) => startTransition(() => setMode(nextMode))}
        onPause={() => void performFlowAction("pause")}
        onRefresh={() => void refreshAll()}
        onResume={() => void performFlowAction("resume")}
        onRoleSelect={(roleId) => {
          if (!linkedFlowId) {
            return;
          }
          startTransition(() => {
            setDetailState({ kind: "agent", flowId: linkedFlowId, roleId });
            setMode("runtime");
          });
        }}
        onSelectAsset={(assetId) => startTransition(() => setTemplateAssetId(assetId))}
        onSendMessage={(event) => void sendManagerMessage(event)}
        onSwitchTheme={switchTheme}
        onToggleBlock={toggleBlock}
        runtimeAvailable={runtimeAvailable}
        runtimeBlocks={runtimeBlocks}
        runtimePhase={runtimePhase}
        sendingManagerMessage={sendingManagerMessage}
        statusMessage={shellStatusMessage}
        statusTone={shellStatusTone}
        studioAvailable={studioAvailable}
        studioBlocks={studioBlocks}
        supervisorPayload={supervisorQuery.data}
        surfaceBusy={surfaceBusy}
        templateCount={templateCount}
        templatePayload={templateQuery.data}
        theme={theme}
      />
    );
  }

  return (
    <div className="desktop-root" data-theme={theme}>
      <DesktopRail
        activeThreads={activeThreads}
        bridgeAvailable={bridgeAvailable}
        configPath={configPath}
        currentFlowId={linkedFlowId}
        historyThreads={historyThreads}
        home={homeQuery.data}
        homeLoading={homeQuery.isFetching}
        isComposingNewThread={isComposingNewThread}
        managerSessionId={managerSessionId}
        mode={mode}
        onOpenNewThread={openNewThread}
        onOpenThread={openThread}
        templateCount={templateCount}
        theme={theme}
        workspaceRoot={workspaceRoot}
      />

      <main className="desktop-main">{renderMainContent()}</main>

      <AgentDetailSheet
        expandedBlocks={expandedBlocks}
        onActionTarget={handleActionTarget}
        onClose={() => setDetailState({ kind: "none" })}
        onToggle={toggleBlock}
        open={detailState.kind === "agent"}
        payload={agentQuery.data}
      />
    </div>
  );
}
