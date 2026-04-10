import { FormEvent, KeyboardEvent, startTransition, useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import type { ManagerMessageStreamEvent } from "../shared/ipc";
import { electronApi, isDesktopBridgeAvailable } from "./lib/electron-api";
import { BridgeMissingState, DesktopRail, EmptyAttachState, MissionShell, type MissionStatusTone } from "./components/mission-shell/MissionShell";
import {
  autoResizeTextarea,
  buildConversationMessages,
  buildManagerThreads,
  composerLabel,
  composerPlaceholder,
  formatValue,
  normalizeConfigPath,
  type ShellMessage
} from "./lib/mission-shell";
import { useManagerThread, useThreadHome } from "./state/queries/use-thread-workbench";

const CONFIG_STORAGE_KEY = "butler.desktop.configPath";
const THEME_STORAGE_KEY = "butler.desktop.theme";

function queryErrorText(scope: string, error: unknown): string {
  const token = String((error as Error)?.message || error || "").trim();
  return token ? `${scope} failed: ${token}` : `${scope} failed.`;
}

export default function App() {
  const queryClient = useQueryClient();
  const composerRef = useRef<HTMLTextAreaElement>(null);
  const streamRequestIdRef = useRef("");
  const transientManagerMessageIdRef = useRef("");
  const [manualConfigPath, setManualConfigPath] = useState("");
  const [configPath, setConfigPath] = useState("");
  const [startupConfigResolved, setStartupConfigResolved] = useState(false);
  const [theme, setTheme] = useState<"day" | "night">("night");
  const [managerSessionId, setManagerSessionId] = useState("");
  const [isComposingNewThread, setIsComposingNewThread] = useState(false);
  const [messageDraft, setMessageDraft] = useState("");
  const [statusMessage, setStatusMessage] = useState("");
  const [sendingManagerMessage, setSendingManagerMessage] = useState(false);
  const [transientMessages, setTransientMessages] = useState<ShellMessage[]>([]);
  const bridgeAvailable = isDesktopBridgeAvailable();

  useEffect(() => {
    const savedTheme = window.localStorage.getItem(THEME_STORAGE_KEY);
    if (savedTheme === "day" || savedTheme === "night") {
      setTheme(savedTheme);
    }
    if (!bridgeAvailable) {
      setStartupConfigResolved(true);
      return;
    }

    let cancelled = false;

    async function bootstrapConfig(): Promise<void> {
      try {
        const result = await electronApi.getDefaultConfigPath();
        const defaultConfigPath = normalizeConfigPath(result.configPath || "");
        if (cancelled) {
          return;
        }
        if (defaultConfigPath) {
          window.localStorage.setItem(CONFIG_STORAGE_KEY, defaultConfigPath);
          setConfigPath(defaultConfigPath);
          setManualConfigPath(defaultConfigPath);
          return;
        }

        const savedConfig = normalizeConfigPath(window.localStorage.getItem(CONFIG_STORAGE_KEY) || "");
        if (savedConfig) {
          setConfigPath(savedConfig);
          setManualConfigPath(savedConfig);
        }
      } catch (error) {
        if (cancelled) {
          return;
        }
        const savedConfig = normalizeConfigPath(window.localStorage.getItem(CONFIG_STORAGE_KEY) || "");
        if (savedConfig) {
          setConfigPath(savedConfig);
          setManualConfigPath(savedConfig);
        }
        setStatusMessage(`Default config attach failed: ${String((error as Error)?.message || error)}`);
      } finally {
        if (!cancelled) {
          setStartupConfigResolved(true);
        }
      }
    }

    void bootstrapConfig();

    return () => {
      cancelled = true;
    };
  }, [bridgeAvailable]);

  useEffect(() => {
    autoResizeTextarea(composerRef.current);
  }, [messageDraft, isComposingNewThread]);

  const homeQuery = useThreadHome(configPath, bridgeAvailable);
  const activeManagerSessionId = isComposingNewThread ? "" : managerSessionId;
  const managerQuery = useManagerThread(configPath, activeManagerSessionId, bridgeAvailable);

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
    if (!bridgeAvailable) {
      return;
    }
    return electronApi.onManagerMessageEvent((event) => {
      if (!streamRequestIdRef.current || event.requestId !== streamRequestIdRef.current) {
        return;
      }
      if (event.type === "chunk") {
        setTransientMessages((current) =>
          current.map((message) =>
            message.id === transientManagerMessageIdRef.current
              ? {
                  ...message,
                  body: `${message.body}${event.chunkText || ""}`,
                  status: "streaming"
                }
              : message
          )
        );
        return;
      }
      if (event.type === "failed") {
        streamRequestIdRef.current = "";
        setSendingManagerMessage(false);
        setStatusMessage(event.error || "Manager stream failed.");
        setTransientMessages((current) =>
          current.map((message) =>
            message.id === transientManagerMessageIdRef.current
              ? {
                  ...message,
                  body: event.error || message.body || "Manager stream failed.",
                  status: "error"
                }
              : message
          )
        );
        return;
      }
      if (event.type === "completed") {
        void finalizeStream(event);
      }
    });
  }, [bridgeAvailable, queryClient]);

  async function invalidateDesktopQueries(): Promise<void> {
    await queryClient.invalidateQueries({ queryKey: ["desktop"] });
  }

  async function finalizeStream(event: ManagerMessageStreamEvent): Promise<void> {
    const finalResult = event.finalResult;
    const finalText = formatValue(finalResult?.message?.response || finalResult?.thread?.latest_response || "Manager updated.");

    setTransientMessages((current) =>
      current.map((message) =>
        message.id === transientManagerMessageIdRef.current
          ? {
              ...message,
              body: message.body || finalText,
              status: "ready"
            }
          : message
      )
    );

    const nextManagerSessionId = String(finalResult?.manager_session_id || "").trim();
    await invalidateDesktopQueries();

    startTransition(() => {
      if (nextManagerSessionId) {
        setManagerSessionId(nextManagerSessionId);
      }
      setIsComposingNewThread(false);
      setMessageDraft("");
      setTransientMessages([]);
    });

    streamRequestIdRef.current = "";
    transientManagerMessageIdRef.current = "";
    setSendingManagerMessage(false);

    const launchedFlowId = String(finalResult?.launched_flow?.flow_id || "").trim();
    setStatusMessage(launchedFlowId ? `Manager launched ${launchedFlowId}` : "");
  }

  async function applyConfigAttachment(nextConfigPath: string, notice: string): Promise<void> {
    window.localStorage.setItem(CONFIG_STORAGE_KEY, nextConfigPath);
    startTransition(() => {
      setConfigPath(nextConfigPath);
      setManualConfigPath(nextConfigPath);
      setManagerSessionId("");
      setIsComposingNewThread(false);
      setMessageDraft("");
      setTransientMessages([]);
    });
    setStatusMessage(notice);
    streamRequestIdRef.current = "";
    transientManagerMessageIdRef.current = "";
    await invalidateDesktopQueries();
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

  function openThread(nextManagerThread: { manager_session_id: string }): void {
    const targetManagerSessionId = String(nextManagerThread.manager_session_id || "").trim();
    if (!targetManagerSessionId) {
      return;
    }
    streamRequestIdRef.current = "";
    transientManagerMessageIdRef.current = "";
    startTransition(() => {
      setIsComposingNewThread(false);
      setManagerSessionId(targetManagerSessionId);
      setMessageDraft("");
      setTransientMessages([]);
    });
    setStatusMessage("");
  }

  function openNewThread(): void {
    streamRequestIdRef.current = "";
    transientManagerMessageIdRef.current = "";
    startTransition(() => {
      setIsComposingNewThread(true);
      setManagerSessionId("");
      setMessageDraft("");
      setTransientMessages([]);
    });
    setStatusMessage("");
  }

  async function sendManagerMessage(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    const instruction = messageDraft.trim();
    if (!bridgeAvailable) {
      setStatusMessage("Desktop bridge unavailable. Manager message can only be sent from Electron.");
      return;
    }
    if (!instruction || !configPath || sendingManagerMessage) {
      return;
    }

    const stamp = `${Date.now()}`;
    const userMessageId = `stream:${stamp}:user`;
    const managerMessageId = `stream:${stamp}:manager`;
    transientManagerMessageIdRef.current = managerMessageId;
    setTransientMessages([
      {
        id: userMessageId,
        role: "user",
        body: instruction,
        createdAt: "",
        meta: "request",
        status: "ready"
      },
      {
        id: managerMessageId,
        role: "manager",
        body: "",
        createdAt: "",
        meta: "streaming",
        title: "Manager",
        status: "streaming"
      }
    ]);
    setSendingManagerMessage(true);
    setStatusMessage("");

    try {
      const result = await electronApi.sendManagerMessageStream({
        configPath,
        instruction,
        managerSessionId: isComposingNewThread ? "" : managerSessionId,
        manageTarget: isComposingNewThread ? "new" : undefined
      });
      streamRequestIdRef.current = result.requestId;
    } catch (error) {
      streamRequestIdRef.current = "";
      setSendingManagerMessage(false);
      setStatusMessage(`Manager stream failed: ${String((error as Error)?.message || error)}`);
      setTransientMessages((current) =>
        current.map((message) =>
          message.id === managerMessageId
            ? {
                ...message,
                body: String((error as Error)?.message || error || "Manager stream failed."),
                status: "error"
              }
            : message
        )
      );
    }
  }

  function switchTheme(): void {
    const nextTheme = theme === "day" ? "night" : "day";
    setTheme(nextTheme);
    window.localStorage.setItem(THEME_STORAGE_KEY, nextTheme);
  }

  const threadRows = buildManagerThreads(homeQuery.data);
  const currentThread = managerQuery.data?.thread;
  const currentTitle = isComposingNewThread
    ? "New thread"
    : currentThread?.title || threadRows.find((summary) => summary.manager_session_id === managerSessionId)?.title || "Manager";
  const currentThreadStatus = isComposingNewThread ? "draft" : currentThread?.status || "active";
  const managerBlocks = managerQuery.data?.blocks || [];
  const conversationMessages = [...buildConversationMessages(managerBlocks), ...transientMessages];
  const managerLabel = composerLabel(isComposingNewThread);
  const managerPlaceholder = composerPlaceholder(isComposingNewThread);
  const workspaceRoot = String(homeQuery.data?.preflight.workspace_root || "").trim();
  const currentWorkspacePath = workspaceRoot || configPath;
  const surfaceBusy = homeQuery.isFetching || (!isComposingNewThread && managerQuery.isFetching);

  const surfaceErrorMessage =
    [
      homeQuery.error ? queryErrorText("Thread home", homeQuery.error) : "",
      managerQuery.error ? queryErrorText("Manager thread", managerQuery.error) : ""
    ].find(Boolean) || "";

  const shellStatusMessage = surfaceErrorMessage || statusMessage;
  const shellStatusTone: MissionStatusTone = surfaceErrorMessage ? "danger" : "info";

  function renderMainContent() {
    if (!bridgeAvailable) {
      return <BridgeMissingState />;
    }
    if (!startupConfigResolved) {
      return (
        <section className="empty-state-shell">
          <div className="empty-state-card">
            <div className="empty-state-badge">
              <SparkleStub />
              <span>Butler Desktop</span>
            </div>
            <h2>正在连接默认 Config</h2>
            <p>启动时会自动挂载仓库里的默认 Butler config，然后直接进入最小 Manager shell。</p>
          </div>
        </section>
      );
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
        composerLabel={managerLabel}
        composerPlaceholder={managerPlaceholder}
        composerRef={composerRef}
        conversationMessages={conversationMessages}
        currentThreadStatus={currentThreadStatus}
        currentTitle={currentTitle}
        currentWorkspacePath={currentWorkspacePath}
        messageDraft={messageDraft}
        onMessageDraftChange={setMessageDraft}
        onSendMessage={(submitEvent) => void sendManagerMessage(submitEvent)}
        sendingManagerMessage={sendingManagerMessage}
        statusMessage={shellStatusMessage}
        statusTone={shellStatusTone}
        surfaceBusy={surfaceBusy}
      />
    );
  }

  return (
    <div className="desktop-root" data-theme={theme}>
      <DesktopRail
        activeManagerSessionId={managerSessionId}
        home={homeQuery.data}
        homeLoading={homeQuery.isLoading}
        isComposingNewThread={isComposingNewThread}
        onOpenNewThread={openNewThread}
        onOpenThread={openThread}
        onSwitchTheme={switchTheme}
        theme={theme}
        threadRows={threadRows}
      />
      <main className="desktop-main">{renderMainContent()}</main>
    </div>
  );
}

function SparkleStub() {
  return <span aria-hidden>*</span>;
}
