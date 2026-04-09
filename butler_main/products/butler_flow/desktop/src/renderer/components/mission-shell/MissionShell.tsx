import type { FormEvent, KeyboardEvent, ReactNode, RefObject } from "react";
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
  X
} from "lucide-react";
import type {
  AgentFocusDTO,
  SupervisorThreadDTO,
  TemplateTeamDTO,
  ThreadBlockDTO,
  ThreadHomeDTO,
  ThreadSummaryDTO
} from "../../../shared/dto";
import {
  blockMeta,
  compactPathLabel,
  formatValue,
  narratorLens,
  shortTime,
  type ConversationMode
} from "../../lib/mission-shell";

export type MissionStatusTone = "info" | "danger";

interface EmptyAttachStateProps {
  manualConfigPath: string;
  onManualConfigChange: (value: string) => void;
  onManualConfigKeyDown: (event: KeyboardEvent<HTMLInputElement>) => void;
  onChooseConfig: () => void;
  onAttachPath: () => void;
}

export function EmptyAttachState({
  manualConfigPath,
  onManualConfigChange,
  onManualConfigKeyDown,
  onChooseConfig,
  onAttachPath
}: EmptyAttachStateProps) {
  return (
    <section className="empty-state-shell">
      <div className="empty-state-card">
        <div className="empty-state-badge">
          <Sparkles size={16} />
          <span>Butler Desktop</span>
        </div>
        <h2>先连接 Butler config</h2>
        <p>连接后，Desktop 会把 live manager threads、runtime signals 和 studio context 收进同一个简洁的 mission shell。</p>
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
            <button
              className="ui-button ui-button-secondary"
              disabled={!manualConfigPath.trim()}
              onClick={onAttachPath}
              type="button"
            >
              Attach Path
            </button>
          </div>
        </div>
      </div>
    </section>
  );
}

export function BridgeMissingState() {
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
    <button
      aria-current={active ? "page" : undefined}
      className={`thread-row ${active ? "is-active" : ""}`}
      onClick={onClick}
      type="button"
    >
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

function ThreadSection({
  title,
  count,
  rows,
  activeManagerSessionId,
  isComposingNewThread,
  emptyText,
  onOpenThread
}: {
  title: string;
  count: number;
  rows: ThreadSummaryDTO[];
  activeManagerSessionId: string;
  isComposingNewThread: boolean;
  emptyText: string;
  onOpenThread: (summary: ThreadSummaryDTO) => void;
}) {
  return (
    <section className="thread-section">
      <div className="rail-section-header">
        <span>{title}</span>
        <span>{count}</span>
      </div>
      <div className="thread-section-body">
        {rows.length ? (
          rows.map((summary) => (
            <ThreadRow
              active={!isComposingNewThread && activeManagerSessionId === summary.manager_session_id}
              key={summary.thread_id}
              onClick={() => onOpenThread(summary)}
              summary={summary}
            />
          ))
        ) : (
          <div className="empty-inline small">{emptyText}</div>
        )}
      </div>
    </section>
  );
}

interface DesktopRailProps {
  bridgeAvailable: boolean;
  configPath: string;
  workspaceRoot: string;
  theme: "day" | "night";
  mode: ConversationMode;
  activeThreads: ThreadSummaryDTO[];
  historyThreads: ThreadSummaryDTO[];
  managerSessionId: string;
  isComposingNewThread: boolean;
  currentFlowId: string;
  templateCount: number;
  homeLoading: boolean;
  home?: ThreadHomeDTO;
  onOpenNewThread: () => void;
  onOpenThread: (summary: ThreadSummaryDTO) => void;
}

export function DesktopRail({
  bridgeAvailable,
  configPath,
  workspaceRoot,
  theme,
  mode,
  activeThreads,
  historyThreads,
  managerSessionId,
  isComposingNewThread,
  currentFlowId,
  templateCount,
  homeLoading,
  home,
  onOpenNewThread,
  onOpenThread
}: DesktopRailProps) {
  const totalSessions = Number(home?.manager_entry.total_sessions || activeThreads.length + historyThreads.length || 0);

  return (
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

      <section className="rail-stack-card">
        <span className="rail-card-label">Mission control</span>
        <strong className="rail-card-title">简洁桌面壳，单主对话</strong>
        <div className="rail-context-value" title={configPath || workspaceRoot || "Select a Butler config"}>
          {compactPathLabel(configPath || workspaceRoot, "Select a Butler config")}
        </div>
        <div className="rail-summary-grid">
          <div className="rail-summary-item">
            <span>Bridge</span>
            <strong>{bridgeAvailable ? "Connected" : "Browser only"}</strong>
          </div>
          <div className="rail-summary-item">
            <span>Lens</span>
            <strong>{mode}</strong>
          </div>
          <div className="rail-summary-item">
            <span>Theme</span>
            <strong>{theme === "night" ? "Night" : "Day"}</strong>
          </div>
          <div className="rail-summary-item">
            <span>Threads</span>
            <strong>{totalSessions}</strong>
          </div>
        </div>
      </section>

      <button className="launch-thread-button" onClick={onOpenNewThread} type="button">
        <PlusSquare size={16} />
        <span>New thread</span>
      </button>

      {homeLoading ? <div className="empty-inline small">Syncing desktop threads…</div> : null}

      <div className="thread-list-shell">
        <ThreadSection
          activeManagerSessionId={managerSessionId}
          count={activeThreads.length}
          emptyText="Attach config 后，这里会显示当前正在继续的 manager threads。"
          isComposingNewThread={isComposingNewThread}
          onOpenThread={onOpenThread}
          rows={activeThreads}
          title="Active"
        />

        <ThreadSection
          activeManagerSessionId={managerSessionId}
          count={historyThreads.length}
          emptyText="线程连续；这里仅收纳已结束或已归档的 manager threads。"
          isComposingNewThread={isComposingNewThread}
          onOpenThread={onOpenThread}
          rows={historyThreads}
          title="History"
        />
      </div>

      <section className="rail-stack-card rail-footer-card">
        <div className="rail-summary-item">
          <span>Workspace</span>
          <strong title={workspaceRoot || configPath}>{compactPathLabel(workspaceRoot || configPath, "Pending attach")}</strong>
        </div>
        <div className="rail-summary-item">
          <span>Live flow</span>
          <strong>{currentFlowId || "Pending launch"}</strong>
        </div>
        <div className="rail-summary-item">
          <span>Templates</span>
          <strong>{templateCount}</strong>
        </div>
      </section>
    </aside>
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
    <button
      aria-pressed={active}
      className={`mode-button ${active ? "is-active" : ""}`}
      disabled={disabled}
      onClick={onClick}
      type="button"
    >
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
  const selectedLabel = formatValue(payload?.selected_asset.label || payload?.thread.title || "Contract Studio");

  return (
    <section className="context-strip">
      <div className="context-strip-copy">
        <span className="context-strip-kicker">Studio Lens</span>
        <strong>{selectedLabel || "Contract Studio"}</strong>
        <p>{payload?.manager_notes || "通过 Studio 语境收口 contract、team guidance 和 review checklist。"}</p>
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

interface MissionShellProps {
  theme: "day" | "night";
  mode: ConversationMode;
  currentTitle: string;
  currentSubtitle: string;
  currentThreadStatus: string;
  isComposingNewThread: boolean;
  runtimeAvailable: boolean;
  studioAvailable: boolean;
  canPause: boolean;
  canResume: boolean;
  linkedFlowId: string;
  runtimePhase: string;
  activeRole: string;
  managerStage: string;
  templateCount: number;
  surfaceBusy: boolean;
  statusMessage: string;
  statusTone: MissionStatusTone;
  composerRef: RefObject<HTMLTextAreaElement>;
  managerBlocks: ThreadBlockDTO[];
  runtimeBlocks: ThreadBlockDTO[];
  studioBlocks: ThreadBlockDTO[];
  supervisorPayload?: SupervisorThreadDTO;
  templatePayload?: TemplateTeamDTO;
  messageDraft: string;
  sendingManagerMessage: boolean;
  composerLabel: string;
  composerPlaceholder: string;
  currentBlockExpanded: (block: ThreadBlockDTO) => boolean;
  onToggleBlock: (blockId: string) => void;
  onActionTarget: (target: string) => void;
  onRoleSelect: (roleId: string) => void;
  onSelectAsset: (assetId: string) => void;
  onModeChange: (mode: ConversationMode) => void;
  onMessageDraftChange: (value: string) => void;
  onSendMessage: (event: FormEvent<HTMLFormElement>) => void;
  onPause: () => void;
  onResume: () => void;
  onRefresh: () => void;
  onChooseConfig: () => void;
  onSwitchTheme: () => void;
}

export function MissionShell({
  theme,
  mode,
  currentTitle,
  currentSubtitle,
  currentThreadStatus,
  isComposingNewThread,
  runtimeAvailable,
  studioAvailable,
  canPause,
  canResume,
  linkedFlowId,
  runtimePhase,
  activeRole,
  managerStage,
  templateCount,
  surfaceBusy,
  statusMessage,
  statusTone,
  composerRef,
  managerBlocks,
  runtimeBlocks,
  studioBlocks,
  supervisorPayload,
  templatePayload,
  messageDraft,
  sendingManagerMessage,
  composerLabel,
  composerPlaceholder,
  currentBlockExpanded,
  onToggleBlock,
  onActionTarget,
  onRoleSelect,
  onSelectAsset,
  onModeChange,
  onMessageDraftChange,
  onSendMessage,
  onPause,
  onResume,
  onRefresh,
  onChooseConfig,
  onSwitchTheme
}: MissionShellProps) {
  return (
    <section className="conversation-shell">
      <header className="mission-header-card">
        <div className="mission-header">
          <div className="mission-header-main">
            <span className="mission-kicker">Manager thread</span>
            <div className="mission-title-row">
              <h1>{currentTitle}</h1>
              <div className="mission-status-row">
                <StatusChip>{mode}</StatusChip>
                <StatusChip>{currentThreadStatus}</StatusChip>
                {runtimeAvailable ? <StatusChip>{runtimePhase || "runtime ready"}</StatusChip> : null}
                {runtimeAvailable ? <StatusChip>{activeRole || "manager"}</StatusChip> : null}
              </div>
            </div>
            <p>{currentSubtitle}</p>
          </div>

          <div className="mission-header-aside">
            <div className="mode-switcher" role="tablist" aria-label="Conversation modes">
              <ModeButton active={mode === "mission"} label="Mission" onClick={() => onModeChange("mission")} />
              <ModeButton
                active={mode === "runtime"}
                disabled={!runtimeAvailable}
                label="Runtime"
                onClick={() => onModeChange("runtime")}
              />
              <ModeButton
                active={mode === "studio"}
                disabled={!studioAvailable}
                label="Studio"
                onClick={() => onModeChange("studio")}
              />
            </div>

            <div className="header-actions">
              <button className="ui-button ui-button-secondary" disabled={!canPause} onClick={onPause} type="button">
                <PauseCircle size={16} />
                Pause
              </button>
              <button className="ui-button ui-button-secondary" disabled={!canResume} onClick={onResume} type="button">
                <PlayCircle size={16} />
                Resume
              </button>
              <button className="ui-button ui-button-secondary" onClick={onRefresh} type="button">
                <RefreshCcw size={16} />
                Refresh
              </button>
              <button className="ui-button ui-button-secondary" onClick={onChooseConfig} type="button">
                <FolderSearch size={16} />
                Config
              </button>
              <button className="ui-button ui-button-secondary" onClick={onSwitchTheme} type="button">
                {theme === "day" ? <Moon size={16} /> : <SunMedium size={16} />}
                {theme === "day" ? "Night" : "Day"}
              </button>
            </div>
          </div>
        </div>

        <div className="surface-snapshot-grid">
          <div className="snapshot-card">
            <span>Thread state</span>
            <strong>{currentThreadStatus}</strong>
            <p>{isComposingNewThread ? "Draft thread waiting for the first manager prompt." : `Manager stage · ${managerStage || "mission"}`}</p>
          </div>
          <div className="snapshot-card">
            <span>Runtime</span>
            <strong>{linkedFlowId || "Pending launch"}</strong>
            <p>{runtimeAvailable ? `Active role · ${activeRole || "manager"}` : "Runtime stays inside the same conversation after launch."}</p>
          </div>
          <div className="snapshot-card">
            <span>Studio</span>
            <strong>{templateCount}</strong>
            <p>{studioAvailable ? "Contract and guidance stay inside the mission shell." : "No template context has been attached yet."}</p>
          </div>
        </div>
      </header>

      {statusMessage ? (
        <div aria-live="polite" className={`status-banner is-${statusTone}`}>
          {statusMessage}
        </div>
      ) : null}

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

          {surfaceBusy ? <div className="conversation-state-card">Syncing desktop surface…</div> : null}

          <div className="message-column">
            {managerBlocks.map((block) => (
              <NarratorMessage
                block={block}
                defaultLens="mission"
                expanded={currentBlockExpanded(block)}
                key={block.block_id}
                onActionTarget={onActionTarget}
                onToggle={() => onToggleBlock(block.block_id)}
              />
            ))}

            {mode === "runtime" ? (
              <>
                <RuntimeStrip payload={supervisorPayload} onRoleSelect={onRoleSelect} />
                {runtimeBlocks.length ? (
                  runtimeBlocks.map((block) => (
                    <NarratorMessage
                      block={block}
                      defaultLens="runtime"
                      expanded={currentBlockExpanded(block)}
                      key={block.block_id}
                      onActionTarget={onActionTarget}
                      onToggle={() => onToggleBlock(block.block_id)}
                    />
                  ))
                ) : (
                  <div className="empty-inline">
                    当前还没有新的 runtime 细流，等下一次 accepted progress 或 operator action 进入后会显示在这里。
                  </div>
                )}
              </>
            ) : null}

            {mode === "studio" ? (
              <>
                <StudioStrip payload={templatePayload} onSelectAsset={onSelectAsset} />
                {studioBlocks.length ? (
                  studioBlocks.map((block) => (
                    <NarratorMessage
                      block={block}
                      defaultLens="studio"
                      expanded={currentBlockExpanded(block)}
                      key={block.block_id}
                      onActionTarget={onActionTarget}
                      onToggle={() => onToggleBlock(block.block_id)}
                    />
                  ))
                ) : (
                  <div className="empty-inline">
                    Studio 目前还没有额外块；进入后会优先展示 contract、role guidance 和 checklist 摘要。
                  </div>
                )}
              </>
            ) : null}
          </div>
        </div>

        <form className="composer-shell mission-composer" onSubmit={onSendMessage}>
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

          <label htmlFor="manager-composer">{composerLabel}</label>

          <div className="composer-row">
            <textarea
              id="manager-composer"
              ref={composerRef}
              className="composer-textarea"
              placeholder={composerPlaceholder}
              value={messageDraft}
              onChange={(event) => onMessageDraftChange(event.target.value)}
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

interface AgentDetailSheetProps {
  payload?: AgentFocusDTO;
  open: boolean;
  expandedBlocks: Record<string, boolean>;
  onToggle: (blockId: string) => void;
  onActionTarget: (target: string) => void;
  onClose: () => void;
}

export function AgentDetailSheet({
  payload,
  open,
  expandedBlocks,
  onToggle,
  onActionTarget,
  onClose
}: AgentDetailSheetProps) {
  if (!open) {
    return null;
  }

  return (
    <>
      <button aria-hidden className="detail-sheet-backdrop" onClick={onClose} tabIndex={-1} type="button" />
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
    </>
  );
}
