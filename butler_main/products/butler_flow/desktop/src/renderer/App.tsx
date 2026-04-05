import { FormEvent, KeyboardEvent, ReactNode, useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  AlertCircle,
  ArrowLeft,
  Bot,
  FolderSearch,
  History,
  LayoutTemplate,
  Moon,
  PauseCircle,
  PlayCircle,
  PlusSquare,
  RefreshCcw,
  Send,
  Sparkles,
  SunMedium
} from "lucide-react";
import type { ThreadBlockDTO, ThreadSummaryDTO } from "../shared/dto";
import { electronApi, isDesktopBridgeAvailable } from "./lib/electron-api";
import {
  useAgentFocus,
  useManagerThread,
  useSupervisorThread,
  useTemplateTeam,
  useThreadHome
} from "./state/queries/use-thread-workbench";

const CONFIG_STORAGE_KEY = "butler.desktop.configPath";
const THEME_STORAGE_KEY = "butler.desktop.theme";

type RailSection = "manager" | "history" | "new-flow" | "templates";

type ViewState =
  | { kind: "manager" }
  | { kind: "history" }
  | { kind: "new-flow" }
  | { kind: "templates" }
  | { kind: "supervisor"; flowId: string }
  | { kind: "agent"; flowId: string; roleId: string };

function normalizeConfigPath(value: string): string {
  return String(value || "").trim();
}

function formatValue(value: unknown): string {
  if (Array.isArray(value)) {
    return value.map((item) => formatValue(item)).filter(Boolean).join(" / ");
  }
  if (value && typeof value === "object") {
    const record = value as Record<string, unknown>;
    for (const key of ["summary", "label", "title", "goal", "reason", "message", "decision"]) {
      const token = String(record[key] || "").trim();
      if (token) {
        return token;
      }
    }
    return JSON.stringify(value, null, 2);
  }
  return String(value || "").trim();
}

function blockMeta(block: ThreadBlockDTO): string[] {
  return [block.kind, block.phase || "", ...(block.tags || [])].filter(Boolean);
}

function shortTime(value: string): string {
  const token = String(value || "").trim();
  if (!token) {
    return "刚刚";
  }
  return token.slice(5, 16).replace(" ", " · ");
}

function isManagerSummary(summary: ThreadSummaryDTO): boolean {
  return String(summary.thread_kind || "").trim() === "manager";
}

function isSupervisorSummary(summary: ThreadSummaryDTO): boolean {
  return String(summary.thread_kind || "").trim() === "supervisor" && Boolean(summary.flow_id);
}

function autoResizeTextarea(node: HTMLTextAreaElement | null): void {
  if (!node || typeof window === "undefined") {
    return;
  }
  const maxHeight = Math.floor(window.innerHeight / 3);
  node.style.height = "0px";
  const nextHeight = Math.max(76, Math.min(node.scrollHeight, maxHeight));
  node.style.height = `${nextHeight}px`;
  node.style.overflowY = node.scrollHeight > maxHeight ? "auto" : "hidden";
}

function RailButton({
  active,
  icon,
  label,
  detail,
  onClick
}: {
  active: boolean;
  icon: ReactNode;
  label: string;
  detail: string;
  onClick: () => void;
}) {
  return (
    <button className={`rail-nav-button ${active ? "is-active" : ""}`} onClick={onClick} type="button">
      <span className="rail-nav-icon">{icon}</span>
      <span className="rail-nav-copy">
        <strong>{label}</strong>
        <span>{detail}</span>
      </span>
    </button>
  );
}

function ThreadShortcut({
  summary,
  active,
  onClick
}: {
  summary: ThreadSummaryDTO;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button className={`thread-shortcut ${active ? "is-active" : ""}`} onClick={onClick} type="button">
      <div className="thread-shortcut-topline">
        <span className="thread-shortcut-kicker">{summary.thread_kind}</span>
        <span className="thread-shortcut-time">{shortTime(summary.updated_at || summary.created_at)}</span>
      </div>
      <span className="thread-shortcut-title">{summary.title}</span>
      <span className="thread-shortcut-subtitle">{summary.subtitle || summary.status}</span>
      <span className="thread-shortcut-meta">
        {[summary.current_phase, summary.active_role_id, summary.badge].filter(Boolean).join(" · ") || summary.status}
      </span>
    </button>
  );
}

function StreamBlock({
  block,
  expanded,
  onToggle,
  onActionTarget
}: {
  block: ThreadBlockDTO;
  expanded: boolean;
  onToggle: () => void;
  onActionTarget: (target: string) => void;
}) {
  const detailPayload = block.payload || {};
  const hasDetail = Object.keys(detailPayload).length > 0;

  return (
    <article className={`stream-card stream-card-${block.kind}`}>
      <div className="stream-card-topline">
        <div className="stream-card-meta">
          {blockMeta(block).map((item) => (
            <span className="meta-pill" key={`${block.block_id}:${item}`}>
              {item}
            </span>
          ))}
        </div>
        <span className="stream-card-status">{block.status || "active"}</span>
      </div>

      <div className="stream-card-header">
        <div className="stream-card-copy">
          <h3>{block.title}</h3>
          <p>{block.summary}</p>
        </div>
        <div className="stream-card-actions">
          {block.action_target ? (
            <button className="ui-button ui-button-secondary" onClick={() => onActionTarget(block.action_target || "")} type="button">
              {block.action_label || "Open"}
            </button>
          ) : null}
          {hasDetail ? (
            <button className="ui-button ui-button-tertiary" onClick={onToggle} type="button">
              {expanded ? "收起" : "展开"}
            </button>
          ) : null}
        </div>
      </div>

      <div className="stream-card-footer">
        <span>{shortTime(block.created_at)}</span>
        {block.role_id ? <span>{`Agent ${block.role_id}`}</span> : null}
      </div>

      {expanded && hasDetail ? (
        <div className="stream-card-detail">
          <pre>{JSON.stringify(detailPayload, null, 2)}</pre>
        </div>
      ) : null}
    </article>
  );
}

function ComposerPill({ label, value }: { label: string; value: string }) {
  return (
    <span className="composer-pill">
      <strong>{label}</strong>
      <span>{value}</span>
    </span>
  );
}

function EmptyAttachState({
  manualConfigPath,
  onManualConfigChange,
  onManualConfigKeyDown,
  onChooseConfig,
  onAttachPath
}: {
  manualConfigPath: string;
  onManualConfigChange: (value: string) => void;
  onManualConfigKeyDown: (event: KeyboardEvent<HTMLInputElement>) => void;
  onChooseConfig: () => void;
  onAttachPath: () => void;
}) {
  return (
    <section className="empty-state-shell">
      <div className="empty-state-card">
        <div className="empty-state-badge">
          <Sparkles size={16} />
          <span>Butler Flow Desktop</span>
        </div>
        <h2>先连接 Butler config</h2>
        <p>连接 config 后，Desktop 会读取 live threads、manager session、supervisor stream 和 template team。</p>
        <div className="empty-state-actions">
          <button className="ui-button ui-button-primary" onClick={onChooseConfig} type="button">
            <FolderSearch size={16} />
            选择 Config
          </button>
        </div>

        <div className="composer-shell compact">
          <label htmlFor="manual-config-path">Config Path Fallback</label>
          <div className="composer-row compact">
            <input
              id="manual-config-path"
              className="composer-input"
              placeholder="/abs/path/to/butler_bot.json"
              value={manualConfigPath}
              onChange={(event) => onManualConfigChange(event.target.value)}
              onKeyDown={onManualConfigKeyDown}
            />
            <button className="ui-button ui-button-secondary" disabled={!manualConfigPath.trim()} onClick={onAttachPath} type="button">
              Attach Path
            </button>
          </div>
        </div>
      </div>
    </section>
  );
}

function BridgeMissingState() {
  return (
    <section className="empty-state-shell">
      <div className="empty-state-card">
        <div className="empty-state-badge">
          <AlertCircle size={16} />
          <span>Bridge Required</span>
        </div>
        <h2>Desktop bridge 未连接</h2>
        <p>当前页面没有注入 `window.butlerDesktop`，所以无法读取 Manager thread、Supervisor stream 或发送 manager message。</p>
        <p>请从 Electron Butler Desktop 窗口打开；如果你现在看到的是纯浏览器 / Vite 页面，这属于预期。</p>
      </div>
    </section>
  );
}

export default function App() {
  const queryClient = useQueryClient();
  const composerRef = useRef<HTMLTextAreaElement | null>(null);
  const [manualConfigPath, setManualConfigPath] = useState("");
  const [configPath, setConfigPath] = useState("");
  const [theme, setTheme] = useState<"day" | "night">("night");
  const [railSection, setRailSection] = useState<RailSection>("manager");
  const [view, setView] = useState<ViewState>({ kind: "manager" });
  const [managerSessionId, setManagerSessionId] = useState("");
  const [templateAssetId, setTemplateAssetId] = useState("");
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
  }, [messageDraft, view.kind]);

  const homeQuery = useThreadHome(configPath, bridgeAvailable);
  const activeManagerSessionId = view.kind === "new-flow" ? "" : managerSessionId;
  const managerQuery = useManagerThread(
    configPath,
    activeManagerSessionId,
    bridgeAvailable && (view.kind === "manager" || view.kind === "new-flow")
  );
  const activeFlowId = view.kind === "supervisor" || view.kind === "agent" ? view.flowId : "";
  const supervisorQuery = useSupervisorThread(
    configPath,
    activeFlowId,
    bridgeAvailable && (view.kind === "supervisor" || view.kind === "agent")
  );
  const agentQuery = useAgentFocus(
    configPath,
    view.kind === "agent" ? view.flowId : "",
    view.kind === "agent" ? view.roleId : "",
    bridgeAvailable && view.kind === "agent"
  );
  const templateQuery = useTemplateTeam(configPath, templateAssetId, bridgeAvailable && view.kind === "templates");

  useEffect(() => {
    if (!managerSessionId) {
      const defaultManagerSessionId = String(homeQuery.data?.manager_entry.default_manager_session_id || "").trim();
      if (defaultManagerSessionId) {
        setManagerSessionId(defaultManagerSessionId);
      }
    }
  }, [homeQuery.data, managerSessionId]);

  useEffect(() => {
    const selectedAssetId = String(templateQuery.data?.asset_id || "").trim();
    if (!templateAssetId && selectedAssetId) {
      setTemplateAssetId(selectedAssetId);
    }
  }, [templateAssetId, templateQuery.data]);

  function currentBlockExpanded(block: ThreadBlockDTO): boolean {
    if (block.block_id in expandedBlocks) {
      return Boolean(expandedBlocks[block.block_id]);
    }
    return Boolean(block.expanded_by_default);
  }

  function toggleBlock(blockId: string): void {
    setExpandedBlocks((current) => ({
      ...current,
      [blockId]: !(blockId in current ? current[blockId] : true)
    }));
  }

  async function chooseConfig(): Promise<void> {
    if (!bridgeAvailable) {
      setStatusMessage("Desktop bridge unavailable. Launch this workbench from Electron.");
      return;
    }
    try {
      const result = await electronApi.chooseConfigPath();
      if (result.canceled || !result.configPath) {
        setStatusMessage("Native config picker canceled or unavailable.");
        return;
      }
      const nextConfigPath = normalizeConfigPath(result.configPath);
      window.localStorage.setItem(CONFIG_STORAGE_KEY, nextConfigPath);
      setConfigPath(nextConfigPath);
      setManualConfigPath(nextConfigPath);
      setStatusMessage(`Config attached: ${nextConfigPath}`);
      await queryClient.invalidateQueries({ queryKey: ["desktop"] });
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
    window.localStorage.setItem(CONFIG_STORAGE_KEY, nextConfigPath);
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
    if (!bridgeAvailable) {
      setStatusMessage("Desktop bridge unavailable. Refresh is disabled in browser-only mode.");
      return;
    }
    await queryClient.invalidateQueries({ queryKey: ["desktop"] });
  }

  async function performFlowAction(type: string): Promise<void> {
    if (!bridgeAvailable) {
      setStatusMessage("Desktop bridge unavailable. Flow actions require Electron.");
      return;
    }
    if (!activeFlowId) {
      return;
    }
    const payload = await electronApi.performAction({
      configPath,
      flowId: activeFlowId,
      type
    });
    setStatusMessage(`Action applied: ${String(payload.action_type || type)}`);
    await refreshAll();
  }

  async function openArtifact(target: string): Promise<void> {
    if (!bridgeAvailable) {
      setStatusMessage("Desktop bridge unavailable. Artifact open requires Electron.");
      return;
    }
    const result = await electronApi.openArtifact({ target });
    if (!result.opened) {
      setStatusMessage(`Artifact open failed: ${result.reason || "unknown"}`);
    }
  }

  function openThread(summary: ThreadSummaryDTO): void {
    if (isSupervisorSummary(summary)) {
      if (summary.manager_session_id) {
        setManagerSessionId(summary.manager_session_id);
      }
      setView({ kind: "supervisor", flowId: summary.flow_id });
      setRailSection(summary.manager_session_id ? "manager" : "history");
      return;
    }
    if (isManagerSummary(summary) && summary.manager_session_id) {
      setManagerSessionId(summary.manager_session_id);
      setView({ kind: "manager" });
      setRailSection("manager");
      return;
    }
    if (summary.thread_kind === "template") {
      setView({ kind: "templates" });
      setRailSection("templates");
    }
  }

  function handleActionTarget(target: string): void {
    const token = String(target || "").trim();
    if (!token) {
      return;
    }
    if (token.startsWith("flow:")) {
      const flowId = token.slice("flow:".length);
      setView({ kind: "supervisor", flowId });
      return;
    }
    if (token.startsWith("role:") && activeFlowId) {
      const roleId = token.slice("role:".length);
      setView({ kind: "agent", flowId: activeFlowId, roleId });
      return;
    }
    if (token.startsWith("artifact:")) {
      void openArtifact(token.slice("artifact:".length));
      return;
    }
    if (token.startsWith("template:")) {
      setTemplateAssetId(token.slice("template:".length));
      setRailSection("templates");
      setView({ kind: "templates" });
      return;
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
        managerSessionId: view.kind === "new-flow" ? "" : managerSessionId,
        manageTarget: view.kind === "new-flow" ? "new" : undefined
      });
      const nextManagerSessionId = String(result.manager_session_id || "").trim();
      if (nextManagerSessionId) {
        setManagerSessionId(nextManagerSessionId);
      }
      setMessageDraft("");
      await refreshAll();
      const launchedFlowId = String(result.launched_flow?.flow_id || "").trim();
      if (launchedFlowId) {
        setRailSection("manager");
        setView({ kind: "supervisor", flowId: launchedFlowId });
        setStatusMessage(`Supervisor started: ${launchedFlowId}`);
      } else {
        setRailSection("manager");
        setView({ kind: "manager" });
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

  function renderManagerStream() {
    const payload = managerQuery.data;
    const blocks = payload?.blocks || [];
    const modeLabel = view.kind === "new-flow" ? "New Flow" : "Manager Thread";

    return (
      <section className="thread-page thread-page-manager">
        <header className="thread-header">
          <div className="thread-heading">
            <p className="page-kicker">Butler Manager</p>
            <h1>{view.kind === "new-flow" ? "新建 Flow" : payload?.thread.title || "Manager 管理台"}</h1>
            <p>
              {view.kind === "new-flow"
                ? "从一个空白的 manager thread 开始，先把 idea、requirements 和 delivery 对齐。"
                : payload?.thread.subtitle || "先对齐 idea，再落 requirements / delivery / test standards。"}
            </p>
          </div>
          <div className="thread-hero-pills">
            <span className="hero-pill">{payload?.thread.status || "draft"}</span>
            <span className="hero-pill">{payload?.manager_stage || "opening"}</span>
            {payload?.linked_flow_id ? <span className="hero-pill">{`Flow ${payload.linked_flow_id}`}</span> : null}
          </div>
        </header>

        <section className="thread-surface single-column manager-surface">
          <div className="thread-stream-panel">
            <div className="thread-stream-header">
              <strong>Current Thread</strong>
              <span>{blocks.length} blocks</span>
            </div>

            {view.kind === "new-flow" ? (
              <div className="thread-intro-card">
                <span className="thread-intro-kicker">Start from Butler</span>
                <h2>先把团队要做什么说清楚，再创建 Supervisor</h2>
                <p>这里保留 Butler 的 Manager 语义，但阅读面和输入区会更像 Codex 的桌面工作台。</p>
              </div>
            ) : null}

            <div className="stream-list thread-stream-list">
              {blocks.map((block) => (
                <StreamBlock
                  block={block}
                  expanded={currentBlockExpanded(block)}
                  key={block.block_id}
                  onActionTarget={handleActionTarget}
                  onToggle={() => toggleBlock(block.block_id)}
                />
              ))}
            </div>
          </div>

          <form className="thread-dock composer-shell manager-dock" onSubmit={(event) => void sendManagerMessage(event)}>
            <div className="composer-topline">
              <ComposerPill label="Surface" value={modeLabel} />
              <ComposerPill label="Target" value={view.kind === "new-flow" ? "Blank manager thread" : "Continue with Manager"} />
              <ComposerPill label="Theme" value={theme === "night" ? "Night" : "Day"} />
            </div>

            <label htmlFor="manager-composer">{view.kind === "new-flow" ? "Start with Manager" : "Continue with Manager"}</label>

            <div className="composer-row">
              <textarea
                id="manager-composer"
                ref={composerRef}
                className="composer-textarea"
                placeholder={
                  view.kind === "new-flow"
                    ? "比如：我想把 Butler Flow Desktop 升级成更像 Codex 的工作台，但仍保留 Butler 的 thread-first 语义。"
                    : "继续补充需求、交付标准、测试要求，或确认让 Manager 创建并切到 Supervisor。"
                }
                value={messageDraft}
                onChange={(event) => setMessageDraft(event.target.value)}
              />
            </div>

            <div className="composer-actions">
              <span className="composer-hint">
                默认小输入框，随输入增长，但最大不超过页面高度的 1/3。
              </span>
              <button className="ui-button ui-button-primary" disabled={!messageDraft.trim() || sendingManagerMessage} type="submit">
                <Send size={16} />
                {sendingManagerMessage ? "Sending..." : "Send to Manager"}
              </button>
            </div>
          </form>
        </section>
      </section>
    );
  }

  function renderHistoryPage() {
    const historyItems = homeQuery.data?.history || [];
    return (
      <section className="thread-page">
        <header className="thread-header compact">
          <div className="thread-heading">
            <p className="page-kicker">Thread History</p>
            <h1>Project Threads</h1>
            <p>这里专门用于切换 Butler 当前项目线程，不再承担旧式 dashboard 说明页角色。</p>
          </div>
        </header>

        <div className="history-list refined">
          {historyItems.length === 0 ? (
            <div className="empty-inline">还没有 thread，先从 `New Flow` 开始。</div>
          ) : (
            historyItems.map((summary) => (
              <button className="history-card refined" key={summary.thread_id} onClick={() => openThread(summary)} type="button">
                <div className="history-card-topline">
                  <div className="history-card-copy">
                    <span className="history-card-kicker">{summary.thread_kind}</span>
                    <h3>{summary.title}</h3>
                  </div>
                  <span className="history-card-time">{shortTime(summary.updated_at || summary.created_at)}</span>
                </div>
                <p>{summary.subtitle || "Open thread"}</p>
                <div className="history-card-meta">
                  {[summary.status, summary.current_phase, summary.active_role_id].filter(Boolean).join(" · ") || "Open"}
                </div>
              </button>
            ))
          )}
        </div>
      </section>
    );
  }

  function renderSupervisorPage() {
    const payload = supervisorQuery.data;
    const roleChips = payload?.role_strip.role_chips || [];
    return (
      <section className="thread-page">
        <header className="thread-header">
          <div className="thread-heading">
            <p className="page-kicker">Supervisor Thread</p>
            <h1>{payload?.thread.title || "Supervisor"}</h1>
            <p>{payload?.thread.subtitle || "Supervisor 正在以流式方式推进团队执行。"}</p>
          </div>
          <div className="thread-hero-pills">
            <span className="hero-pill">{payload?.summary.effective_status || "running"}</span>
            <span className="hero-pill">{payload?.summary.effective_phase || "implement"}</span>
            <span className="hero-pill">{payload?.summary.active_role_id || "supervisor"}</span>
          </div>
        </header>

        <section className="thread-surface single-column">
          <div className="thread-stream-panel">
            <div className="thread-toolbar">
              <div className="role-chip-row">
                {roleChips.map((chip) => {
                  const roleId = String(chip.role_id || "");
                  return (
                    <button
                      className={`role-chip ${chip.is_active ? "is-active" : ""}`}
                      key={roleId}
                      onClick={() => setView({ kind: "agent", flowId: activeFlowId, roleId })}
                      type="button"
                    >
                      <strong>{roleId}</strong>
                      <span>{String(chip.state || "idle")}</span>
                    </button>
                  );
                })}
              </div>

              <div className="action-strip">
                <button className="ui-button ui-button-secondary" onClick={() => void performFlowAction("pause")} type="button">
                  <PauseCircle size={16} />
                  Pause
                </button>
                <button className="ui-button ui-button-secondary" onClick={() => void performFlowAction("resume")} type="button">
                  <PlayCircle size={16} />
                  Resume
                </button>
                <button className="ui-button ui-button-secondary" onClick={() => void performFlowAction("retry_current_phase")} type="button">
                  <RefreshCcw size={16} />
                  Retry Phase
                </button>
              </div>
            </div>

            <div className="stream-list thread-stream-list">
              {(payload?.blocks || []).map((block) => (
                <StreamBlock
                  block={block}
                  expanded={currentBlockExpanded(block)}
                  key={block.block_id}
                  onActionTarget={handleActionTarget}
                  onToggle={() => toggleBlock(block.block_id)}
                />
              ))}
            </div>
          </div>
        </section>
      </section>
    );
  }

  function renderAgentPage() {
    const payload = agentQuery.data;
    return (
      <section className="thread-page">
        <header className="thread-header">
          <div className="thread-heading">
            <button className="back-link" onClick={() => setView({ kind: "supervisor", flowId: activeFlowId })} type="button">
              <ArrowLeft size={16} />
              Back to Supervisor
            </button>
            <p className="page-kicker">Agent Focus</p>
            <h1>{payload?.title || "Agent"}</h1>
            <p>{payload?.thread.subtitle || "这是当前 flow thread 在单个 role 视角下的整线程聚焦页。"}</p>
          </div>
          <div className="thread-hero-pills">
            <span className="hero-pill">{payload?.role_id || "agent"}</span>
            <span className="hero-pill">{String(payload?.role.state || "idle")}</span>
          </div>
        </header>

        <section className="thread-surface single-column">
          <div className="thread-stream-panel">
            <div className="thread-stream-header">
              <strong>Role Lens</strong>
              <span>{payload?.role_id || "agent"}</span>
            </div>
            <div className="stream-list thread-stream-list">
              {(payload?.blocks || []).map((block) => (
                <StreamBlock
                  block={block}
                  expanded={currentBlockExpanded(block)}
                  key={block.block_id}
                  onActionTarget={handleActionTarget}
                  onToggle={() => toggleBlock(block.block_id)}
                />
              ))}
            </div>
          </div>
        </section>
      </section>
    );
  }

  function renderTemplatesPage() {
    const payload = templateQuery.data;
    const assets = payload?.assets || [];
    return (
      <section className="thread-page">
        <header className="thread-header">
          <div className="thread-heading">
            <p className="page-kicker">Template Team</p>
            <h1>{payload?.thread.title || "Templates"}</h1>
            <p>{payload?.thread.subtitle || "统一查看 template、默认 agent team 与 review standards。"}</p>
          </div>
        </header>

        <section className="thread-surface single-column">
          <div className="thread-stream-panel">
            <div className="asset-selector">
              {assets.map((asset) => {
                const assetId = String(asset.asset_id || asset.id || "");
                return (
                  <button
                    className={`asset-pill ${assetId === payload?.asset_id ? "is-active" : ""}`}
                    key={assetId}
                    onClick={() => setTemplateAssetId(assetId)}
                    type="button"
                  >
                    {String(asset.label || asset.title || assetId)}
                  </button>
                );
              })}
            </div>

            <div className="stream-list thread-stream-list">
              {(payload?.blocks || []).map((block) => (
                <StreamBlock
                  block={block}
                  expanded={currentBlockExpanded(block)}
                  key={block.block_id}
                  onActionTarget={handleActionTarget}
                  onToggle={() => toggleBlock(block.block_id)}
                />
              ))}
            </div>
          </div>
        </section>
      </section>
    );
  }

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
    if (view.kind === "history") {
      return renderHistoryPage();
    }
    if (view.kind === "templates") {
      return renderTemplatesPage();
    }
    if (view.kind === "supervisor") {
      return renderSupervisorPage();
    }
    if (view.kind === "agent") {
      return renderAgentPage();
    }
    return renderManagerStream();
  }

  const recentThreads = homeQuery.data?.history || [];

  return (
    <div className="desktop-root" data-theme={theme}>
      <aside className="desktop-rail">
        <div className="rail-brand">
          <span className="rail-brand-mark">
            <Sparkles size={16} />
          </span>
          <div>
            <strong>Butler Flow Desktop</strong>
            <span>Codex-aligned shell, Butler-native threads</span>
          </div>
        </div>

        <div className="rail-context">
          <span className="rail-context-label">Workspace</span>
          <strong title={configPath}>{configPath || "Select a Butler config"}</strong>
        </div>

        <div className="rail-nav">
          <RailButton
            active={railSection === "manager"}
            detail="brainstorm → requirements → launch"
            icon={<Bot size={16} />}
            label="Manager 管理台"
            onClick={() => {
              setRailSection("manager");
              setView({ kind: "manager" });
            }}
          />
          <RailButton
            active={railSection === "history"}
            detail="project threads"
            icon={<History size={16} />}
            label="Threads 历史"
            onClick={() => {
              setRailSection("history");
              setView({ kind: "history" });
            }}
          />
          <RailButton
            active={railSection === "new-flow"}
            detail="start from a blank manager thread"
            icon={<PlusSquare size={16} />}
            label="New Flow 新建"
            onClick={() => {
              setManagerSessionId("");
              setRailSection("new-flow");
              setView({ kind: "new-flow" });
              setMessageDraft("");
            }}
          />
          <RailButton
            active={railSection === "templates"}
            detail="template + default agent team"
            icon={<LayoutTemplate size={16} />}
            label="Templates 模板"
            onClick={() => {
              setRailSection("templates");
              setView({ kind: "templates" });
            }}
          />
        </div>

        <div className="rail-thread-list">
          <div className="rail-section-header">
            <span>Recent Threads</span>
            <span>{recentThreads.length}</span>
          </div>
          {recentThreads.length === 0 ? (
            <div className="empty-inline small">Attach config 后，这里会显示 manager 与 flow 线程。</div>
          ) : (
            recentThreads.slice(0, 8).map((summary) => (
              <ThreadShortcut
                active={
                  (isSupervisorSummary(summary) && view.kind === "supervisor" && view.flowId === summary.flow_id) ||
                  (isManagerSummary(summary) && view.kind === "manager" && managerSessionId === summary.manager_session_id)
                }
                key={summary.thread_id}
                onClick={() => openThread(summary)}
                summary={summary}
              />
            ))
          )}
        </div>

        <div className="rail-footer">
          <div className="rail-footer-block">
            <span>Theme</span>
            <strong>{theme === "night" ? "Night" : "Day"}</strong>
          </div>
          <div className="rail-footer-block">
            <span>Bridge</span>
            <strong>{bridgeAvailable ? "Connected" : "Browser only"}</strong>
          </div>
        </div>
      </aside>

      <main className="desktop-main">
        <header className="global-header">
          <div className="global-header-copy">
            <span>Current Surface</span>
            <strong>
              {view.kind === "manager" && "Manager thread"}
              {view.kind === "new-flow" && "Blank manager thread"}
              {view.kind === "history" && "Project threads"}
              {view.kind === "templates" && "Template team"}
              {view.kind === "supervisor" && "Supervisor thread"}
              {view.kind === "agent" && "Agent focus"}
            </strong>
          </div>
          <div className="global-header-actions">
            <button className="ui-button ui-button-secondary" onClick={() => void chooseConfig()} type="button">
              <FolderSearch size={16} />
              Config
            </button>
            <button className="ui-button ui-button-secondary" disabled={!bridgeAvailable} onClick={() => void refreshAll()} type="button">
              <RefreshCcw size={16} />
              Refresh
            </button>
            <button className="ui-button ui-button-secondary" onClick={switchTheme} type="button">
              {theme === "day" ? <Moon size={16} /> : <SunMedium size={16} />}
              {theme === "day" ? "Night" : "Day"}
            </button>
          </div>
        </header>

        {renderMainContent()}

        {bridgeAvailable && homeQuery.error ? (
          <div className="status-toast error">Thread home load failed: {String(homeQuery.error.message)}</div>
        ) : null}
        {bridgeAvailable && managerQuery.error ? (
          <div className="status-toast error">Manager thread load failed: {String(managerQuery.error.message)}</div>
        ) : null}
        {bridgeAvailable && supervisorQuery.error ? (
          <div className="status-toast error">Supervisor thread load failed: {String(supervisorQuery.error.message)}</div>
        ) : null}
        {bridgeAvailable && agentQuery.error ? (
          <div className="status-toast error">Agent focus load failed: {String(agentQuery.error.message)}</div>
        ) : null}
        {bridgeAvailable && templateQuery.error ? (
          <div className="status-toast error">Template load failed: {String(templateQuery.error.message)}</div>
        ) : null}
        {statusMessage ? <div className="status-toast">{statusMessage}</div> : null}
      </main>
    </div>
  );
}
