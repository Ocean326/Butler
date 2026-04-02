import { useEffect, useState, useTransition } from "react";

import { consoleApi } from "../lib/api";
import { shortText } from "../lib/format";
import type { CompilePreviewEnvelope, FrontdoorDraftView, WorkflowAuthoringEnvelope } from "../types";
import { queryClient } from "../query-client";

interface DraftBoardProps {
  workspace: string;
  drafts: FrontdoorDraftView[];
  draft?: FrontdoorDraftView;
  workflowAuthoring?: WorkflowAuthoringEnvelope;
  compilePreview?: CompilePreviewEnvelope;
  selectedDraftId: string;
  onSelectDraft: (draftId: string) => void;
  onLaunched: (campaignId: string) => void;
}

export function DraftBoard({
  workspace,
  drafts,
  draft,
  workflowAuthoring,
  compilePreview,
  selectedDraftId,
  onSelectDraft,
  onLaunched
}: DraftBoardProps) {
  const skillSelection = (draft?.skill_selection || {}) as {
    collection_id?: string;
    family_hints?: string[];
  };
  const [form, setForm] = useState({
    goal: "",
    materials: "",
    hard_constraints: "",
    acceptance_criteria: "",
    selected_template_id: "",
    composition_mode: "template",
    skill_collection_id: "",
    skill_family_hints: "",
    phase_plan: "",
    role_plan: ""
  });
  const [message, setMessage] = useState("");
  const [isPending, startTransition] = useTransition();

  useEffect(() => {
    setForm({
      goal: draft?.goal || "",
      materials: (draft?.materials || []).join("\n"),
      hard_constraints: (draft?.hard_constraints || []).join("\n"),
      acceptance_criteria: (draft?.acceptance_criteria || []).join("\n"),
      selected_template_id: draft?.selected_template_id || draft?.recommended_template_id || "",
      composition_mode: workflowAuthoring?.composition_mode || draft?.composition_mode || "template",
      skill_collection_id: String(skillSelection.collection_id || ""),
      skill_family_hints: (skillSelection.family_hints || []).join("\n"),
      phase_plan: ((workflowAuthoring?.phase_plan || []) as string[]).join("\n"),
      role_plan: ((workflowAuthoring?.role_plan || []) as string[]).join("\n")
    });
    setMessage("");
  }, [draft, skillSelection.collection_id, skillSelection.family_hints, workflowAuthoring]);

  return (
    <section className="draft-shell">
      <aside className="draft-list">
        <div className="section-head">
          <h2>Draft Studio</h2>
          <span className="meta-chip">{drafts.length}</span>
        </div>
        <div className="panel-list">
          {drafts.map((item) => (
            <button
              key={item.draft_id}
              className={`list-card ${selectedDraftId === item.draft_id ? "is-active" : ""}`}
              onClick={() => onSelectDraft(item.draft_id)}
              title={item.goal || item.draft_id}
            >
              <strong>{shortText(item.goal || item.draft_id, 76) || item.draft_id}</strong>
              <p>{shortText(item.selected_template_id || item.mode_id || "Draft", 76)}</p>
              <span className="micro-meta">{item.linked_campaign_id ? "Launched" : "Pending"}</span>
            </button>
          ))}
          {!drafts.length && <div className="empty-block">No drafts available.</div>}
        </div>
      </aside>

      <div className="draft-editor">
        {!draft && <div className="empty-block">Select a draft from the left column to edit, compile, and launch it.</div>}
        {draft && (
          <>
            <header className="draft-header">
              <div>
                <p className="eyebrow">Draft Studio</p>
                <h2 title={draft.goal || draft.draft_id}>{shortText(draft.goal || draft.draft_id, 120) || draft.draft_id}</h2>
                <p>
                  {shortText(
                    [
                      workflowAuthoring?.template_label || draft.selected_template_id || draft.recommended_template_id || draft.mode_id,
                      draft.pending_confirmation ? "awaiting confirmation" : draft.linked_campaign_id ? `linked to ${draft.linked_campaign_id}` : "ready to launch"
                    ].filter(Boolean).join(" · "),
                    140
                  )}
                </p>
              </div>
              <div className="draft-actions">
                <button
                  disabled={isPending}
                  onClick={() =>
                    startTransition(() => {
                      void (async () => {
                        try {
                          await saveDraft({
                            workspace,
                            draftId: draft.draft_id,
                            form,
                            onSaved: async () => {
                              setMessage(`Saved ${draft.draft_id}`);
                            }
                          });
                        } catch (error) {
                          setMessage(error instanceof Error ? error.message : `Failed to save ${draft.draft_id}`);
                        }
                      })();
                    })
                  }
                >
                  Save
                </button>
                <button
                  disabled={isPending}
                  onClick={() =>
                    startTransition(() => {
                      void (async () => {
                        try {
                          await compileDraft({
                            workspace,
                            draftId: draft.draft_id,
                            form,
                            onCompiled: async () => {
                              setMessage(`Compiled ${draft.draft_id}`);
                            }
                          });
                        } catch (error) {
                          setMessage(error instanceof Error ? error.message : `Failed to compile ${draft.draft_id}`);
                        }
                      })();
                    })
                  }
                >
                  Compile preview
                </button>
                <button
                  className="button-strong"
                  disabled={isPending || Boolean(draft.linked_campaign_id)}
                  onClick={() =>
                    startTransition(() => {
                      void (async () => {
                        try {
                          await saveDraft({
                            workspace,
                            draftId: draft.draft_id,
                            form
                          });
                          const launched = await consoleApi.launchDraft(workspace, draft.draft_id);
                          await invalidateDraftQueries(workspace, draft.draft_id);
                          setMessage(`Launched ${launched.linked_campaign_id}`);
                          if (launched.linked_campaign_id) {
                            onLaunched(launched.linked_campaign_id);
                          }
                        } catch (error) {
                          setMessage(error instanceof Error ? error.message : `Failed to launch ${draft.draft_id}`);
                        }
                      })();
                    })
                  }
                >
                  {draft.linked_campaign_id ? "Already launched" : "Launch"}
                </button>
              </div>
            </header>

            <div className="draft-studio-grid">
              <section className="data-card">
                <header className="panel-header">
                  <div>
                    <p className="eyebrow">Draft Workspace</p>
                    <h3>Goal & constraints</h3>
                  </div>
                </header>
                <div className="draft-form-grid">
                  <label className="draft-form-grid__full">
                    <span>Goal</span>
                    <textarea
                      value={form.goal}
                      onChange={(event) => setForm((current) => ({ ...current, goal: event.currentTarget.value }))}
                      rows={4}
                    />
                  </label>
                  <label>
                    <span>Materials</span>
                    <textarea
                      value={form.materials}
                      onChange={(event) => setForm((current) => ({ ...current, materials: event.currentTarget.value }))}
                      rows={7}
                    />
                  </label>
                  <label>
                    <span>Hard constraints</span>
                    <textarea
                      value={form.hard_constraints}
                      onChange={(event) => setForm((current) => ({ ...current, hard_constraints: event.currentTarget.value }))}
                      rows={7}
                    />
                  </label>
                  <label className="draft-form-grid__full">
                    <span>Acceptance criteria</span>
                    <textarea
                      value={form.acceptance_criteria}
                      onChange={(event) => setForm((current) => ({ ...current, acceptance_criteria: event.currentTarget.value }))}
                      rows={6}
                    />
                  </label>
                </div>
              </section>

              <section className="data-card">
                <header className="panel-header">
                  <div>
                    <p className="eyebrow">Workflow Canvas</p>
                    <h3>Template & authoring shell</h3>
                  </div>
                </header>
                <div className="draft-form-grid">
                  <label>
                    <span>Template ID</span>
                    <input
                      value={form.selected_template_id}
                      onChange={(event) => setForm((current) => ({ ...current, selected_template_id: event.currentTarget.value }))}
                    />
                  </label>
                  <label>
                    <span>Composition mode</span>
                    <input
                      value={form.composition_mode}
                      onChange={(event) => setForm((current) => ({ ...current, composition_mode: event.currentTarget.value }))}
                    />
                  </label>
                  <label>
                    <span>Phase plan</span>
                    <textarea
                      value={form.phase_plan}
                      onChange={(event) => setForm((current) => ({ ...current, phase_plan: event.currentTarget.value }))}
                      rows={7}
                    />
                  </label>
                  <label>
                    <span>Role plan</span>
                    <textarea
                      value={form.role_plan}
                      onChange={(event) => setForm((current) => ({ ...current, role_plan: event.currentTarget.value }))}
                      rows={7}
                    />
                  </label>
                </div>
              </section>

              <section className="data-card">
                <header className="panel-header">
                  <div>
                    <p className="eyebrow">Policy Plane</p>
                    <h3>Skill exposure</h3>
                  </div>
                </header>
                <div className="draft-form-grid">
                  <label>
                    <span>Skill collection</span>
                    <input
                      value={form.skill_collection_id}
                      onChange={(event) => setForm((current) => ({ ...current, skill_collection_id: event.currentTarget.value }))}
                    />
                  </label>
                  <label>
                    <span>Family hints</span>
                    <textarea
                      value={form.skill_family_hints}
                      onChange={(event) => setForm((current) => ({ ...current, skill_family_hints: event.currentTarget.value }))}
                      rows={7}
                    />
                  </label>
                </div>
              </section>

              <section className="data-card">
                <header className="panel-header">
                  <div>
                    <p className="eyebrow">Compile & Diff Review</p>
                    <h3>Pre-launch validation</h3>
                  </div>
                  <span className="micro-meta">{compilePreview?.compile_result || "Not compiled"}</span>
                </header>
                <div className="compile-preview">
                  <strong>{compilePreview?.template_id || workflowAuthoring?.template_id || "No template selected"}</strong>
                  <p>{shortText((compilePreview?.warnings || []).join(" · ") || "No warnings yet.", 180)}</p>
                  <div className="micro-stack">
                    {(compilePreview?.risk_hints || []).map((item) => (
                      <span key={item} className="micro-meta">{item}</span>
                    ))}
                  </div>
                  <pre className="prompt-preview">
                    {JSON.stringify(compilePreview?.compiled_contract || workflowAuthoring || {}, null, 2)}
                  </pre>
                </div>
              </section>
            </div>
            {message && <p className="draft-message">{message}</p>}
          </>
        )}
      </div>
    </section>
  );
}

async function saveDraft({
  workspace,
  draftId,
  form,
  onSaved
}: {
  workspace: string;
  draftId: string;
  form: {
    goal: string;
    materials: string;
    hard_constraints: string;
    acceptance_criteria: string;
    selected_template_id: string;
    composition_mode: string;
    skill_collection_id: string;
    skill_family_hints: string;
    phase_plan: string;
    role_plan: string;
  };
  onSaved?: () => Promise<void> | void;
}) {
  await consoleApi.patchDraft(workspace, draftId, {
    goal: form.goal,
    materials: splitLines(form.materials),
    hard_constraints: splitLines(form.hard_constraints),
    acceptance_criteria: splitLines(form.acceptance_criteria),
    selected_template_id: form.selected_template_id,
    composition_mode: form.composition_mode,
    skill_selection: {
      collection_id: form.skill_collection_id,
      family_hints: splitLines(form.skill_family_hints)
    }
  });
  await consoleApi.patchDraftWorkflowAuthoring(workspace, draftId, {
    selected_template_id: form.selected_template_id,
    composition_mode: form.composition_mode,
    composition_plan: {
      phase_plan: splitLines(form.phase_plan),
      role_plan: splitLines(form.role_plan)
    },
    skeleton_changed: form.composition_mode === "composition"
  });
  await invalidateDraftQueries(workspace, draftId);
  await onSaved?.();
}

async function compileDraft({
  workspace,
  draftId,
  form,
  onCompiled
}: {
  workspace: string;
  draftId: string;
  form: {
    selected_template_id: string;
    composition_mode: string;
    phase_plan: string;
    role_plan: string;
  };
  onCompiled?: () => Promise<void> | void;
}) {
  await consoleApi.postDraftCompilePreview(workspace, draftId, {
    selected_template_id: form.selected_template_id,
    composition_mode: form.composition_mode,
    composition_plan: {
      phase_plan: splitLines(form.phase_plan),
      role_plan: splitLines(form.role_plan)
    },
    skeleton_changed: form.composition_mode === "composition"
  });
  await invalidateDraftQueries(workspace, draftId);
  await onCompiled?.();
}

async function invalidateDraftQueries(workspace: string, draftId: string) {
  await queryClient.invalidateQueries({ queryKey: ["console", "drafts", workspace] });
  await queryClient.invalidateQueries({ queryKey: ["console", "draft", workspace, draftId] });
  await queryClient.invalidateQueries({ queryKey: ["console", "draft-workflow-authoring", workspace, draftId] });
  await queryClient.invalidateQueries({ queryKey: ["console", "draft-compile-preview", workspace, draftId] });
}

function splitLines(value: string): string[] {
  return value
    .split("\n")
    .map((item) => item.trim())
    .filter(Boolean);
}
