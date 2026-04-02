import { create } from "zustand";

import type { AgentTab, BoardMode, ContextTab, ScopeMode } from "../types";
import type { ConsoleUrlState } from "../lib/url-state";

type ScrollState = Record<string, number>;
type ViewportState = Record<string, { x: number; y: number; zoom: number }>;

export interface ConsoleStoreState {
  workspace: string;
  scope: ScopeMode;
  selectedCampaignId: string;
  boardMode: BoardMode;
  contextTab: ContextTab;
  selectedNodeId: string;
  selectedArtifactId: string;
  selectedRecordId: string;
  selectedDraftId: string;
  timelineScrollByScope: ScrollState;
  graphViewportByScope: ViewportState;
  detailOpen: boolean;
  detailCampaignId: string;
  detailNodeId: string;
  detailTab: AgentTab;
  setWorkspace: (workspace: string) => void;
  setScope: (scope: ScopeMode) => void;
  setCampaign: (campaignId: string) => void;
  setBoardMode: (mode: BoardMode) => void;
  setContextTab: (tab: ContextTab) => void;
  selectNode: (nodeId: string) => void;
  selectArtifact: (artifactId: string) => void;
  selectRecord: (recordId: string) => void;
  clearPreviewSelection: () => void;
  selectDraft: (draftId: string) => void;
  setTimelineScroll: (scopeKey: string, left: number) => void;
  setGraphViewport: (scopeKey: string, view: { x: number; y: number; zoom: number }) => void;
  openDetail: (campaignId: string, nodeId: string) => void;
  closeDetail: () => void;
  setDetailTab: (tab: AgentTab) => void;
  hydrate: (state: ConsoleUrlState) => void;
}

export const scopeKey = (scope: ScopeMode, campaignId: string): string =>
  scope === "campaign" ? `campaign:${campaignId}` : scope;

export const useConsoleStore = create<ConsoleStoreState>((set) => ({
  workspace: ".",
  scope: "global",
  selectedCampaignId: "",
  boardMode: "graph",
  contextTab: "runtime",
  selectedNodeId: "",
  selectedArtifactId: "",
  selectedRecordId: "",
  selectedDraftId: "",
  timelineScrollByScope: {},
  graphViewportByScope: {},
  detailOpen: false,
  detailCampaignId: "",
  detailNodeId: "",
  detailTab: "records",
  setWorkspace: (workspace) => set({ workspace: workspace.trim() || "." }),
  setScope: (scope) =>
    set((state) => ({
      scope,
      contextTab: scope === "drafts" ? "drafts" : state.contextTab
    })),
  setCampaign: (selectedCampaignId) => set({ selectedCampaignId, scope: "campaign" }),
  setBoardMode: (boardMode) => set({ boardMode }),
  setContextTab: (contextTab) => set({ contextTab }),
  selectNode: (selectedNodeId) => set({ selectedNodeId }),
  selectArtifact: (selectedArtifactId) =>
    set({
      selectedArtifactId,
      selectedRecordId: "",
      detailOpen: false,
      detailCampaignId: "",
      detailNodeId: ""
    }),
  selectRecord: (selectedRecordId) =>
    set({
      selectedRecordId,
      selectedArtifactId: "",
      detailOpen: false,
      detailCampaignId: "",
      detailNodeId: ""
    }),
  clearPreviewSelection: () => set({ selectedArtifactId: "", selectedRecordId: "" }),
  selectDraft: (selectedDraftId) => set({ selectedDraftId, scope: "drafts", contextTab: "drafts" }),
  setTimelineScroll: (key, left) =>
    set((state) => ({
      timelineScrollByScope: {
        ...state.timelineScrollByScope,
        [key]: left
      }
    })),
  setGraphViewport: (key, view) =>
    set((state) => ({
      graphViewportByScope: {
        ...state.graphViewportByScope,
        [key]: view
      }
    })),
  openDetail: (detailCampaignId, detailNodeId) =>
    set({
      detailOpen: true,
      detailCampaignId,
      detailNodeId,
      selectedArtifactId: "",
      selectedRecordId: ""
    }),
  closeDetail: () => set({ detailOpen: false, detailCampaignId: "", detailNodeId: "" }),
  setDetailTab: (detailTab) => set({ detailTab }),
  hydrate: (state) =>
    set({
      workspace: state.workspace?.trim() || ".",
      scope: state.scope ?? "global",
      selectedCampaignId: state.campaign ?? "",
      boardMode: state.board ?? "graph",
      contextTab: state.tab ?? "runtime",
      selectedNodeId: state.node ?? "",
      selectedArtifactId: state.artifact ?? "",
      selectedRecordId: state.record ?? "",
      selectedDraftId: state.draft ?? "",
      detailOpen: Boolean(state.detailCampaign && state.detailNode),
      detailCampaignId: state.detailCampaign ?? "",
      detailNodeId: state.detailNode ?? "",
      detailTab: state.detailTab ?? "records"
    })
}));
