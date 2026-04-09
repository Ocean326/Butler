import type { FormEvent, KeyboardEvent, RefObject } from "react";
import { AlertCircle, FolderSearch, MessageSquareText, Moon, PlusSquare, Send, Sparkles, SunMedium } from "lucide-react";
import type { ThreadHomeDTO, ThreadSummaryDTO } from "../../../shared/dto";
import { compactPathLabel, shortTime, type ShellMessage } from "../../lib/mission-shell";

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
        <p>连接后，这个桌面壳会先只保留左侧 thread rail 和右侧 Manager conversation。</p>
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
        <p>当前页面没有注入 `window.butlerDesktop`，所以无法读取真实 thread history，也不能发送 manager message。</p>
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
        <span className="thread-row-time">{shortTime(summary.updated_at || summary.created_at)}</span>
        <span className="thread-row-kicker">{summary.status || "thread"}</span>
      </div>
      <strong className="thread-row-title">{summary.title || "Untitled Manager Thread"}</strong>
      <span className="thread-row-subtitle">{summary.subtitle || "Continue with Manager"}</span>
    </button>
  );
}

interface DesktopRailProps {
  bridgeAvailable: boolean;
  configPath: string;
  workspaceRoot: string;
  theme: "day" | "night";
  threadRows: ThreadSummaryDTO[];
  activeManagerSessionId: string;
  isComposingNewThread: boolean;
  homeLoading: boolean;
  home?: ThreadHomeDTO;
  onOpenNewThread: () => void;
  onOpenThread: (summary: ThreadSummaryDTO) => void;
  onSwitchTheme: () => void;
}

export function DesktopRail({
  bridgeAvailable,
  configPath,
  workspaceRoot,
  theme,
  threadRows,
  activeManagerSessionId,
  isComposingNewThread,
  homeLoading,
  home,
  onOpenNewThread,
  onOpenThread,
  onSwitchTheme
}: DesktopRailProps) {
  return (
    <aside className="desktop-rail">
      <div className="rail-brand">
        <div className="rail-brand-copy">
          <span className="rail-brand-kicker">SuperButler</span>
          <strong>Butler Desktop</strong>
          <span>Manager conversation shell</span>
        </div>
        <button
          aria-label={theme === "day" ? "Switch to night mode" : "Switch to day mode"}
          className="theme-button"
          onClick={onSwitchTheme}
          type="button"
        >
          {theme === "day" ? <Moon size={15} /> : <SunMedium size={15} />}
        </button>
      </div>

      <button className="launch-thread-button" onClick={onOpenNewThread} type="button">
        <PlusSquare size={16} />
        <span>New thread</span>
      </button>

      <section className="rail-section">
        <div className="rail-section-header">
          <span>History</span>
          <span>{threadRows.length || Number(home?.manager_entry.total_sessions || 0)}</span>
        </div>
        {homeLoading ? <div className="empty-inline small">Syncing threads…</div> : null}
        <div className="thread-list-shell">
          {threadRows.length ? (
            threadRows.map((summary) => (
              <ThreadRow
                active={!isComposingNewThread && activeManagerSessionId === summary.manager_session_id}
                key={summary.thread_id}
                onClick={() => onOpenThread(summary)}
                summary={summary}
              />
            ))
          ) : (
            <div className="empty-inline small">Attach config 后，这里会显示 Manager threads 的真实历史卡片。</div>
          )}
        </div>
      </section>

      <div className="rail-footer">
        <div className="rail-footer-row">
          <span>Bridge</span>
          <strong>{bridgeAvailable ? "Connected" : "Browser only"}</strong>
        </div>
        <div className="rail-footer-row">
          <span>Config</span>
          <strong title={configPath || workspaceRoot}>{compactPathLabel(configPath || workspaceRoot, "Pending attach")}</strong>
        </div>
      </div>
    </aside>
  );
}

function ConversationMessage({ message }: { message: ShellMessage }) {
  return (
    <article className={`conversation-message is-${message.role} is-${message.status || "ready"}`}>
      <div className="conversation-message-meta">
        <span className="conversation-message-role">{message.role === "manager" ? "Manager" : "You"}</span>
        <span>{message.meta}</span>
        <span>{shortTime(message.createdAt)}</span>
      </div>
      {message.title ? <h3>{message.title}</h3> : null}
      <p>{message.body || (message.status === "streaming" ? "…" : "")}</p>
    </article>
  );
}

interface MissionShellProps {
  currentTitle: string;
  currentSubtitle: string;
  currentThreadStatus: string;
  conversationMessages: ShellMessage[];
  surfaceBusy: boolean;
  statusMessage: string;
  statusTone: MissionStatusTone;
  composerRef: RefObject<HTMLTextAreaElement>;
  messageDraft: string;
  sendingManagerMessage: boolean;
  composerLabel: string;
  composerPlaceholder: string;
  onMessageDraftChange: (value: string) => void;
  onSendMessage: (event: FormEvent<HTMLFormElement>) => void;
}

export function MissionShell({
  currentTitle,
  currentSubtitle,
  currentThreadStatus,
  conversationMessages,
  surfaceBusy,
  statusMessage,
  statusTone,
  composerRef,
  messageDraft,
  sendingManagerMessage,
  composerLabel,
  composerPlaceholder,
  onMessageDraftChange,
  onSendMessage
}: MissionShellProps) {
  return (
    <section className="conversation-shell">
      <header className="mission-header-card">
        <div className="mission-header-main">
          <span className="mission-kicker">Manager conversation</span>
          <div className="mission-title-row">
            <h1>{currentTitle}</h1>
            <span className="status-chip">{currentThreadStatus || "active"}</span>
          </div>
          <p>{currentSubtitle}</p>
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
              <MessageSquareText size={16} />
            </div>
            <div>
              <strong>Manager only</strong>
              <p>这轮先只保留 Manager 主对话和真实历史，不让其他模块干扰第一层骨架。</p>
            </div>
          </div>

          {surfaceBusy ? <div className="conversation-state-card">Syncing manager thread…</div> : null}

          <div className="message-column">
            {conversationMessages.length ? (
              conversationMessages.map((message) => <ConversationMessage key={message.id} message={message} />)
            ) : (
              <div className="conversation-state-card">从这里开始，先把你的目标直接交给 Manager。</div>
            )}
          </div>
        </div>

        <form className="composer-shell mission-composer" onSubmit={onSendMessage}>
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
            <span className="composer-hint">右侧现在只服务和 Manager 的持续对话，后续能力再增量接回。</span>
            <button className="ui-button ui-button-primary" disabled={!messageDraft.trim() || sendingManagerMessage} type="submit">
              <Send size={16} />
              {sendingManagerMessage ? "Streaming..." : "Send to Manager"}
            </button>
          </div>
        </form>
      </div>
    </section>
  );
}
