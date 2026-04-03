import { beforeEach, describe, expect, it } from "vitest";

import { scopeKey, useConsoleStore } from "./console-store";

describe("console-store", () => {
  beforeEach(() => {
    useConsoleStore.setState({
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
      detailTab: "records"
    });
  });

  it("hydrates url state into the store", () => {
    useConsoleStore.getState().hydrate({
      workspace: "/tmp/demo",
      scope: "campaign",
      campaign: "campaign_7",
      board: "preview",
      tab: "artifacts",
      node: "review",
      artifact: "artifact_x",
      detailCampaign: "campaign_7",
      detailNode: "review"
    });

    const state = useConsoleStore.getState();
    expect(state.workspace).toBe("/tmp/demo");
    expect(state.scope).toBe("campaign");
    expect(state.selectedCampaignId).toBe("campaign_7");
    expect(state.boardMode).toBe("preview");
    expect(state.selectedArtifactId).toBe("artifact_x");
    expect(state.detailOpen).toBe(true);
  });

  it("stores timeline and viewport state by scope", () => {
    const key = scopeKey("campaign", "campaign_99");
    useConsoleStore.getState().setTimelineScroll(key, 248);
    useConsoleStore.getState().setGraphViewport(key, { x: 80, y: 140, zoom: 1.22 });

    const state = useConsoleStore.getState();
    expect(state.timelineScrollByScope[key]).toBe(248);
    expect(state.graphViewportByScope[key]).toEqual({ x: 80, y: 140, zoom: 1.22 });
  });

  it("keeps preview and detail selections mutually exclusive", () => {
    useConsoleStore.getState().selectArtifact("artifact_1");
    expect(useConsoleStore.getState().selectedArtifactId).toBe("artifact_1");

    useConsoleStore.getState().openDetail("campaign_1", "turn");
    let state = useConsoleStore.getState();
    expect(state.detailOpen).toBe(true);
    expect(state.selectedArtifactId).toBe("");
    expect(state.selectedRecordId).toBe("");

    useConsoleStore.getState().selectRecord("record_1");
    state = useConsoleStore.getState();
    expect(state.selectedRecordId).toBe("record_1");
    expect(state.detailOpen).toBe(false);
    expect(state.detailCampaignId).toBe("");
    expect(state.detailNodeId).toBe("");
  });
});
