import { FormEvent, KeyboardEvent, ReactNode, useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  AlertCircle,
  Bot,
  FolderSearch,
  Moon,
  PauseCircle,
  PlayCircle,
  PlusSquare,
  RefreshCcw,
  Send,
  Sparkles,
  SunMedium,
  Wrench,
  X
} from "lucide-react";
import type {
  AgentFocusDTO,
  ManagerThreadDTO,
  SupervisorThreadDTO,
  TemplateTeamDTO,
  ThreadBlockDTO,
  ThreadHomeDTO,
  ThreadSummaryDTO
} from "../shared/dto";
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

type ConversationMode = "mission" | "runtime" | "studio";

type DetailState =
  | { kind: "none" }
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
    for (const key of ["summary", "label", "title", "goal", "reason", "message", "decision", "response"]) {
      const token = String(record[key] || "").trim();
      if (token) {
        return token;
      }
    }
    return JSON.stringify(value, null, 2);
  }
  return String(value || "").trim();
}

function shortTime(value: string): string {
  const token = String(value || "").trim();
  if (!token) {
    return "刚刚";
  }
  return token.slice(5, 16).replace(" ", " · ");
}

function autoResizeTextarea(node: HTMLTextAreaElement | null): void {
  if (!node || typeof window === "undefined") {
    return;
  }
  const maxHeight = Math.floor(window.innerHeight / 3);
  node.style.height = "0px";
  const nextHeight = Math.max(84, Math.min(node.scrollHeight, maxHeight));
  node.style.height = `${nextHeight}px`;
  node.style.overflowY = node.scrollHeight > maxHeight ? "auto" : "hidden";
}

function isManagerSummary(summary: ThreadSummaryDTO): boolean {
  return String(summary.thread_kind || "").trim() === "manager";
}

function isSupervisorSummary(summary: ThreadSummaryDTO): boolean {
  return String(summary.thread_kind || "").trim() === "supervisor";
}

function blockMeta(block: ThreadBlockDTO): string[] {
  return [block.kind, block.phase || "", ...(block.tags || [])].filter(Boolean);
}

function narratorLens(kind: string, fallback: ConversationMode): string {
  const token = String(kind || "").trim();
  if (["team", "team_draft", "launch", "requirements", "opening", "idea"].includes(token)) {
    return "manager";
  }
  if (["overview", "policy", "contract", "team_template"].includes(token)) {
    return "studio";
  }
  if (["decision", "artifact", "progress", "start", "role_brief"].includes(token)) {
    return "runtime";
  }
  return fallback;
}

function buildManagerThreads(home: ThreadHomeDTO | undefined): ThreadSummaryDTO[] {
  const ordered: ThreadSummaryDTO[] = [];
  const seen = new Set<string>();
  const history = home?.history || [];

  function push(summary: ThreadSummaryDTO): void {
    const key = String(summary.manager_session_id || summary.thread_id || "").trim();
    if (!key || seen.has(key)) {
      return;
    }
    seen.add(key);
    ordered.push(summary);
  }

  for (const summary of history) {
    if (isManagerSummary(summary)) {
      push(summary);
    }
  }
  for (const summary of history) {
    if (isSupervisorSummary(summary) && summary.manager_session_id) {
      push({
        ...summary,
        thread_id: `manager:${summary.manager_session_id}`,
        thread_kind: "manager",
        title: summary.title || "Manager Thread",
        subtitle: summary.subtitle || "Continue with Manager"
      });
    }
  }

  const defaultManagerSessionId = String(home?.manager_entry.default_manager_session_id || "").trim();
  if (defaultManagerSessionId && !seen.has(defaultManagerSessionId)) {
    push({
      thread_id: `manager:${defaultManagerSessionId}`,
      thread_kind: "manager",
      title: String(home?.manager_entry.title || "Manager"),
      subtitle: String(home?.manager_entry.draft_summary || "Continue with Manager"),
      status: String(home?.manager_entry.status || "active"),
      created_at: "",
      updated_at: "",
      manager_session_id: defaultManagerSessionId,
      flow_id: String(home?.manager_entry.active_flow_id || ""),
      active_role_id: "",
      current_phase: "",
      badge: "manager",
      tags: ["manager"]
    });
  }

  return ordered;
}

function isHistoricalStatus(status: string): boolean {
  return ["completed", "failed", "archived", "cancelled"].includes(String(status || "").trim().toLowerCase());
}

function composerLabel(mode: ConversationMode, isNewThread: boolean): string {
  if (isNewThread) {
    return "Start with Manager";
  }
  if (mode === "runtime") {
    return "Guide the runtime through Manager";
  }
  if (mode === "studio") {
    return "Edit contract or policy through Manager";
  }
  return "Continue with Manager";
}

function composerPlaceholder(mode: ConversationMode, isNewThread: boolean): string {
  if (isNewThread) {
    return "例如：/start 一个 Butler Desktop 升级 mission，先帮我收敛需求、验收和团队分工。";
  }
  if (mode === "runtime") {
    return "例如：/pause、/resume，或继续告诉 Manager 当前阶段该如何推进。";
  }
  if (mode === "studio") {
    return "例如：更新 contract、policy、role guidance，或要求 Manager 重新整理验收口径。";
  }
  return "继续和 Manager 协调 mission、追加需求、改验收、或发起下一轮工作。";
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
          <span>Butler Desktop</span>
        </div>
        <h2>先连接 Butler config</h2>
        <p>连接后，Desktop 会把 live manager threads、runtime signals 和 studio context 收进同一个主对话壳。</p>
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
        <p>当前页面没有注入 `window.butlerDesktop`，所以无法读取 Manager threads、runtime 细流或发送 manager message。</p>
        <p>请从 Electron Butler Desktop 窗口打开；如果你现在看到的是纯浏览器 / Vite 页面，这属于预期。</p>
      </div>
    </section>
  );
}

function ThreadRow({
  summary,
  active,
  onClick
}: {
  summary: ThreadSummaryDTO;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button className={`thread-row ${active ? "is-active" : ""}`} onClick={onClick} type="button">
      <div className="thread-row-topline">
        <span className="thread-row-kicker">{summary.badge || summary.status || "thread"}</span>
        <span className="thread-row-time">{shortTime(summary.updated_at || summary.created_at)}</span>
      </div>
      <strong className="thread-row-title">{summary.title || "Untitled Manager Thread"}</strong>
      <span className="thread-row-subtitle">{summary.subtitle || "Continue with Manager"}</span>
      <span className="thread-row-meta">
        {[summary.status, summary.current_phase, summary.active_role_id].filter(Boolean).join(" · ") || "thread"}
      </span>
    </button>
  );
}

function ModeButton({
  active,
  label,
  onClick,
  disabled
}: {
  active: boolean;
  label: string;
  onClick: () => void;
  disabled?: boolean;
}) {
  return (
    <button className={`mode-button ${active ? "is-active" : ""}`} disabled={disabled} onClick={onClick} type="button">
      {label}
    </button>
  );
}

function StatusChip({ children }: { children: ReactNode }) {
  return <span className="status-chip">{children}</span>;
}

function NarratorMessage({
  block,
  defaultLens,
  expanded,
  onToggle,
  onActionTarget
}: {
  block: ThreadBlockDTO;
  defaultLens: ConversationMode;
  expanded: boolean;
  onToggle: () => void;
  onActionTarget: (target: string) => void;
}) {
  const detailPayload = block.payload || {};
  const hasDetail = Object.keys(detailPayload).length > 0;
  const lens = narratorLens(block.kind, defaultLens);

  return (
    <article className={`narrator-message lens-${lens}`}>
      <div className="message-topline">
        <div className="message-author">
          <span className="message-avatar">
            <Bot size={14} />
          </span>
          <div>
            <strong>Manager</strong>
            <span>{lens === "manager" ? "main narration" : `${lens} relay`}</span>
          </div>
        </div>
        <div className="message-meta">
          {blockMeta(block).slice(0, 3).map((item) => (
            <span className="meta-pill" key={`${block.block_id}:${item}`}>
              {item}
            </span>
          ))}
          <span className="message-time">{shortTime(block.created_at)}</span>
        </div>
      </div>

      <div className="message-copy">
        <h3>{block.title}</h3>
        <p>{block.summary}</p>
      </div>

      <div className="message-actions">
        {block.action_target ? (
          <button className="ui-button ui-button-secondary" onClick={() => onActionTarget(block.action_target || "")} type="button">
            {block.action_label || "Open"}
          </button>
        ) : null}
        {hasDetail ? (
          <button className="ui-button ui-button-ghost" onClick={onToggle} type="button">
            {expanded ? "收起细节" : "展开细节"}
          </button>
        ) : null}
      </div>

      {expanded && hasDetail ? (
        <div className="message-detail">
          <pre>{JSON.stringify(detailPayload, null, 2)}</pre>
        </div>
      ) : null}
    </article>
  );
}

function RuntimeStrip({
  payload,
  onRoleSelect
}: {
  payload?: SupervisorThreadDTO;
  onRoleSelect: (roleId: string) => void;
}) {
  const roleChips = payload?.role_strip.role_chips || [];

  return (
    <section className="context-strip">
      <div className="context-strip-copy">
        <span className="context-strip-kicker">Runtime Lens</span>
        <strong>{payload?.thread.title || "No active runtime yet"}</strong>
        <p>
          {payload?.thread.subtitle ||
            "当 mission 已启动时，runtime 的 accepted progress、handoff 与 operator action 会在这里以内联方式进入主对话。"}
        </p>
      </div>
      <div className="context-strip-aside">
        <div className="compact-stats">
          <span>{payload?.summary.effective_status || "draft"}</span>
          <span>{payload?.summary.effective_phase || "opening"}</span>
          <span>{payload?.summary.active_role_id || "manager"}</span>
        </div>
        {roleChips.length ? (
          <div className="role-chip-row">
            {roleChips.map((chip) => {
              const roleId = String(chip.role_id || "");
              return (
                <button
                  className={`role-chip ${chip.is_active ? "is-active" : ""}`}
                  key={roleId}
                  onClick={() => onRoleSelect(roleId)}
                  type="button"
                >
                  <strong>{roleId}</strong>
                  <span>{String(chip.state || "idle")}</span>
                </button>
              );
            })}
          </div>
        ) : null}
      </div>
    </section>
  );
}

function StudioStrip({
  payload,
  onSelectAsset
}: {
  payload?: TemplateTeamDTO;
  onSelectAsset: (assetId: string) => void;
}) {
  const assets = payload?.assets || [];
  return (
    <section className="context-strip">
      <div className="context-strip-copy">
        <span className="context-strip-kicker">Studio Lens</span>
        <strong>{formatValue(payload?.selected_asset.label) || payload?.thread.title || "Contract Studio"}</strong>
        <p>{payload?.manager_notes || "通过 Studio 语境收口 contract、team guidance 和 review checklist。"} </p>
      </div>
      <div className="context-strip-aside">
        {assets.length ? (
          <div className="asset-pill-row">
            {assets.map((asset) => {
              const assetId = String(asset.asset_id || asset.id || "");
              return (
                <button
                  className={`asset-pill ${assetId === payload?.asset_id ? "is-active" : ""}`}
                  key={assetId}
                  onClick={() => onSelectAsset(assetId)}
                  type="button"
                >
                  {String(asset.label || asset.title || assetId)}
                </button>
              );
            })}
          </div>
        ) : null}
      </div>
    </section>
  );
}

function AgentDetailSheet({
  payload,
  open,
  onClose,
  expandedBlocks,
  onToggle,
  onActionTarget
}: {
  payload?: AgentFocusDTO;
  open: boolean;
  onClose: () => void;
  expandedBlocks: Record<string, boolean>;
  onToggle: (blockId: string) => void;
  onActionTarget: (target: string) => void;
}) {
  if (!open) {
    return null;
  }

  return (
    <aside aria-label="Agent detail" className="detail-sheet" role="dialog">
      <div className="detail-sheet-header">
        <div>
          <span className="detail-kicker">Agent Drill-in</span>
          <h2>{payload?.title || "Agent stream"}</h2>
          <p>{payload?.thread.subtitle || "完整的 agent 输出流会在这里展开，但不抢主对话的位置。"}</p>
        </div>
        <button aria-label="Close agent detail" className="detail-close" onClick={onClose} type="button">
          <X size={16} />
        </button>
      </div>

      <div className="detail-meta">
        <StatusChip>{payload?.role_id || "agent"}</StatusChip>
        <StatusChip>{String(payload?.role.state || "idle")}</StatusChip>
        <StatusChip>{payload?.summary.effective_phase || "phase"}</StatusChip>
      </div>

      <div className="detail-body">
        {(payload?.blocks || []).map((block) => (
          <NarratorMessage
            block={block}
            defaultLens="runtime"
            expanded={block.block_id in expandedBlocks ? Boolean(expandedBlocks[block.block_id]) : Boolean(block.expanded_by_default)}
            key={block.block_id}
            onActionTarget={onActionTarget}
            onToggle={() => onToggle(block.block_id)}
          />
        ))}
      </div>
    </aside>
  );
}

export default function App() {
  const queryClient = useQueryClient();
  const composerRef = useRef<HTMLTextAreaElement | null>(null);
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
  const templateQuery = useTemplateTeam(configPath, templateAssetId, bridgeAvailable && mode === "studio");

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
    setStatusMessage("Mission shell refreshed.");
  }

  async function performFlowAction(type: string): Promise<void> {
    if (!bridgeAvailable) {
      setStatusMessage("Desktop bridge unavailable. Runtime actions require Electron.");
      return;
    }
    if (!linkedFlowId) {
      return;
    }
    const payload = await electronApi.performAction({
      configPath,
      flowId: linkedFlowId,
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
    const targetManagerSessionId = String(summary.manager_session_id || "").trim();
    if (!targetManagerSessionId) {
      return;
    }
    setIsComposingNewThread(false);
    setManagerSessionId(targetManagerSessionId);
    setMode("mission");
    setDetailState({ kind: "none" });
    setMessageDraft("");
  }

  function openNewThread(): void {
    setIsComposingNewThread(true);
    setManagerSessionId("");
    setMode("mission");
    setDetailState({ kind: "none" });
    setMessageDraft("");
  }

  function handleActionTarget(target: string): void {
    const token = String(target || "").trim();
    if (!token) {
      return;
    }
    if (token.startsWith("flow:")) {
      setMode("runtime");
      return;
    }
    if (token.startsWith("role:") && linkedFlowId) {
      const roleId = token.slice("role:".length);
      setMode("runtime");
      setDetailState({ kind: "agent", flowId: linkedFlowId, roleId });
      return;
    }
    if (token.startsWith("artifact:")) {
      void openArtifact(token.slice("artifact:".length));
      return;
    }
    if (token.startsWith("template:")) {
      setTemplateAssetId(token.slice("template:".length));
      setMode("studio");
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
        managerSessionId: isComposingNewThread ? "" : managerSessionId,
        manageTarget: isComposingNewThread ? "new" : undefined
      });
      const nextManagerSessionId = String(result.manager_session_id || "").trim();
      if (nextManagerSessionId) {
        setManagerSessionId(nextManagerSessionId);
        setIsComposingNewThread(false);
      }
      setMessageDraft("");
      await refreshAll();
      const launchedFlowId = String(result.launched_flow?.flow_id || "").trim();
      if (launchedFlowId) {
        setMode("runtime");
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
  const managerBlocks = managerQuery.data?.blocks || [];
  const runtimeBlocks = supervisorQuery.data?.blocks || [];
  const studioBlocks = templateQuery.data?.blocks || [];
  const managerLabel = composerLabel(mode, isComposingNewThread);

  function renderConversationShell() {
    return (
      <section className="conversation-shell">
        <header className="mission-header">
          <div className="mission-header-main">
            <span className="mission-kicker">Manager thread</span>
            <div className="mission-title-row">
              <h1>{currentTitle}</h1>
              <div className="mission-status-row">
                <StatusChip>{mode}</StatusChip>
                <StatusChip>{currentThread?.status || (isComposingNewThread ? "draft" : "active")}</StatusChip>
                {runtimeAvailable ? <StatusChip>{supervisorQuery.data?.summary.effective_phase || "runtime ready"}</StatusChip> : null}
                {runtimeAvailable ? <StatusChip>{supervisorQuery.data?.summary.active_role_id || "manager"}</StatusChip> : null}
              </div>
            </div>
            <p>{currentSubtitle}</p>
          </div>

          <div className="mission-header-aside">
            <div className="mode-switcher" role="tablist" aria-label="Conversation modes">
              <ModeButton active={mode === "mission"} label="Mission" onClick={() => setMode("mission")} />
              <ModeButton active={mode === "runtime"} disabled={!runtimeAvailable} label="Runtime" onClick={() => setMode("runtime")} />
              <ModeButton active={mode === "studio"} disabled={!studioAvailable} label="Studio" onClick={() => setMode("studio")} />
            </div>

            <div className="header-actions">
              {runtimeAvailable ? (
                <>
                  <button className="ui-button ui-button-secondary" onClick={() => void performFlowAction("pause")} type="button">
                    <PauseCircle size={16} />
                    Pause
                  </button>
                  <button className="ui-button ui-button-secondary" onClick={() => void performFlowAction("resume")} type="button">
                    <PlayCircle size={16} />
                    Resume
                  </button>
                </>
              ) : null}
              <button className="ui-button ui-button-secondary" onClick={() => void refreshAll()} type="button">
                <RefreshCcw size={16} />
                Refresh
              </button>
              <button className="ui-button ui-button-secondary" onClick={() => void chooseConfig()} type="button">
                <FolderSearch size={16} />
                Config
              </button>
              <button className="ui-button ui-button-secondary" onClick={switchTheme} type="button">
                {theme === "day" ? <Moon size={16} /> : <SunMedium size={16} />}
                {theme === "day" ? "Night" : "Day"}
              </button>
            </div>
          </div>
        </header>

        {statusMessage ? <div className="status-banner">{statusMessage}</div> : null}

        <div className="conversation-frame">
          <div className="conversation-scroll">
            <div className="conversation-intro">
              <div className="conversation-intro-mark">
                <Sparkles size={16} />
              </div>
              <div>
                <strong>Mission narrator</strong>
                <p>默认只让 Manager 出面，runtime / studio / agent 输出以内联证据块和折叠细流进入同一条主对话。</p>
              </div>
            </div>

            <div className="message-column">
              {managerBlocks.map((block) => (
                <NarratorMessage
                  block={block}
                  defaultLens="mission"
                  expanded={currentBlockExpanded(block)}
                  key={block.block_id}
                  onActionTarget={handleActionTarget}
                  onToggle={() => toggleBlock(block.block_id)}
                />
              ))}

              {mode === "runtime" ? (
                <>
                  <RuntimeStrip
                    payload={supervisorQuery.data}
                    onRoleSelect={(roleId) => {
                      if (!linkedFlowId) {
                        return;
                      }
                      setDetailState({ kind: "agent", flowId: linkedFlowId, roleId });
                    }}
                  />
                  {(runtimeBlocks.length ? runtimeBlocks : []).map((block) => (
                    <NarratorMessage
                      block={block}
                      defaultLens="runtime"
                      expanded={currentBlockExpanded(block)}
                      key={block.block_id}
                      onActionTarget={handleActionTarget}
                      onToggle={() => toggleBlock(block.block_id)}
                    />
                  ))}
                  {!runtimeBlocks.length ? (
                    <div className="empty-inline">当前还没有新的 runtime 细流，等下一次 accepted progress 或 operator action 进入后会显示在这里。</div>
                  ) : null}
                </>
              ) : null}

              {mode === "studio" ? (
                <>
                  <StudioStrip payload={templateQuery.data} onSelectAsset={setTemplateAssetId} />
                  {(studioBlocks.length ? studioBlocks : []).map((block) => (
                    <NarratorMessage
                      block={block}
                      defaultLens="studio"
                      expanded={currentBlockExpanded(block)}
                      key={block.block_id}
                      onActionTarget={handleActionTarget}
                      onToggle={() => toggleBlock(block.block_id)}
                    />
                  ))}
                  {!studioBlocks.length ? (
                    <div className="empty-inline">Studio 目前还没有额外块；进入后会优先展示 contract、role guidance 和 checklist 摘要。</div>
                  ) : null}
                </>
              ) : null}
            </div>
          </div>

          <form className="composer-shell mission-composer" onSubmit={(event) => void sendManagerMessage(event)}>
            <div className="composer-topline">
              <span className="composer-pill">
                <strong>Mode</strong>
                <span>{mode}</span>
              </span>
              <span className="composer-pill">
                <strong>Thread</strong>
                <span>{isComposingNewThread ? "new" : currentTitle}</span>
              </span>
              <span className="composer-pill">
                <strong>Commands</strong>
                <span>/start /pause /resume</span>
              </span>
            </div>

            <label htmlFor="manager-composer">{managerLabel}</label>

            <div className="composer-row">
              <textarea
                id="manager-composer"
                ref={composerRef}
                className="composer-textarea"
                placeholder={composerPlaceholder(mode, isComposingNewThread)}
                value={messageDraft}
                onChange={(event) => setMessageDraft(event.target.value)}
              />
            </div>

            <div className="composer-actions">
              <span className="composer-hint">
                继续对 Manager 发话即可；runtime、studio 和 agent 只作为同一条 mission conversation 里的内部来源浮现。
              </span>
              <button className="ui-button ui-button-primary" disabled={!messageDraft.trim() || sendingManagerMessage} type="submit">
                <Send size={16} />
                {sendingManagerMessage ? "Sending..." : "Send to Manager"}
              </button>
            </div>
          </form>
        </div>
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
    return renderConversationShell();
  }

  return (
    <div className="desktop-root" data-theme={theme}>
      <aside className="desktop-rail">
        <div className="rail-brand">
          <span className="rail-brand-mark">
            <Sparkles size={16} />
          </span>
          <div>
            <strong>Butler Desktop</strong>
            <span>Manager-first mission shell</span>
          </div>
        </div>

        <div className="rail-context">
          <span className="rail-context-label">Workspace</span>
          <strong title={configPath}>{configPath || "Select a Butler config"}</strong>
        </div>

        <button className="launch-thread-button" onClick={openNewThread} type="button">
          <PlusSquare size={16} />
          <span>New thread</span>
        </button>

        <div className="thread-list-shell">
          <div className="rail-section-header">
            <span>Active</span>
            <span>{activeThreads.length}</span>
          </div>
          {activeThreads.length ? (
            activeThreads.map((summary) => (
              <ThreadRow
                active={!isComposingNewThread && managerSessionId === summary.manager_session_id}
                key={summary.thread_id}
                onClick={() => openThread(summary)}
                summary={summary}
              />
            ))
          ) : (
            <div className="empty-inline small">Attach config 后，这里会显示当前正在继续的 manager threads。</div>
          )}
        </div>

        <div className="thread-list-shell">
          <div className="rail-section-header">
            <span>History</span>
            <span>{historyThreads.length}</span>
          </div>
          {historyThreads.length ? (
            historyThreads.map((summary) => (
              <ThreadRow
                active={!isComposingNewThread && managerSessionId === summary.manager_session_id}
                key={summary.thread_id}
                onClick={() => openThread(summary)}
                summary={summary}
              />
            ))
          ) : (
            <div className="empty-inline small">线程连续；这里仅收纳已结束或已归档的 manager threads。</div>
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
          <div className="rail-footer-block">
            <span>Lens</span>
            <strong>{mode}</strong>
          </div>
        </div>
      </aside>

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
