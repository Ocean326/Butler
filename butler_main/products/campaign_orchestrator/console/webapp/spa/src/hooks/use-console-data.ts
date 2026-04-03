import { useEffect } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { consoleApi } from "../lib/api";
import { useConsoleStore } from "../state/console-store";
import type { ConsoleEventEnvelope } from "../types";

const OVERVIEW_INTERVAL = 20_000;
const ACTIVE_INTERVAL = 12_000;

export function useConsoleData() {
  const workspace = useConsoleStore((state) => state.workspace);
  const scope = useConsoleStore((state) => state.scope);
  const selectedCampaignId = useConsoleStore((state) => state.selectedCampaignId);
  const detailOpen = useConsoleStore((state) => state.detailOpen);
  const detailCampaignId = useConsoleStore((state) => state.detailCampaignId);
  const detailNodeId = useConsoleStore((state) => state.detailNodeId);
  const selectedNodeId = useConsoleStore((state) => state.selectedNodeId);
  const selectedArtifactId = useConsoleStore((state) => state.selectedArtifactId);
  const selectedDraftId = useConsoleStore((state) => state.selectedDraftId);
  const queryClient = useQueryClient();

  const runtimeQuery = useQuery({
    queryKey: ["console", "runtime", workspace],
    queryFn: () => consoleApi.getRuntime(workspace),
    refetchInterval: OVERVIEW_INTERVAL
  });

  const accessQuery = useQuery({
    queryKey: ["console", "access", workspace],
    queryFn: () => consoleApi.getAccess(workspace),
    refetchInterval: OVERVIEW_INTERVAL
  });

  const campaignsQuery = useQuery({
    queryKey: ["console", "campaigns", workspace],
    queryFn: () => consoleApi.listCampaigns(workspace),
    refetchInterval: OVERVIEW_INTERVAL
  });

  const draftsQuery = useQuery({
    queryKey: ["console", "drafts", workspace],
    queryFn: () => consoleApi.listDrafts(workspace),
    refetchInterval: OVERVIEW_INTERVAL
  });

  const globalBoardQuery = useQuery({
    queryKey: ["console", "global-board", workspace],
    queryFn: () => consoleApi.getGlobalBoard(workspace),
    enabled: scope === "global",
    refetchInterval: scope === "global" ? OVERVIEW_INTERVAL : false
  });

  const campaignQuery = useQuery({
    queryKey: ["console", "campaign", workspace, selectedCampaignId],
    queryFn: () => consoleApi.getCampaign(workspace, selectedCampaignId),
    enabled: scope === "campaign" && Boolean(selectedCampaignId),
    refetchInterval: scope === "campaign" ? ACTIVE_INTERVAL : false
  });

  const graphQuery = useQuery({
    queryKey: ["console", "graph", workspace, selectedCampaignId],
    queryFn: () => consoleApi.getCampaignGraph(workspace, selectedCampaignId),
    enabled: scope === "campaign" && Boolean(selectedCampaignId),
    refetchInterval: scope === "campaign" ? ACTIVE_INTERVAL : false
  });

  const boardQuery = useQuery({
    queryKey: ["console", "board", workspace, selectedCampaignId],
    queryFn: () => consoleApi.getCampaignBoard(workspace, selectedCampaignId),
    enabled: scope === "campaign" && Boolean(selectedCampaignId),
    refetchInterval: scope === "campaign" ? ACTIVE_INTERVAL : false
  });

  const controlPlaneQuery = useQuery({
    queryKey: ["console", "control-plane", workspace, selectedCampaignId],
    queryFn: () => consoleApi.getCampaignControlPlane(workspace, selectedCampaignId),
    enabled: scope === "campaign" && Boolean(selectedCampaignId),
    refetchInterval: scope === "campaign" ? ACTIVE_INTERVAL : false
  });

  const transitionOptionsQuery = useQuery({
    queryKey: ["console", "transition-options", workspace, selectedCampaignId],
    queryFn: () => consoleApi.getCampaignTransitionOptions(workspace, selectedCampaignId),
    enabled: scope === "campaign" && Boolean(selectedCampaignId),
    refetchInterval: scope === "campaign" ? ACTIVE_INTERVAL : false
  });

  const recoveryCandidatesQuery = useQuery({
    queryKey: ["console", "recovery-candidates", workspace, selectedCampaignId],
    queryFn: () => consoleApi.getCampaignRecoveryCandidates(workspace, selectedCampaignId),
    enabled: scope === "campaign" && Boolean(selectedCampaignId),
    refetchInterval: scope === "campaign" ? ACTIVE_INTERVAL : false
  });

  const eventsQuery = useQuery({
    queryKey: ["console", "events", workspace, selectedCampaignId],
    queryFn: () => consoleApi.getCampaignEvents(workspace, selectedCampaignId),
    enabled: scope === "campaign" && Boolean(selectedCampaignId),
    refetchInterval: false
  });

  const auditActionsQuery = useQuery({
    queryKey: ["console", "audit-actions", workspace, selectedCampaignId],
    queryFn: () => consoleApi.getAuditActions(workspace, selectedCampaignId),
    enabled: scope === "campaign" && Boolean(selectedCampaignId),
    refetchInterval: scope === "campaign" ? ACTIVE_INTERVAL : false
  });

  const previewQuery = useQuery({
    queryKey: ["console", "preview", workspace, selectedCampaignId, selectedArtifactId],
    queryFn: () => consoleApi.getArtifactPreview(workspace, selectedCampaignId, selectedArtifactId),
    enabled: scope === "campaign" && Boolean(selectedCampaignId) && Boolean(selectedArtifactId)
  });

  const draftQuery = useQuery({
    queryKey: ["console", "draft", workspace, selectedDraftId],
    queryFn: () => consoleApi.getDraft(workspace, selectedDraftId),
    enabled: scope === "drafts" && Boolean(selectedDraftId)
  });

  const detailQuery = useQuery({
    queryKey: ["console", "detail", workspace, detailCampaignId, detailNodeId],
    queryFn: () => consoleApi.getAgentDetail(workspace, detailCampaignId, detailNodeId),
    enabled: detailOpen && Boolean(detailCampaignId) && Boolean(detailNodeId),
    refetchInterval: detailOpen ? ACTIVE_INTERVAL : false
  });

  const promptSurfaceQuery = useQuery({
    queryKey: ["console", "prompt-surface", workspace, selectedCampaignId, selectedNodeId],
    queryFn: () =>
      selectedNodeId
        ? consoleApi.getAgentPromptSurface(workspace, selectedCampaignId, selectedNodeId)
        : consoleApi.getCampaignPromptSurface(workspace, selectedCampaignId),
    enabled: scope === "campaign" && Boolean(selectedCampaignId),
    refetchInterval: scope === "campaign" ? ACTIVE_INTERVAL : false
  });

  const campaignWorkflowAuthoringQuery = useQuery({
    queryKey: ["console", "campaign-workflow-authoring", workspace, selectedCampaignId],
    queryFn: () => consoleApi.getCampaignWorkflowAuthoring(workspace, selectedCampaignId),
    enabled: scope === "campaign" && Boolean(selectedCampaignId),
    refetchInterval: scope === "campaign" ? ACTIVE_INTERVAL : false
  });

  const draftWorkflowAuthoringQuery = useQuery({
    queryKey: ["console", "draft-workflow-authoring", workspace, selectedDraftId],
    queryFn: () => consoleApi.getDraftWorkflowAuthoring(workspace, selectedDraftId),
    enabled: scope === "drafts" && Boolean(selectedDraftId)
  });

  const draftCompilePreviewQuery = useQuery({
    queryKey: ["console", "draft-compile-preview", workspace, selectedDraftId],
    queryFn: () => consoleApi.getDraftCompilePreview(workspace, selectedDraftId),
    enabled: scope === "drafts" && Boolean(selectedDraftId)
  });

  useEffect(() => {
    if (scope !== "campaign" || !selectedCampaignId) {
      return undefined;
    }
    const stream = consoleApi.createEventStream(workspace, selectedCampaignId);
    const seen = new Set<string>();
    stream.addEventListener("message", (event) => {
      if (!event.data) {
        return;
      }
      try {
        const payload = JSON.parse(event.data) as ConsoleEventEnvelope;
        if (payload.event_id) {
          if (seen.has(payload.event_id)) {
            return;
          }
          seen.add(payload.event_id);
        }
        queryClient.setQueryData<ConsoleEventEnvelope[] | undefined>(
          ["console", "events", workspace, selectedCampaignId],
          (current) => {
            const next = [...(current ?? []), payload];
            next.sort((left, right) => {
              if (left.created_at === right.created_at) {
                return left.event_id.localeCompare(right.event_id);
              }
              return left.created_at.localeCompare(right.created_at);
            });
            return next.slice(-32);
          }
        );
        queryClient.invalidateQueries({ queryKey: ["console", "board", workspace, selectedCampaignId] });
        queryClient.invalidateQueries({ queryKey: ["console", "graph", workspace, selectedCampaignId] });
        queryClient.invalidateQueries({ queryKey: ["console", "campaign", workspace, selectedCampaignId] });
        queryClient.invalidateQueries({ queryKey: ["console", "control-plane", workspace, selectedCampaignId] });
        queryClient.invalidateQueries({ queryKey: ["console", "recovery-candidates", workspace, selectedCampaignId] });
        queryClient.invalidateQueries({ queryKey: ["console", "transition-options", workspace, selectedCampaignId] });
        queryClient.invalidateQueries({ queryKey: ["console", "audit-actions", workspace, selectedCampaignId] });
        queryClient.invalidateQueries({ queryKey: ["console", "prompt-surface", workspace, selectedCampaignId] });
        queryClient.invalidateQueries({ queryKey: ["console", "campaign-workflow-authoring", workspace, selectedCampaignId] });
        if (detailOpen && detailCampaignId === selectedCampaignId) {
          queryClient.invalidateQueries({
            queryKey: ["console", "detail", workspace, detailCampaignId, detailNodeId]
          });
        }
      } catch {
        queryClient.invalidateQueries({ queryKey: ["console", "events", workspace, selectedCampaignId] });
      }
    });
    stream.onerror = () => {
      queryClient.invalidateQueries({ queryKey: ["console", "events", workspace, selectedCampaignId] });
    };
    return () => {
      stream.close();
    };
  }, [detailCampaignId, detailNodeId, detailOpen, queryClient, scope, selectedCampaignId, workspace]);

  return {
    runtimeQuery,
    accessQuery,
    campaignsQuery,
    draftsQuery,
    globalBoardQuery,
    campaignQuery,
    graphQuery,
    boardQuery,
    controlPlaneQuery,
    transitionOptionsQuery,
    recoveryCandidatesQuery,
    eventsQuery,
    auditActionsQuery,
    previewQuery,
    draftQuery,
    detailQuery,
    promptSurfaceQuery,
    campaignWorkflowAuthoringQuery,
    draftWorkflowAuthoringQuery,
    draftCompilePreviewQuery
  };
}
