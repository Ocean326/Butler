import type { QueryObserverResult, RefetchOptions } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import type { ManageCenterDTO, SingleFlowPayload, TimelineEvent } from "../../../shared/dto";
import type { ConversationLens } from "../../state/atoms/ui";

type StreamSource = "supervisor" | "workflow" | "studio" | "recovery";
type EntryTone = "manager" | "activity" | "support";

interface ConversationEntry {
  id: string;
  tone: EntryTone;
  sourceLabel: string;
  title: string;
  summary: string;
  createdAt: string;
  chips: string[];
  details: string[];
  streamSource?: StreamSource;
}

interface StreamModel {
  source: StreamSource;
  label: string;
  intro: string;
  entries: ConversationEntry[];
}

interface StudioAssetModel {
  id: string;
  title: string;
  status: string;
}

interface ShellModel {
  title: string;
  subtitle: string;
  quickFacts: Array<{ label: string; value: string }>;
  entries: ConversationEntry[];
  streams: StreamModel[];
  latestArtifactRef: string;
  studioAssets: StudioAssetModel[];
}

interface WorkbenchShellProps {
  payload?: SingleFlowPayload;
  managePayload?: ManageCenterDTO;
  loading: boolean;
  lens: ConversationLens;
  actionDraft: string;
  selectedAssetId: string;
  onActionDraftChange: (value: string) => void;
  onSubmitComposer: () => void;
  onPause: () => void;
  onResume: () => void;
  onRetry: () => void;
  onRefresh: (options?: RefetchOptions) => Promise<QueryObserverResult<SingleFlowPayload, Error>>;
  onLensChange: (lens: ConversationLens) => void;
  onSelectAsset: (assetId: string) => void;
  onOpenArtifact: (target: string) => void;
}

function text(value: unknown, fallback = "—"): string {
  const raw = String(value ?? "").trim();
  return raw || fallback;
}

function maybeText(value: unknown): string {
  return String(value ?? "").trim();
}

function numberValue(value: unknown): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function record(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : {};
}

function records(value: unknown): Array<Record<string, unknown>> {
  return Array.isArray(value) ? value.filter((item) => item && typeof item === "object") as Array<Record<string, unknown>> : [];
}

function renderTime(value: unknown): string {
  const token = maybeText(value);
  if (!token) {
    return "pending";
  }
  return token.replace("T", " ").replace("Z", "");
}

function sortEntries(entries: ConversationEntry[]): ConversationEntry[] {
  return [...entries].sort((left, right) => {
    if (!left.createdAt && !right.createdAt) {
      return 0;
    }
    if (!left.createdAt) {
      return -1;
    }
    if (!right.createdAt) {
      return 1;
    }
    return left.createdAt.localeCompare(right.createdAt);
  });
}

function detailLines(lines: Array<unknown>): string[] {
  return lines
    .map((line) => maybeText(line))
    .filter(Boolean);
}

function timelineEntry(sourceLabel: string, streamSource: StreamSource, event: TimelineEvent): ConversationEntry {
  return {
    id: `${streamSource}-${event.event_id}`,
    tone: "activity",
    sourceLabel,
    title: text(event.title || event.kind, "Runtime event"),
    summary: text(event.message || event.title, "No message"),
    createdAt: maybeText(event.created_at),
    chips: detailLines([event.phase || "runtime", event.kind, event.family]),
    details: detailLines([event.raw_text]),
    streamSource,
  };
}

function studioAssetModel(managePayload?: ManageCenterDTO, selectedAssetId?: string): { assets: StudioAssetModel[]; active: Record<string, unknown> } {
  const items = records(managePayload?.assets.items).map((item, index) => ({
    id: maybeText(item.asset_id || item.id) || `asset-${index}`,
    title: text(item.title || item.name || item.asset_key, "Untitled contract"),
    status: text(item.status, "active"),
    raw: item,
  }));
  const active =
    items.find((item) => item.id === selectedAssetId)?.raw ||
    record(managePayload?.selected_asset) ||
    items[0]?.raw ||
    {};
  return {
    assets: items.map(({ id, title, status }) => ({ id, title, status })),
    active,
  };
}

function buildShellModel(payload: SingleFlowPayload | undefined, managePayload: ManageCenterDTO | undefined, selectedAssetId: string, lens: ConversationLens): ShellModel {
  const summary = record(payload?.navigator_summary || payload?.summary);
  const missionConsole = record(payload?.mission_console);
  const taskContractSummary = record(payload?.task_contract_summary || summary.task_contract_summary);
  const latestReceiptSummary = record(payload?.latest_receipt_summary || summary.latest_receipt_summary);
  const recoveryCursor = record(payload?.recovery_cursor);
  const governanceSummary = record(payload?.governance_summary);
  const guardCondition =
    maybeText(record(taskContractSummary.acceptance_summary).guard_condition) ||
    maybeText(summary.guard_condition);
  const goal = text(taskContractSummary.goal || missionConsole.goal || summary.goal, "Select a mission thread");
  const status = text(summary.effective_status, "idle");
  const phase = text(summary.effective_phase, "unstarted");
  const activeRole = text(summary.active_role_id, "manager");
  const receiptCount = numberValue(payload?.accepted_receipt_count ?? summary.accepted_receipt_count);
  const recoveryState = text(payload?.recovery_state || summary.recovery_state, "tracking");
  const latestArtifactRef = maybeText(payload?.latest_artifact_ref || summary.latest_artifact_ref);
  const latestReceiptLabel =
    maybeText(latestReceiptSummary.summary) ||
    maybeText(latestReceiptSummary.title) ||
    maybeText(latestReceiptSummary.receipt_kind) ||
    maybeText(latestReceiptSummary.receipt_id);
  const { assets: studioAssets, active: activeStudioAsset } = studioAssetModel(managePayload, selectedAssetId);
  const activeStudioDefinition = record(activeStudioAsset.definition);
  const activeStudioTaskSummary = record(activeStudioDefinition.task_contract_summary);

  const managerEntries: ConversationEntry[] = [
    {
      id: "manager-brief",
      tone: "manager",
      sourceLabel: "Manager",
      title: goal,
      summary:
        lens === "studio"
          ? "Manager is narrating the contract and guidance lens for this mission."
          : lens === "recovery"
            ? "Manager is narrating the current recovery lane and the next safe move."
            : "Manager is narrating current progress, accepted state, and the next delivery move.",
      createdAt: maybeText(summary.updated_at),
      chips: detailLines([status, phase, activeRole]),
      details: detailLines([
        guardCondition ? `Guard: ${guardCondition}` : "",
        latestReceiptLabel ? `Latest accepted receipt: ${latestReceiptLabel}` : "Latest accepted receipt: pending",
        `Accepted receipts: ${receiptCount || 0}`,
        latestArtifactRef ? `Latest artifact: ${latestArtifactRef}` : "",
        `Recovery state: ${recoveryState}`,
      ]),
    },
  ];

  if (lens === "mission") {
    managerEntries.push({
      id: "manager-progress",
      tone: "support",
      sourceLabel: "Manager",
      title: "Current checkpoint",
      summary: latestReceiptLabel || "The runtime is still building toward the next accepted checkpoint.",
      createdAt: maybeText(summary.updated_at),
      chips: detailLines([
        `Approval ${text(summary.approval_state, "not_required")}`,
        `Mode ${text(summary.execution_mode, "default")}`,
        `Sessions ${text(summary.session_strategy, "shared")}`,
      ]),
      details: detailLines([
        maybeText(record(governanceSummary.authority_summary).operator)
          ? `Operator: ${maybeText(record(governanceSummary.authority_summary).operator)}`
          : "",
        maybeText(record(governanceSummary.policy_summary).repo_binding_policy)
          ? `Repo binding: ${maybeText(record(governanceSummary.policy_summary).repo_binding_policy)}`
          : "",
      ]),
    });
  }

  if (lens === "studio") {
    const roleGuidance = record(managePayload?.role_guidance);
    const reviewChecklist = Array.isArray(managePayload?.review_checklist) ? managePayload?.review_checklist : [];
    managerEntries.push({
      id: "studio-focus",
      tone: "support",
      sourceLabel: "Studio",
      title: text(activeStudioAsset.title || activeStudioAsset.name || activeStudioAsset.asset_key, "Contract focus"),
      summary: text(activeStudioAsset.synopsis || activeStudioAsset.summary || managePayload?.manager_notes, "Contract guidance is ready."),
      createdAt: maybeText(summary.updated_at),
      chips: detailLines([text(activeStudioAsset.status, "active"), text(record(managePayload?.contract_studio).projection_kind, "contract_studio")]),
      details: detailLines([
        maybeText(managePayload?.manager_notes),
        ...Object.entries(roleGuidance)
          .slice(0, 3)
          .map(([key, value]) => `${key}: ${String(value)}`),
        ...reviewChecklist.slice(0, 3).map((item) => `Checklist: ${item}`),
      ]),
      streamSource: "studio",
    });
  }

  if (lens === "recovery") {
    managerEntries.push({
      id: "recovery-focus",
      tone: "support",
      sourceLabel: "Recovery",
      title: "Recovery lane",
      summary: `Runtime recovery is currently marked as ${recoveryState}.`,
      createdAt: maybeText(recoveryCursor.updated_at || summary.updated_at),
      chips: detailLines([
        maybeText(recoveryCursor.current_phase),
        maybeText(recoveryCursor.active_role_id),
        maybeText(recoveryCursor.recovery_state),
      ]),
      details: detailLines([
        maybeText(recoveryCursor.latest_accepted_receipt_id)
          ? `Latest accepted receipt id: ${maybeText(recoveryCursor.latest_accepted_receipt_id)}`
          : "",
        maybeText(recoveryCursor.codex_session_id) ? `Codex session: ${maybeText(recoveryCursor.codex_session_id)}` : "",
        maybeText(recoveryCursor.latest_artifact_ref) ? `Latest artifact: ${maybeText(recoveryCursor.latest_artifact_ref)}` : "",
      ]),
      streamSource: "recovery",
    });
  }

  const supervisorEntries = (payload?.supervisor_view?.events || []).map((event) => timelineEntry("Supervisor", "supervisor", event));
  const workflowEvents = payload?.workflow_view?.events || [];
  const workflowFallbackEntries =
    workflowEvents.length > 0
      ? workflowEvents.map((event) => timelineEntry("Team Runtime", "workflow", event))
      : records(payload?.flow_console?.step_history).map((step, index) => ({
          id: `workflow-step-${index}`,
          tone: "activity" as const,
          sourceLabel: "Team Runtime",
          title: text(step.summary || step.phase, "Workflow step"),
          summary: text(step.summary || step.phase, "Runtime checkpoint"),
          createdAt: maybeText(step.created_at),
          chips: detailLines([step.phase || "runtime"]),
          details: [],
          streamSource: "workflow" as const,
        }));

  const studioEntries =
    lens === "studio"
      ? [
          {
            id: "studio-manager-note",
            tone: "activity" as const,
            sourceLabel: "Studio",
            title: "Manager notes",
            summary: text(managePayload?.manager_notes, "No additional manager notes are attached to this studio context."),
            createdAt: maybeText(summary.updated_at),
            chips: detailLines([text(record(managePayload?.contract_studio).asset_kind, "asset"), text(record(managePayload?.contract_studio).projection_kind, "contract_studio")]),
            details: detailLines([
              maybeText(activeStudioTaskSummary.goal),
              maybeText(record(managePayload?.bundle_manifest).bundle_id)
                ? `Bundle: ${maybeText(record(managePayload?.bundle_manifest).bundle_id)}`
                : "",
            ]),
            streamSource: "studio" as const,
          },
        ]
      : [];

  const recoveryEntries =
    lens === "recovery"
      ? [
          {
            id: "recovery-next-step",
            tone: "activity" as const,
            sourceLabel: "Recovery",
            title: "Next safe move",
            summary:
              maybeText(recoveryCursor.recovery_state) === "resume_existing_session"
                ? "Resume the current bound session."
                : maybeText(recoveryCursor.latest_accepted_receipt_id)
                  ? `Resume from accepted receipt ${maybeText(recoveryCursor.latest_accepted_receipt_id)}.`
                  : "Collect a fresh checkpoint before resuming.",
            createdAt: maybeText(recoveryCursor.updated_at),
            chips: detailLines([maybeText(recoveryCursor.current_phase), maybeText(recoveryCursor.active_role_id)]),
            details: detailLines([
              maybeText(recoveryCursor.flow_id) ? `Flow: ${maybeText(recoveryCursor.flow_id)}` : "",
              maybeText(recoveryCursor.task_contract_id) ? `Task contract: ${maybeText(recoveryCursor.task_contract_id)}` : "",
            ]),
            streamSource: "recovery" as const,
          },
        ]
      : [];

  const activityEntries =
    lens === "studio"
      ? studioEntries
      : lens === "recovery"
        ? recoveryEntries
        : sortEntries([...supervisorEntries, ...workflowFallbackEntries]);

  const streams: StreamModel[] = [
    {
      source: "supervisor",
      label: "Supervisor stream",
      intro: "Full supervisor-facing execution narrative, including decisions and runtime prompts.",
      entries:
        supervisorEntries.length > 0
          ? supervisorEntries
          : [
              {
                id: "supervisor-empty",
                tone: "support",
                sourceLabel: "Supervisor",
                title: "No supervisor output yet",
                summary: "Once the team runtime emits a supervisor-facing decision or output, it will land here.",
                createdAt: "",
                chips: [],
                details: [],
              },
            ],
    },
    {
      source: "workflow",
      label: "Team runtime stream",
      intro: "Artifacts, handoffs, and workflow-side execution checkpoints.",
      entries:
        workflowFallbackEntries.length > 0
          ? workflowFallbackEntries
          : [
              {
                id: "workflow-empty",
                tone: "support",
                sourceLabel: "Team Runtime",
                title: "No workflow output yet",
                summary: "Accepted runtime events and artifacts will appear here.",
                createdAt: "",
                chips: [],
                details: [],
              },
            ],
    },
    {
      source: "studio",
      label: "Contract studio stream",
      intro: "Contract guidance, review checklist, and asset context that Manager can pull into the mission thread.",
      entries:
        studioEntries.length > 0
          ? studioEntries
          : [
              {
                id: "studio-empty",
                tone: "support",
                sourceLabel: "Studio",
                title: "Studio is quiet",
                summary: "Switch to the Studio lens to surface contract-specific notes and guidance.",
                createdAt: "",
                chips: [],
                details: [],
              },
            ],
    },
    {
      source: "recovery",
      label: "Recovery stream",
      intro: "Transcript-independent recovery cues derived from the canonical cursor and accepted state.",
      entries:
        recoveryEntries.length > 0
          ? recoveryEntries
          : [
              {
                id: "recovery-empty",
                tone: "support",
                sourceLabel: "Recovery",
                title: "Recovery looks steady",
                summary: `Current recovery state is ${recoveryState}. Open this stream when you need the exact recovery pointer.`,
                createdAt: "",
                chips: [],
                details: [],
              },
            ],
    },
  ];

  return {
    title: goal,
    subtitle:
      lens === "studio"
        ? "Contract lens active. Manager is surfacing asset guidance and contract edits inside the main thread."
        : lens === "recovery"
          ? "Recovery lens active. Manager is surfacing transcript-independent resume cues inside the same thread."
          : "Mission lens active. Manager is narrating accepted progress and delegating deeper agent output into drilldown streams.",
    quickFacts: [
      { label: "Status", value: status },
      { label: "Phase", value: phase },
      { label: "Active Role", value: activeRole },
      { label: "Accepted", value: String(receiptCount || 0) },
      { label: "Recovery", value: recoveryState },
      { label: "Latest Receipt", value: latestReceiptLabel || "pending" },
    ],
    entries: [...managerEntries, ...activityEntries],
    streams,
    latestArtifactRef,
    studioAssets,
  };
}

function MessageCard({
  entry,
  onOpenStream,
}: {
  entry: ConversationEntry;
  onOpenStream: (source: StreamSource) => void;
}) {
  return (
    <article className={`message-card message-card-${entry.tone}`}>
      <div className="message-card-head">
        <div className="message-card-source">
          <span className="message-source-label">{entry.sourceLabel}</span>
          {entry.streamSource ? (
            <button className="message-stream-link" onClick={() => onOpenStream(entry.streamSource!)} type="button">
              Open {entry.sourceLabel} stream
            </button>
          ) : null}
        </div>
        <span className="message-card-time">{renderTime(entry.createdAt)}</span>
      </div>
      <div className="message-card-body">
        <h3>{entry.title}</h3>
        <p>{entry.summary}</p>
        {entry.chips.length > 0 ? (
          <div className="message-chip-row">
            {entry.chips.map((chip) => (
              <span className="message-chip" key={chip}>
                {chip}
              </span>
            ))}
          </div>
        ) : null}
        {entry.details.length > 0 ? (
          <ul className="message-detail-list">
            {entry.details.map((detail) => (
              <li key={detail}>{detail}</li>
            ))}
          </ul>
        ) : null}
      </div>
    </article>
  );
}

function StreamSheet({
  stream,
  onClose,
  onOpenArtifact,
  latestArtifactRef,
}: {
  stream: StreamModel;
  onClose: () => void;
  onOpenArtifact: (target: string) => void;
  latestArtifactRef: string;
}) {
  return (
    <div className="stream-sheet-backdrop">
      <aside className="stream-sheet panel-shell">
        <header className="panel-header compact stream-sheet-header">
          <div>
            <p className="panel-kicker">Agent Drilldown</p>
            <h2>{stream.label}</h2>
            <p className="topbar-copy">{stream.intro}</p>
          </div>
          <button className="ui-button ui-button-secondary" onClick={onClose} type="button">
            Close
          </button>
        </header>
        <div className="stream-sheet-actions">
          <button className="ui-button ui-button-secondary" disabled={!latestArtifactRef} onClick={() => onOpenArtifact(latestArtifactRef)} type="button">
            Open Latest Artifact
          </button>
        </div>
        <div className="stream-sheet-body">
          {stream.entries.map((entry) => (
            <article className="stream-sheet-entry" key={entry.id}>
              <div className="stream-sheet-entry-head">
                <strong>{entry.title}</strong>
                <span>{renderTime(entry.createdAt)}</span>
              </div>
              <p>{entry.summary}</p>
              {entry.chips.length > 0 ? (
                <div className="message-chip-row">
                  {entry.chips.map((chip) => (
                    <span className="message-chip" key={chip}>
                      {chip}
                    </span>
                  ))}
                </div>
              ) : null}
              {entry.details.length > 0 ? (
                <pre className="runtime-pre">{entry.details.join("\n")}</pre>
              ) : null}
            </article>
          ))}
        </div>
      </aside>
    </div>
  );
}

export function WorkbenchShell({
  payload,
  managePayload,
  loading,
  lens,
  actionDraft,
  selectedAssetId,
  onActionDraftChange,
  onSubmitComposer,
  onPause,
  onResume,
  onRetry,
  onRefresh,
  onLensChange,
  onSelectAsset,
  onOpenArtifact,
}: WorkbenchShellProps) {
  const [openStreamSource, setOpenStreamSource] = useState<StreamSource | null>(null);
  const model = useMemo(() => buildShellModel(payload, managePayload, selectedAssetId, lens), [payload, managePayload, selectedAssetId, lens]);
  const summary = record(payload?.navigator_summary || payload?.summary);
  const status = text(summary.effective_status, "unknown");
  const canPause = status === "running";
  const canResume = status === "paused";
  const commandMode = actionDraft.trim().startsWith("/");
  const composerPlaceholder =
    lens === "studio"
      ? "Talk to Manager about the contract, acceptance, or guidance. Commands: /mission /recovery /open"
      : lens === "recovery"
        ? "Talk to Manager about resume, rollback, or pause. Commands: /resume /pause /mission"
        : "Talk to Manager about this mission. Commands: /pause /resume /studio /recovery /open";
  const activeStream = model.streams.find((stream) => stream.source === openStreamSource) || null;

  return (
    <div className="workbench-shell mission-thread-shell">
      <section className="panel-shell mission-header">
        <header className="mission-header-top">
          <div>
            <p className="panel-kicker">Manager Thread</p>
            <h2>{model.title}</h2>
            <p className="topbar-copy">{model.subtitle}</p>
          </div>
          <div className="mission-header-actions">
            <div className="lens-switcher" aria-label="Conversation Lens">
              {([
                ["mission", "Mission"],
                ["studio", "Studio"],
                ["recovery", "Recovery"],
              ] as Array<[ConversationLens, string]>).map(([nextLens, label]) => (
                <button
                  key={nextLens}
                  className={`lens-chip ${lens === nextLens ? "is-active" : ""}`}
                  onClick={() => onLensChange(nextLens)}
                  type="button"
                >
                  {label}
                </button>
              ))}
            </div>
            <div className="topbar-actions">
              <button className="ui-button ui-button-secondary" onClick={() => void onRefresh()} type="button">
                Refresh
              </button>
              <button className="ui-button ui-button-secondary" disabled={!model.latestArtifactRef} onClick={() => onOpenArtifact(model.latestArtifactRef)} type="button">
                Open Artifact
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
          </div>
        </header>

        <div className="mission-meta-strip">
          {model.quickFacts.map((fact) => (
            <div className="mission-meta-tile" key={`${fact.label}-${fact.value}`}>
              <span>{fact.label}</span>
              <strong>{fact.value}</strong>
            </div>
          ))}
        </div>

        {lens === "studio" && model.studioAssets.length > 0 ? (
          <div className="studio-asset-strip">
            {model.studioAssets.map((asset) => (
              <button
                key={asset.id}
                className={`studio-asset-pill ${asset.id === selectedAssetId ? "is-active" : ""}`}
                onClick={() => onSelectAsset(asset.id)}
                type="button"
              >
                <span>{asset.status}</span>
                <strong>{asset.title}</strong>
              </button>
            ))}
          </div>
        ) : null}
      </section>

      {loading ? <div className="empty-panel shell-loading">Loading manager thread…</div> : null}

      {!loading && !payload ? (
        <section className="panel-shell thread-empty">
          <header className="panel-header compact">
            <div>
              <p className="panel-kicker">No Thread Selected</p>
              <h2>Pick a mission thread from the left rail</h2>
            </div>
          </header>
          <div className="empty-panel">Manager will start narrating as soon as a mission thread is selected.</div>
        </section>
      ) : null}

      {payload ? (
        <>
          <section className="panel-shell conversation-panel">
            <div className="conversation-scroll">
              {model.entries.map((entry) => (
                <MessageCard entry={entry} key={entry.id} onOpenStream={setOpenStreamSource} />
              ))}
            </div>
          </section>

          <form
            className="panel-shell composer-shell"
            onSubmit={(event) => {
              event.preventDefault();
              onSubmitComposer();
            }}
          >
            <div className="composer-head">
              <p className="panel-kicker">Manager Composer</p>
              <div className="composer-shortcuts">
                {["/pause", "/resume", "/studio", "/recovery", "/open"].map((shortcut) => (
                  <button
                    key={shortcut}
                    className="shortcut-pill"
                    onClick={() => onActionDraftChange(shortcut)}
                    type="button"
                  >
                    {shortcut}
                  </button>
                ))}
              </div>
            </div>
            <div className="composer-body">
              <textarea
                className="composer-textarea"
                placeholder={composerPlaceholder}
                rows={3}
                value={actionDraft}
                onChange={(event) => onActionDraftChange(event.target.value)}
              />
              <button className="ui-button ui-button-primary composer-submit" disabled={!actionDraft.trim()} type="submit">
                {commandMode ? "Run Command" : "Message Manager"}
              </button>
            </div>
          </form>
        </>
      ) : null}

      {activeStream ? (
        <StreamSheet
          latestArtifactRef={model.latestArtifactRef}
          onClose={() => setOpenStreamSource(null)}
          onOpenArtifact={onOpenArtifact}
          stream={activeStream}
        />
      ) : null}
    </div>
  );
}
