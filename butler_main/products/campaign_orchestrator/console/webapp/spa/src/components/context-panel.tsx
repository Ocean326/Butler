import { useEffect, useState, useTransition } from "react";

import type {
  AccessDiagnostics,
  AgentExecutionView,
  ArtifactListItem,
  AuditActionRecord,
  ChannelThreadSummary,
  ContextTab,
  ControlPlaneEnvelope,
  PromptSurfaceEnvelope,
  RecordListItem,
  RuntimeStatus,
  WorkflowAuthoringEnvelope
} from "../types";
import { formatDate, humanize, shortText, statusTone } from "../lib/format";
import { StatusPill } from "./status-pill";

interface ContextPanelProps {
  tab: ContextTab;
  onChangeTab: (tab: ContextTab) => void;
  artifacts: ArtifactListItem[];
  records: RecordListItem[];
  runtime?: RuntimeStatus;
  access?: AccessDiagnostics;
  currentAgent?: AgentExecutionView | null;
  nextAgent?: AgentExecutionView | null;
  channel?: ChannelThreadSummary;
  selectedArtifactId: string;
  selectedRecordId: string;
  selectedNodeId: string;
  controlPlane?: ControlPlaneEnvelope;
  auditActions: AuditActionRecord[];
  promptSurface?: PromptSurfaceEnvelope;
  workflowAuthoring?: WorkflowAuthoringEnvelope;
  onSelectArtifact: (artifactId: string) => void;
  onSelectRecord: (recordId: string) => void;
  onApplyAction: (action: string, patch?: Record<string, unknown>) => Promise<void> | void;
  onApplyPromptPatch: (patch: Record<string, unknown>) => Promise<void> | void;
  onApplyWorkflowPatch: (patch: Record<string, unknown>) => Promise<void> | void;
}

export function ContextPanel(props: ContextPanelProps) {
  const {
    tab,
    onChangeTab,
    artifacts,
    records,
    runtime,
    access,
    currentAgent,
    nextAgent,
    channel,
    selectedArtifactId,
    selectedRecordId,
    selectedNodeId,
    controlPlane,
    auditActions,
    promptSurface,
    workflowAuthoring,
    onSelectArtifact,
    onSelectRecord,
    onApplyAction,
    onApplyPromptPatch,
    onApplyWorkflowPatch
  } = props;
  const [isPending, startTransition] = useTransition();
  const [operatorReason, setOperatorReason] = useState("");
  const [feedbackText, setFeedbackText] = useState("");
  const [collectionId, setCollectionId] = useState("");
  const [familyHints, setFamilyHints] = useState("");
  const [riskLevel, setRiskLevel] = useState("");
  const [autonomyProfile, setAutonomyProfile] = useState("");
  const [nodeOverlay, setNodeOverlay] = useState("");
  const [phasePlan, setPhasePlan] = useState("");
  const [rolePlan, setRolePlan] = useState("");
  const [operatorNotice, setOperatorNotice] = useState("");

  useEffect(() => {
    const structured = (promptSurface?.structured_contract || {}) as Record<string, unknown>;
    const skillExposure = (structured.skill_exposure || {}) as Record<string, unknown>;
    const governance = (structured.governance_contract || {}) as Record<string, unknown>;
    const nodeOverlayPayload = (structured.node_overlay || {}) as Record<string, unknown>;
    setCollectionId(String(skillExposure.collection_id || ""));
    setFamilyHints(((skillExposure.family_hints as string[] | undefined) || []).join("\n"));
    setRiskLevel(String(governance.risk_level || controlPlane?.risk_level || ""));
    setAutonomyProfile(String(governance.autonomy_profile || controlPlane?.autonomy_profile || ""));
    setNodeOverlay(nodeOverlayPayload && Object.keys(nodeOverlayPayload).length ? JSON.stringify(nodeOverlayPayload, null, 2) : "");
  }, [controlPlane?.autonomy_profile, controlPlane?.risk_level, promptSurface]);

  useEffect(() => {
    setPhasePlan(((workflowAuthoring?.phase_plan || []) as string[]).join("\n"));
    setRolePlan(((workflowAuthoring?.role_plan || []) as string[]).join("\n"));
  }, [workflowAuthoring]);

  const transitionOptions = (controlPlane?.transition_options || []) as AuditActionRecord[];
  const recoveryCandidates = (controlPlane?.recovery_candidates || []) as AuditActionRecord[];
  const availableActions = new Set((controlPlane?.available_actions || []) as string[]);
  const visiblePrimaryActions = ["pause", "resume", "abort", "annotate_governance", "force_recover_from_snapshot"]
    .filter((action) => !availableActions.size || availableActions.has(action));
  const harnessSummary = (controlPlane?.harness_summary || {}) as Record<string, unknown>;

  const applyAction = (action: string, patch: Record<string, unknown> = {}) => {
    startTransition(() => {
      void (async () => {
        try {
          await onApplyAction(action, {
            operator_reason: operatorReason,
            reason: operatorReason,
            target_node_id: selectedNodeId,
            ...patch
          });
          setOperatorNotice(`${humanize(action)} applied.`);
          if (action === "append_feedback") {
            setFeedbackText("");
          }
        } catch (error) {
          setOperatorNotice(error instanceof Error ? error.message : `${humanize(action)} failed.`);
        }
      })();
    });
  };

  const savePromptSurface = () => {
    const promptPatch = buildPromptPatch({
      collectionId,
      familyHints,
      riskLevel,
      autonomyProfile,
      operatorReason,
      nodeOverlay,
      setOperatorNotice
    });
    if (!promptPatch) {
      return;
    }
    startTransition(() => {
      void (async () => {
        try {
          await onApplyPromptPatch(promptPatch);
          setOperatorNotice("Prompt surface updated.");
        } catch (error) {
          setOperatorNotice(error instanceof Error ? error.message : "Prompt surface update failed.");
        }
      })();
    });
  };

  const saveWorkflowPatch = () => {
    startTransition(() => {
      void (async () => {
        try {
          await onApplyWorkflowPatch({
            phase_plan: splitLines(phasePlan),
            role_plan: splitLines(rolePlan),
            operator_reason: operatorReason
          });
          setOperatorNotice("Workflow patch updated.");
        } catch (error) {
          setOperatorNotice(error instanceof Error ? error.message : "Workflow patch update failed.");
        }
      })();
    });
  };

  return (
    <aside className="context-panel">
      <div className="tab-row">
        {(["artifacts", "records", "runtime", "operator"] as ContextTab[]).map((item) => (
          <button key={item} className={tab === item ? "is-active" : ""} onClick={() => onChangeTab(item)}>
            {humanize(item)}
          </button>
        ))}
      </div>
      {tab === "artifacts" && (
        <div className="panel-list">
          {artifacts.map((artifact) => (
            <button
              key={artifact.artifact_id}
              className={`list-card ${selectedArtifactId === artifact.artifact_id ? "is-active" : ""}`}
              onClick={() => onSelectArtifact(artifact.artifact_id)}
            >
              <strong>{artifact.label}</strong>
              <p>{shortText(artifact.ref || artifact.kind || "Artifact", 64)}</p>
              <span className="micro-meta">{artifact.created_at || "No timestamp"}</span>
            </button>
          ))}
          {!artifacts.length && <div className="empty-block">No artifacts yet.</div>}
        </div>
      )}
      {tab === "records" && (
        <div className="panel-list">
          {records.map((record) => (
            <button
              key={record.record_id}
              className={`list-card ${selectedRecordId === record.record_id ? "is-active" : ""}`}
              onClick={() => onSelectRecord(record.record_id)}
            >
              <strong>{record.title}</strong>
              <p>{shortText(record.summary || record.kind || "Record", 84)}</p>
              <span className="micro-meta">{record.created_at || "No timestamp"}</span>
            </button>
          ))}
          {!records.length && <div className="empty-block">No records yet.</div>}
        </div>
      )}
      {tab === "runtime" && (
        <div className="runtime-cards">
          <section className="data-card">
            <header className="panel-header">
              <h3>Runtime</h3>
              <StatusPill label={humanize(runtime?.process_state as string) || "Unknown"} tone={statusTone(runtime?.process_state as string)} />
            </header>
            <dl>
              <div>
                <dt>Macro state</dt>
                <dd>{humanize(controlPlane?.macro_state || currentAgent?.status || runtime?.phase as string) || "Unknown"}</dd>
              </div>
              <div>
                <dt>Updated</dt>
                <dd>{formatDate(runtime?.updated_at as string)}</dd>
              </div>
              <div>
                <dt>Session</dt>
                <dd>{shortText(String(controlPlane?.canonical_session_id || "Unavailable"), 28)}</dd>
              </div>
            </dl>
            <p>{shortText(controlPlane?.narrative_summary || runtime?.note as string, 160) || "No runtime note."}</p>
          </section>
          <section className="data-card">
            <header className="panel-header">
              <h3>Supervisor loop</h3>
            </header>
            <dl>
              <div>
                <dt>Current</dt>
                <dd>{currentAgent?.title || "None"}</dd>
              </div>
              <div>
                <dt>Next</dt>
                <dd>{nextAgent?.title || "None"}</dd>
              </div>
              <div>
                <dt>Channel</dt>
                <dd>{channel?.channel || "N/A"}</dd>
              </div>
            </dl>
            <p>{shortText(controlPlane?.operator_next_action || channel?.latest_system_message || "No next action projected.", 140)}</p>
          </section>
          <section className="data-card">
            <header className="panel-header">
              <h3>Harness</h3>
            </header>
            <dl>
              <div>
                <dt>Turns</dt>
                <dd>{String(harnessSummary.turn_count || 0)}</dd>
              </div>
              <div>
                <dt>Session events</dt>
                <dd>{String(harnessSummary.session_event_count || 0)}</dd>
              </div>
              <div>
                <dt>Artifacts</dt>
                <dd>{String(harnessSummary.artifact_count || 0)}</dd>
              </div>
            </dl>
            <p>{shortText(String(harnessSummary.yield_reason || access?.note || "No harness note."), 150)}</p>
            <div className="link-stack">
              {(access?.lan_urls || []).slice(0, 3).map((url) => (
                <a key={url} href={url} target="_blank" rel="noreferrer">
                  {url}
                </a>
              ))}
            </div>
          </section>
        </div>
      )}
      {tab === "operator" && (
        <div className="operator-stack">
          <section className="data-card">
            <header className="panel-header">
              <div>
                <p className="eyebrow">Control Plane</p>
                <h3>Operator Harness</h3>
              </div>
              <StatusPill
                label={humanize(controlPlane?.macro_state || controlPlane?.execution_state) || "Unknown"}
                tone={statusTone(controlPlane?.macro_state || controlPlane?.execution_state)}
              />
            </header>
            <div className="operator-grid">
              <div>
                <strong>{humanize(controlPlane?.macro_state || controlPlane?.closure_state) || "Unknown closure"}</strong>
                <p>{shortText(controlPlane?.narrative_summary || controlPlane?.progress_reason || controlPlane?.closure_reason || "No current operator guidance.", 140)}</p>
              </div>
              <div>
                <strong>{humanize(controlPlane?.approval_state) || "Approval"}</strong>
                <p>{shortText(controlPlane?.operator_next_action || "Review current control state.", 140)}</p>
              </div>
            </div>
            <div className="micro-stack">
              <span className="micro-meta">Session: {shortText(String(controlPlane?.canonical_session_id || "Unavailable"), 48)}</span>
              <span className="micro-meta">Turn: {shortText(String(controlPlane?.latest_turn_receipt?.turn_id || "None"), 32)}</span>
            </div>
            <label className="inline-form">
              <span>Operator reason</span>
              <textarea value={operatorReason} onChange={(event) => setOperatorReason(event.currentTarget.value)} rows={3} />
            </label>
            <label className="inline-form">
              <span>Operator feedback</span>
              <textarea
                value={feedbackText}
                onChange={(event) => setFeedbackText(event.currentTarget.value)}
                rows={3}
                placeholder="Add user or operator feedback to the running campaign"
              />
            </label>
            <div className="action-row action-row--wrap">
              {visiblePrimaryActions.map((action) => (
                <button
                  key={action}
                  disabled={isPending}
                  onClick={() =>
                    applyAction(action, action === "annotate_governance" ? { risk_level: riskLevel, autonomy_profile: autonomyProfile } : {})
                  }
                >
                  {humanize(action)}
                </button>
              ))}
              {(!availableActions.size || availableActions.has("append_feedback")) && (
                <button
                  disabled={isPending || !feedbackText.trim()}
                  onClick={() => applyAction("append_feedback", { feedback: feedbackText, target_node_id: "" })}
                >
                  Append feedback
                </button>
              )}
            </div>
            {operatorNotice && <p className="micro-meta">{operatorNotice}</p>}
          </section>

          <section className="data-card">
            <header className="panel-header">
              <div>
                <p className="eyebrow">Governance</p>
                <h3>Annotate strategy</h3>
              </div>
              <span className="micro-meta">{humanize(controlPlane?.risk_level) || "Medium"} risk</span>
            </header>
            <div className="draft-form-grid">
              <label>
                <span>Risk level</span>
                <input value={riskLevel} onChange={(event) => setRiskLevel(event.currentTarget.value)} />
              </label>
              <label>
                <span>Autonomy profile</span>
                <input value={autonomyProfile} onChange={(event) => setAutonomyProfile(event.currentTarget.value)} />
              </label>
            </div>
            <div className="action-row action-row--compact">
              <button
                disabled={isPending}
                onClick={() =>
                  applyAction("annotate_governance", {
                    risk_level: riskLevel,
                    autonomy_profile: autonomyProfile
                  })
                }
              >
                Save governance annotation
              </button>
            </div>
          </section>

          <section className="data-card">
            <header className="panel-header">
              <div>
                <p className="eyebrow">Recovery Inspector</p>
                <h3>Recovery candidates</h3>
              </div>
              <span className="micro-meta">{recoveryCandidates.length + transitionOptions.length} options</span>
            </header>
            <div className="panel-list">
              {[...recoveryCandidates, ...transitionOptions].map((item, index) => (
                <article
                  key={String(item.candidate_id || item.option_id || item.action_id || `${item.action || item.action_type}:${item.transition_to || item.resume_from || index}`)}
                  className="list-card list-card--static"
                >
                  <strong>{item.label || humanize(String(item.action || item.action_type || ""))}</strong>
                  <p>{shortText(String(item.reason || item.result_summary || ""), 120)}</p>
                  <div className="action-row action-row--compact">
                    <button
                      disabled={isPending}
                      onClick={() =>
                        applyAction(String(item.action || item.action_type || ""), {
                          transition_to: item.transition_to,
                          resume_from: item.resume_from,
                          check_ids: item.check_ids,
                          target_scope: item.target_scope,
                          target_node_id: item.target_node_id
                        })
                      }
                    >
                      Apply
                    </button>
                  </div>
                </article>
              ))}
              {!recoveryCandidates.length && !transitionOptions.length && (
                <div className="empty-block">No recovery candidates were projected for this campaign.</div>
              )}
            </div>
          </section>

          <section className="data-card">
            <header className="panel-header">
              <div>
                <p className="eyebrow">Audit Console</p>
                <h3>Recent operator actions</h3>
              </div>
              <span className="micro-meta">{auditActions.length}</span>
            </header>
            <div className="micro-stack">
              <span className="micro-meta">Skill collection: {shortText(collectionId || "Not specified", 36)}</span>
              <span className="micro-meta">Template: {shortText(workflowAuthoring?.template_label || workflowAuthoring?.template_id || "No template", 36)}</span>
            </div>
            <div className="panel-list">
              {auditActions.map((item, index) => (
                <article key={`${item.action_id || index}`} className="list-card list-card--static">
                  <strong>{humanize(String(item.action_type || item.action || "operator action"))}</strong>
                  <p>{shortText(String(item.result_summary || item.reason || ""), 120)}</p>
                  <div className="micro-stack">
                    <span className="micro-meta">{formatDate(String(item.created_at || ""))}</span>
                    <span className="micro-meta">{String(item.target_scope || "campaign")}</span>
                  </div>
                </article>
              ))}
              {!auditActions.length && <div className="empty-block">No operator actions recorded yet.</div>}
            </div>
          </section>
        </div>
      )}
    </aside>
  );
}

function splitLines(value: string): string[] {
  return value
    .split("\n")
    .map((item) => item.trim())
    .filter(Boolean);
}

function parseJsonObject(value: string): { value: Record<string, unknown>; error: string } {
  const text = value.trim();
  if (!text) {
    return { value: {}, error: "" };
  }
  try {
    const parsed = JSON.parse(text);
    if (typeof parsed === "object" && parsed !== null && !Array.isArray(parsed)) {
      return { value: parsed as Record<string, unknown>, error: "" };
    }
    return { value: {}, error: "Node overlay JSON must be an object." };
  } catch {
    return { value: {}, error: "Node overlay JSON is invalid; fix it before saving." };
  }
}

function buildPromptPatch({
  collectionId,
  familyHints,
  riskLevel,
  autonomyProfile,
  operatorReason,
  nodeOverlay,
  setOperatorNotice
}: {
  collectionId: string;
  familyHints: string;
  riskLevel: string;
  autonomyProfile: string;
  operatorReason: string;
  nodeOverlay: string;
  setOperatorNotice: (message: string) => void;
}): Record<string, unknown> | null {
  const parsedOverlay = parseJsonObject(nodeOverlay);
  if (parsedOverlay.error) {
    setOperatorNotice(parsedOverlay.error);
    return null;
  }
  return {
    collection_id: collectionId,
    family_hints: splitLines(familyHints),
    risk_level: riskLevel,
    autonomy_profile: autonomyProfile,
    operator_reason: operatorReason,
    node_overlay: parsedOverlay.value
  };
}
