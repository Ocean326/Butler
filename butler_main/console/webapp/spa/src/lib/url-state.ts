import type { AgentTab, BoardMode, ContextTab, ScopeMode } from "../types";

export interface ConsoleUrlState {
  workspace?: string;
  scope?: ScopeMode;
  campaign?: string;
  board?: BoardMode;
  tab?: ContextTab;
  node?: string;
  artifact?: string;
  record?: string;
  draft?: string;
  detailCampaign?: string;
  detailNode?: string;
  detailTab?: AgentTab;
}

export function readUrlState(search: string): ConsoleUrlState {
  const params = new URLSearchParams(search);
  const scopeRaw = params.get("scope");
  const boardRaw = params.get("board");
  const tabRaw = params.get("tab");
  const detailTabRaw = params.get("detailTab");
  return {
    workspace: params.get("workspace") || undefined,
    scope: scopeRaw === "campaign" || scopeRaw === "drafts" ? scopeRaw : "global",
    campaign: params.get("campaign") || undefined,
    board: boardRaw === "preview" ? "preview" : "graph",
    tab:
      tabRaw === "artifacts" || tabRaw === "records" || tabRaw === "drafts" || tabRaw === "operator"
        ? tabRaw
        : "runtime",
    node: params.get("node") || undefined,
    artifact: params.get("artifact") || undefined,
    record: params.get("record") || undefined,
    draft: params.get("draft") || undefined,
    detailCampaign: params.get("detailCampaign") || undefined,
    detailNode: params.get("detailNode") || undefined,
    detailTab:
      detailTabRaw === "planned" || detailTabRaw === "artifacts" || detailTabRaw === "raw"
        ? detailTabRaw
        : "records"
  };
}

export function writeUrlState(next: ConsoleUrlState): string {
  const params = new URLSearchParams();
  if (next.workspace && next.workspace !== ".") {
    params.set("workspace", next.workspace);
  }
  if (next.scope && next.scope !== "global") {
    params.set("scope", next.scope);
  }
  if (next.campaign) {
    params.set("campaign", next.campaign);
  }
  if (next.board && next.board !== "graph") {
    params.set("board", next.board);
  }
  if (next.tab && next.tab !== "runtime") {
    params.set("tab", next.tab);
  }
  if (next.node) {
    params.set("node", next.node);
  }
  if (next.artifact) {
    params.set("artifact", next.artifact);
  }
  if (next.record) {
    params.set("record", next.record);
  }
  if (next.draft) {
    params.set("draft", next.draft);
  }
  if (next.detailCampaign) {
    params.set("detailCampaign", next.detailCampaign);
  }
  if (next.detailNode) {
    params.set("detailNode", next.detailNode);
  }
  if (next.detailTab && next.detailTab !== "records") {
    params.set("detailTab", next.detailTab);
  }
  const encoded = params.toString();
  return encoded ? `?${encoded}` : "";
}
