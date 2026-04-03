import { useEffect, useMemo, useRef, useState, startTransition } from "react";
import { useMutation } from "@tanstack/react-query";
import type { Viewport } from "@xyflow/react";

import { CommandRail } from "./components/command-rail";
import { ActivityDock } from "./components/activity-dock";
import { ContextPanel } from "./components/context-panel";
import { DraftBoard } from "./components/draft-board";
import { GraphCanvas } from "./components/graph-canvas";
import { PreviewPane } from "./components/preview-pane";
import { AgentDetailDialog } from "./components/agent-detail-dialog";
import { consoleApi } from "./lib/api";
import { formatDate, humanize, shortText, statusTone } from "./lib/format";
import { readUrlState, writeUrlState } from "./lib/url-state";
import { useConsoleData } from "./hooks/use-console-data";
import { queryClient } from "./query-client";
import { scopeKey, useConsoleStore } from "./state/console-store";
import type { BoardNodeView, ConsoleEventEnvelope } from "./types";
import { StatusPill } from "./components/status-pill";

export function App() {
  const hydratedRef = useRef(false);
  const workspace = useConsoleStore((state) => state.workspace);
  const scope = useConsoleStore((state) => state.scope);
  const selectedCampaignId = useConsoleStore((state) => state.selectedCampaignId);
  const boardMode = useConsoleStore((state) => state.boardMode);
  const contextTab = useConsoleStore((state) => state.contextTab);
  const selectedNodeId = useConsoleStore((state) => state.selectedNodeId);
  const selectedArtifactId = useConsoleStore((state) => state.selectedArtifactId);
  const selectedRecordId = useConsoleStore((state) => state.selectedRecordId);
  const selectedDraftId = useConsoleStore((state) => state.selectedDraftId);
  const timelineScrollByScope = useConsoleStore((state) => state.timelineScrollByScope);
  const graphViewportByScope = useConsoleStore((state) => state.graphViewportByScope);
  const detailOpen = useConsoleStore((state) => state.detailOpen);
  const detailCampaignId = useConsoleStore((state) => state.detailCampaignId);
  const detailNodeId = useConsoleStore((state) => state.detailNodeId);
  const detailTab = useConsoleStore((state) => state.detailTab);
  const hydrate = useConsoleStore((state) => state.hydrate);
  const setWorkspace = useConsoleStore((state) => state.setWorkspace);
  const setScope = useConsoleStore((state) => state.setScope);
  const setCampaign = useConsoleStore((state) => state.setCampaign);
  const setBoardMode = useConsoleStore((state) => state.setBoardMode);
  const setContextTab = useConsoleStore((state) => state.setContextTab);
  const selectNode = useConsoleStore((state) => state.selectNode);
  const selectArtifact = useConsoleStore((state) => state.selectArtifact);
  const selectRecord = useConsoleStore((state) => state.selectRecord);
  const clearPreviewSelection = useConsoleStore((state) => state.clearPreviewSelection);
  const selectDraft = useConsoleStore((state) => state.selectDraft);
  const setTimelineScroll = useConsoleStore((state) => state.setTimelineScroll);
  const setGraphViewport = useConsoleStore((state) => state.setGraphViewport);
  const openDetail = useConsoleStore((state) => state.openDetail);
  const closeDetail = useConsoleStore((state) => state.closeDetail);
  const setDetailTab = useConsoleStore((state) => state.setDetailTab);
  const [selectedTimelineItemId, setSelectedTimelineItemId] = useState("");
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [inspectorOpen, setInspectorOpen] = useState(false);
  const [theme, setTheme] = useState<"light" | "dark">(readThemePreference);
  const scopeId = scopeKey(scope, selectedCampaignId);
  const previewOpen = scope !== "drafts" && Boolean(selectedArtifactId || selectedRecordId);

  useEffect(() => {
    if (hydratedRef.current) {
      return;
    }
    hydrate(readUrlState(window.location.search));
    hydratedRef.current = true;
  }, [hydrate]);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    document.documentElement.style.colorScheme = theme;
    document.querySelector('meta[name="theme-color"]')?.setAttribute("content", theme === "dark" ? "#10161f" : "#efe7da");
    window.localStorage.setItem("butler-console-theme", theme);
  }, [theme]);

  useEffect(() => {
    if ((detailOpen || previewOpen) && inspectorOpen) {
      setInspectorOpen(false);
    }
  }, [detailOpen, inspectorOpen, previewOpen]);

  useEffect(() => {
    if (scope === "drafts") {
      setInspectorOpen(false);
      clearPreviewSelection();
      closeDetail();
    }
  }, [clearPreviewSelection, closeDetail, scope]);

  useEffect(() => {
    if (boardMode === "preview") {
      setBoardMode("graph");
    }
  }, [boardMode, setBoardMode]);

  useEffect(() => {
    if (!hydratedRef.current) {
      return;
    }
    const next = writeUrlState({
      workspace,
      scope,
      campaign: selectedCampaignId || undefined,
      board: boardMode,
      tab: contextTab,
      node: selectedNodeId || undefined,
      artifact: selectedArtifactId || undefined,
      record: selectedRecordId || undefined,
      draft: selectedDraftId || undefined,
      detailCampaign: detailOpen ? detailCampaignId : undefined,
      detailNode: detailOpen ? detailNodeId : undefined,
      detailTab
    });
    const nextUrl = `${window.location.pathname}${next}`;
    window.history.replaceState({}, "", nextUrl);
  }, [
    boardMode,
    contextTab,
    detailCampaignId,
    detailNodeId,
    detailOpen,
    detailTab,
    scope,
    selectedArtifactId,
    selectedCampaignId,
    selectedDraftId,
    selectedNodeId,
    selectedRecordId,
    workspace
  ]);

  const {
    runtimeQuery,
    accessQuery,
    campaignsQuery,
    draftsQuery,
    globalBoardQuery,
    campaignQuery,
    graphQuery,
    boardQuery,
    eventsQuery,
    controlPlaneQuery,
    transitionOptionsQuery,
    recoveryCandidatesQuery,
    auditActionsQuery,
    previewQuery,
    draftQuery,
    detailQuery,
    promptSurfaceQuery,
    campaignWorkflowAuthoringQuery,
    draftWorkflowAuthoringQuery,
    draftCompilePreviewQuery
  } = useConsoleData();

  const campaigns = campaignsQuery.data || [];
  const drafts = draftsQuery.data || [];
  const board = scope === "global" ? globalBoardQuery.data : boardQuery.data;
  const graph = graphQuery.data;
  const timelineItems = useMemo(() => {
    if (scope !== "campaign") {
      return board?.timeline_items || [];
    }
    const boardItems = board?.timeline_items || [];
    const extraEvents = eventsQuery.data || [];
    if (!extraEvents.length) {
      return boardItems;
    }
    const mapped = extraEvents.map(eventToTimelineItem);
    const merged = [...boardItems];
    for (const item of mapped) {
      if (!merged.find((current) => current.id === item.id)) {
        merged.push(item);
      }
    }
    merged.sort((left, right) => String(left.timestamp || "").localeCompare(String(right.timestamp || "")));
    return merged;
  }, [board?.timeline_items, eventsQuery.data, scope]);

  const previewRecord = useMemo(
    () => board?.records.find((item) => item.record_id === selectedRecordId),
    [board?.records, selectedRecordId]
  );

  const currentDraft =
    draftQuery.data ||
    drafts.find((item) => item.draft_id === selectedDraftId) ||
    drafts[0];

  const controlPlane = useMemo(() => {
    if (!controlPlaneQuery.data) {
      return undefined;
    }
    return {
      ...controlPlaneQuery.data,
      transition_options:
        transitionOptionsQuery.data?.options || controlPlaneQuery.data.transition_options || [],
      recovery_candidates:
        recoveryCandidatesQuery.data?.candidates || controlPlaneQuery.data.recovery_candidates || []
    };
  }, [controlPlaneQuery.data, recoveryCandidatesQuery.data?.candidates, transitionOptionsQuery.data?.options]);

  useEffect(() => {
    if (scope === "campaign" && selectedCampaignId && !campaigns.find((item) => item.campaign_id === selectedCampaignId)) {
      if (campaigns[0]?.campaign_id) {
        setCampaign(campaigns[0].campaign_id);
      } else {
        setScope("global");
      }
    }
  }, [campaigns, scope, selectedCampaignId, setCampaign, setScope]);

  useEffect(() => {
    if (scope === "campaign" && board?.preview_defaults?.selected_node_id && !selectedNodeId) {
      selectNode(board.preview_defaults.selected_node_id);
    }
  }, [board?.preview_defaults?.selected_node_id, scope, selectNode, selectedNodeId]);

  useEffect(() => {
    if (scope === "drafts" && !selectedDraftId && drafts[0]?.draft_id) {
      selectDraft(drafts[0].draft_id);
    }
  }, [drafts, scope, selectDraft, selectedDraftId]);

  const actionMutation = useMutation({
    mutationFn: async ({
      action,
      patch
    }: {
      action: string;
      patch?: Record<string, unknown>;
    }) => {
      if (!selectedCampaignId) {
        return null;
      }
      return consoleApi.postCampaignAction(workspace, selectedCampaignId, {
        action,
        target_kind: "campaign",
        source_surface: "console_react",
        ...patch
      });
    },
    onSuccess: async () => {
      await invalidateCampaignQueries(workspace, selectedCampaignId);
    }
  });

  const promptPatchMutation = useMutation({
    mutationFn: async (patch: Record<string, unknown>) => {
      if (!selectedCampaignId) {
        return null;
      }
      return consoleApi.patchCampaignPromptSurface(workspace, selectedCampaignId, patch, selectedNodeId || undefined);
    },
    onSuccess: async () => {
      await invalidateCampaignQueries(workspace, selectedCampaignId);
    }
  });

  const workflowPatchMutation = useMutation({
    mutationFn: async (patch: Record<string, unknown>) => {
      if (!selectedCampaignId) {
        return null;
      }
      return consoleApi.patchCampaignWorkflowAuthoring(workspace, selectedCampaignId, patch);
    },
    onSuccess: async () => {
      await invalidateCampaignQueries(workspace, selectedCampaignId);
    }
  });

  const selectedNode = useMemo(() => {
    if (!board?.nodes?.length) {
      return null;
    }
    return (
      board.nodes.find((item) => item.id === selectedNodeId) ||
      board.nodes.find((item) => item.detail_node_id === selectedNodeId) ||
      board.nodes[0]
    );
  }, [board?.nodes, selectedNodeId]);

  const workspaceViewport = graphViewportByScope[scopeId];
  const workspaceTimelineScroll = timelineScrollByScope[scopeId] || 0;
  const draftStatus = currentDraft?.linked_campaign_id
    ? `Linked to ${currentDraft.linked_campaign_id}`
    : currentDraft?.pending_confirmation
      ? "Awaiting confirmation"
      : "Ready for patch and compile";
  const surfaceLabel = scope === "campaign" ? "Campaign Workspace" : scope === "drafts" ? "Draft Studio" : "Global Queue";
  const currentTaskSummary = (campaignQuery.data?.task_summary as Record<string, unknown> | undefined) || {};
  const currentTaskProgress = (currentTaskSummary.progress as Record<string, unknown> | undefined) || {};
  const controlHarness = (controlPlane?.harness_summary as Record<string, unknown> | undefined) || {};
  const surfaceTitle =
    scope === "campaign"
      ? shortText(board?.title || selectedCampaignId || "Campaign", 72) || "Campaign"
      : scope === "drafts"
        ? shortText(currentDraft?.goal || "Draft Studio", 84) || "Draft Studio"
        : shortText(board?.title || "Global Scheduler", 48) || "Global Scheduler";
  const surfaceSummary =
    scope === "drafts"
      ? shortText(
          [
            currentDraft?.selected_template_id || currentDraft?.recommended_template_id || currentDraft?.mode_id,
            draftStatus,
            currentDraft?.materials?.length ? `${currentDraft.materials.length} materials` : "",
            currentDraft?.hard_constraints?.length ? `${currentDraft.hard_constraints.length} constraints` : ""
          ].filter(Boolean).join(" · ") ||
            "Pick a draft, patch the contract, then launch into a campaign.",
          180
        ) || "Pick a draft, patch the contract, then launch into a campaign."
      : shortText(
          String(
            controlPlane?.narrative_summary ||
              currentTaskProgress.latest_summary ||
              board?.summary ||
              currentTaskSummary.next_action ||
              ""
          ),
          180
        ) || "Use the graph, turn ledger, and harness sheet to follow the active campaign.";
  const selectionTitle =
    shortText(selectedNode?.display_title || selectedNode?.title || "No node selected", 64) || "No node selected";
  const selectionSummary =
    shortText(selectedNode?.display_brief || selectedNode?.subtitle || "Select a node, artifact, or timeline point.", 108) ||
    "Select a node, artifact, or timeline point.";
  const signalItems = [
    {
      label: scope === "campaign" ? "Macro state" : "Runtime",
      value:
        scope === "campaign"
          ? humanize(controlPlane?.macro_state || board?.status) || "Unknown"
          : humanize(runtimeQuery.data?.process_state as string) || "Unknown",
      detail:
        scope === "campaign"
          ? shortText(String(controlPlane?.operator_next_action || currentTaskSummary.next_action || "No next action projected."), 90) || "No next action projected."
          : shortText((runtimeQuery.data?.note as string) || "No runtime note available.", 90) || "No runtime note available.",
      tone: statusTone(scope === "campaign" ? controlPlane?.macro_state || board?.status : (runtimeQuery.data?.process_state as string))
    },
    {
      label: scope === "campaign" ? "Harness" : "Scope",
      value:
        scope === "campaign"
          ? `${String(controlHarness.turn_count || 0)} turns · ${String(controlHarness.session_event_count || 0)} events`
          : scope === "drafts"
            ? `${drafts.length} drafts`
            : `${campaigns.length} campaigns`,
      detail:
        scope === "campaign"
          ? shortText(String(controlPlane?.canonical_session_id || selectionTitle), 56) || "Canonical session"
          : scope === "drafts"
            ? shortText(currentDraft?.selected_template_id || currentDraft?.recommended_template_id || draftStatus, 60) || "Draft queue"
            : shortText(board?.idle_reason || board?.summary || "Cross-campaign queue and runtime posture.", 90) || "Cross-campaign queue and runtime posture.",
      tone: "muted"
    },
    {
      label: scope === "campaign" ? "Deliveries" : "Updated",
      value:
        scope === "campaign"
          ? `${String((controlPlane?.latest_delivery_refs || []).length)} refs`
          : formatDate((runtimeQuery.data?.updated_at as string) || ""),
      detail:
        scope === "campaign"
          ? shortText(String(controlPlane?.latest_turn_receipt?.yield_reason || board?.idle_reason || "No delivery note available."), 90) || "No delivery note available."
          : shortText(board?.idle_reason || board?.summary || "Awaiting new state projection.", 90) || "Awaiting new state projection.",
      tone: statusTone(board?.status)
    }
  ];
  const activeBoard = scope === "campaign" ? board : globalBoardQuery.data;
  const previewModalTitle =
    previewQuery.data?.title || previewRecord?.preview_title || previewRecord?.title || "Preview";

  const openInspector = () => {
    closeDetail();
    clearPreviewSelection();
    setInspectorOpen(true);
  };

  const closeInspector = () => {
    setInspectorOpen(false);
  };

  const handleOpenDetail = (campaignId: string, nodeId: string) => {
    setInspectorOpen(false);
    openDetail(campaignId, nodeId);
  };

  const handleSelectArtifact = (artifactId: string) => {
    setInspectorOpen(false);
    selectArtifact(artifactId);
  };

  const handleSelectRecord = (recordId: string) => {
    setInspectorOpen(false);
    selectRecord(recordId);
  };

  return (
    <div className={`console-root ${sidebarCollapsed ? "console-root--sidebar-collapsed" : ""}`}>
      <div className={`console-sidebar ${sidebarCollapsed ? "is-collapsed" : ""}`}>
        <CommandRail
          workspace={workspace}
          runtime={runtimeQuery.data}
          access={accessQuery.data}
          campaigns={campaigns}
          drafts={drafts}
          scope={scope}
          selectedCampaignId={selectedCampaignId}
          selectedDraftId={selectedDraftId}
          theme={theme}
          collapsed={sidebarCollapsed}
          controlsEnabled={scope !== "drafts"}
          onWorkspaceChange={(value) => setWorkspace(value)}
          onActivateGlobal={() => startTransition(() => setScope("global"))}
          onActivateCampaign={(campaignId) =>
            startTransition(() => {
              setCampaign(campaignId);
              setContextTab("artifacts");
            })
          }
          onActivateDrafts={() => startTransition(() => setScope("drafts"))}
          onSelectDraft={(draftId) =>
            startTransition(() => {
              selectDraft(draftId);
              setScope("drafts");
            })
          }
          onOpenControls={openInspector}
          onToggleTheme={() => setTheme((current) => (current === "light" ? "dark" : "light"))}
          onToggleCollapsed={() => setSidebarCollapsed((current) => !current)}
        />
      </div>

      <div className="console-shell">
        <header className="console-masthead">
          <div className="masthead-copy">
            <p className="eyebrow">{surfaceLabel}</p>
            <h2 title={scope === "drafts" ? currentDraft?.goal || "Draft Studio" : board?.title || surfaceTitle}>{surfaceTitle}</h2>
            <p className="console-summary">{surfaceSummary}</p>
          </div>
          <div className="signal-strip">
            {signalItems.map((item) => (
              <article key={item.label} className="signal-card">
                <span className="signal-label">{item.label}</span>
                <strong>{item.value}</strong>
                <div className="signal-foot">
                  <p>{item.detail}</p>
                  <StatusPill label={humanize(item.tone === "muted" ? "steady" : item.tone)} tone={item.tone} />
                </div>
              </article>
            ))}
          </div>
        </header>

        <main className="mission-layout">
          {scope === "drafts" ? (
            <section className="workspace-stage workspace-stage--draft">
              <header className="stage-header">
                <div>
                  <p className="eyebrow">Draft Workspace</p>
                  <h3>Draft editing</h3>
                  <p>Edit the contract, run compile preview, then launch without leaving the workspace.</p>
                </div>
              </header>
              <DraftBoard
                workspace={workspace}
                drafts={drafts}
                draft={currentDraft}
                workflowAuthoring={draftWorkflowAuthoringQuery.data}
                compilePreview={draftCompilePreviewQuery.data}
                selectedDraftId={selectedDraftId}
                onSelectDraft={(draftId) => selectDraft(draftId)}
                onLaunched={(campaignId) =>
                  startTransition(() => {
                    setCampaign(campaignId);
                    setScope("campaign");
                    setContextTab("artifacts");
                  })
                }
              />
            </section>
          ) : (
            <>
              <section className="workspace-stage workspace-stage--graph">
                <header className="stage-header">
                  <div>
                    <p className="eyebrow">{scope === "campaign" ? "Campaign Narrative" : "Queue Workspace"}</p>
                    <h3>{scope === "campaign" ? "Ledger graph" : "Queue graph"}</h3>
                    <p>
                      {scope === "campaign"
                        ? "The graph shows macro ledger, current turn, deliverables, and harness recovery as one readable flow."
                        : "Inspect queue posture and campaign routing directly from the graph surface."}
                    </p>
                  </div>
                  <div className="stage-actions">
                    <button className="rail-tool-button" onClick={openInspector}>
                      Open controls
                    </button>
                  </div>
                </header>

                <section className="board-panel board-panel--graph">
                  <div className="board-surface-head">
                    <div>
                      <p className="eyebrow">Narrative Graph</p>
                      <strong title={selectedNode?.display_title || selectedNode?.title || "No node selected"}>{selectionTitle}</strong>
                    </div>
                    <p>{selectionSummary}</p>
                  </div>
                  <GraphCanvas
                    board={activeBoard}
                    selectedNodeId={selectedNode?.id || ""}
                    onSelectNode={(nodeId) => {
                      selectNode(nodeId);
                    }}
                    onOpenDetail={handleOpenDetail}
                    viewport={workspaceViewport}
                    onViewportChange={(view) => setGraphViewport(scopeId, view as Viewport)}
                  />
                </section>
              </section>

              <ActivityDock
                timelineItems={timelineItems}
                artifacts={board?.artifacts || []}
                records={board?.records || []}
                selectedTimelineItemId={selectedTimelineItemId}
                selectedArtifactId={selectedArtifactId}
                selectedRecordId={selectedRecordId}
                scrollLeft={workspaceTimelineScroll}
                onScrollChange={(left) => setTimelineScroll(scopeId, left)}
                onSelectTimelineItem={(item) => {
                  setSelectedTimelineItemId(item.id);
                  const targetNodeId = item.detail_node_id || item.node_id || item.step_id;
                  if (targetNodeId) {
                    selectNode(targetNodeId);
                  }
                  if (item.detail_available && item.detail_campaign_id && item.detail_node_id) {
                    handleOpenDetail(item.detail_campaign_id, item.detail_node_id);
                  }
                }}
                onSelectArtifact={handleSelectArtifact}
                onSelectRecord={handleSelectRecord}
              />
            </>
          )}
        </main>
      </div>

      {scope !== "drafts" && inspectorOpen && (
        <div className="panel-overlay" onClick={closeInspector}>
          <div className="panel-sheet" onClick={(event) => event.stopPropagation()}>
            <div className="panel-sheet__header">
              <div>
                <p className="eyebrow">Control Sheet</p>
                <h3>{surfaceTitle}</h3>
              </div>
              <button className="icon-button" onClick={closeInspector}>
                Close
              </button>
            </div>
            <ContextPanel
              tab={contextTab}
              onChangeTab={setContextTab}
              artifacts={board?.artifacts || []}
              records={board?.records || []}
              runtime={runtimeQuery.data}
              access={accessQuery.data}
              currentAgent={board?.current_agent}
              nextAgent={board?.next_agent}
              selectedNodeId={selectedNodeId}
              controlPlane={controlPlane}
              auditActions={auditActionsQuery.data || []}
              promptSurface={promptSurfaceQuery.data}
              workflowAuthoring={campaignWorkflowAuthoringQuery.data}
              channel={
                currentDraft?.session_id
                  ? ({
                      channel: "external_chat",
                      session_id: currentDraft.session_id,
                      thread_id: currentDraft.session_id,
                      latest_system_message: currentDraft.goal
                    } as const)
                  : undefined
              }
              selectedArtifactId={selectedArtifactId}
              selectedRecordId={selectedRecordId}
              onSelectArtifact={handleSelectArtifact}
              onSelectRecord={handleSelectRecord}
              onApplyAction={async (action, patch) => {
                await actionMutation.mutateAsync({ action, patch });
              }}
              onApplyPromptPatch={async (patch) => {
                await promptPatchMutation.mutateAsync(patch);
              }}
              onApplyWorkflowPatch={async (patch) => {
                await workflowPatchMutation.mutateAsync(patch);
              }}
            />
          </div>
        </div>
      )}

      {previewOpen && (
        <div className="preview-overlay" onClick={() => clearPreviewSelection()}>
          <div className="preview-modal" onClick={(event) => event.stopPropagation()}>
            <div className="preview-modal__header">
              <div>
                <p className="eyebrow">Document Preview</p>
                <h3 title={previewModalTitle}>{shortText(previewModalTitle, 120) || "Preview"}</h3>
              </div>
              <button className="icon-button" onClick={() => clearPreviewSelection()}>
                Close
              </button>
            </div>
            <div className="preview-modal__body">
              <PreviewPane preview={previewQuery.data} record={previewRecord} chromeless />
            </div>
          </div>
        </div>
      )}

      <AgentDetailDialog
        open={detailOpen}
        detail={detailQuery.data}
        tab={detailTab}
        onClose={closeDetail}
        onChangeTab={setDetailTab}
      />
    </div>
  );
}

function eventToTimelineItem(event: ConsoleEventEnvelope) {
  return {
    id: event.event_id,
    kind: event.event_type,
    timestamp: event.created_at,
    anchor_timestamp: event.created_at,
    display_time: formatDate(event.created_at),
    display_title: humanize(event.event_type),
    display_brief: shortText(JSON.stringify(event.payload ?? {}), 84),
    node_id: String(event.payload?.phase || event.payload?.step_id || ""),
    step_id: String(event.payload?.step_id || event.payload?.phase || ""),
    status: String(event.payload?.status || event.severity || ""),
    detail_available: Boolean(event.scope_id && (event.payload?.phase || event.payload?.step_id)),
    detail_campaign_id: event.scope_id,
    detail_node_id: String(event.payload?.phase || event.payload?.step_id || ""),
    detail_payload: event.payload || {}
  };
}

async function invalidateCampaignQueries(workspace: string, campaignId?: string) {
  if (!campaignId) {
    return;
  }
  await Promise.all([
    queryClient.invalidateQueries({ queryKey: ["console", "campaign", workspace, campaignId] }),
    queryClient.invalidateQueries({ queryKey: ["console", "board", workspace, campaignId] }),
    queryClient.invalidateQueries({ queryKey: ["console", "graph", workspace, campaignId] }),
    queryClient.invalidateQueries({ queryKey: ["console", "events", workspace, campaignId] }),
    queryClient.invalidateQueries({ queryKey: ["console", "control-plane", workspace, campaignId] }),
    queryClient.invalidateQueries({ queryKey: ["console", "transition-options", workspace, campaignId] }),
    queryClient.invalidateQueries({ queryKey: ["console", "recovery-candidates", workspace, campaignId] }),
    queryClient.invalidateQueries({ queryKey: ["console", "audit-actions", workspace, campaignId] }),
    queryClient.invalidateQueries({ queryKey: ["console", "prompt-surface", workspace, campaignId] }),
    queryClient.invalidateQueries({ queryKey: ["console", "campaign-workflow-authoring", workspace, campaignId] })
  ]);
}

function readThemePreference(): "light" | "dark" {
  if (typeof window === "undefined") {
    return "light";
  }
  const stored = window.localStorage.getItem("butler-console-theme");
  if (stored === "light" || stored === "dark") {
    return stored;
  }
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}
