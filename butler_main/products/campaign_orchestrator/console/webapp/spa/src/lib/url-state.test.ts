import { describe, expect, it } from "vitest";

import { readUrlState, writeUrlState } from "./url-state";

describe("url-state", () => {
  it("reads defaults for an empty query string", () => {
    expect(readUrlState("")).toEqual({
      workspace: undefined,
      scope: "global",
      campaign: undefined,
      board: "graph",
      tab: "runtime",
      node: undefined,
      artifact: undefined,
      record: undefined,
      draft: undefined,
      detailCampaign: undefined,
      detailNode: undefined,
      detailTab: "records"
    });
  });

  it("round-trips non-default values", () => {
    const encoded = writeUrlState({
      workspace: "/tmp/workspace",
      scope: "campaign",
      campaign: "campaign_1",
      board: "preview",
      tab: "artifacts",
      node: "implement",
      artifact: "artifact_a",
      draft: "draft_9",
      detailCampaign: "campaign_1",
      detailNode: "review",
      detailTab: "raw"
    });

    expect(readUrlState(encoded)).toEqual({
      workspace: "/tmp/workspace",
      scope: "campaign",
      campaign: "campaign_1",
      board: "preview",
      tab: "artifacts",
      node: "implement",
      artifact: "artifact_a",
      record: undefined,
      draft: "draft_9",
      detailCampaign: "campaign_1",
      detailNode: "review",
      detailTab: "raw"
    });
  });
});
