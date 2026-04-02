import type {
  AccessDiagnostics,
  AgentDetailEnvelope,
  AuditActionRecord,
  BoardSnapshot,
  CampaignSummary,
  ChannelThreadSummary,
  CompilePreviewEnvelope,
  ConsoleEventEnvelope,
  ControlPlaneEnvelope,
  ControlActionRequest,
  ControlActionResult,
  FrontdoorDraftView,
  GraphSnapshot,
  PromptSurfaceEnvelope,
  PreviewEnvelope,
  RuntimeStatus,
  WorkflowAuthoringEnvelope
} from "../types";

export interface ApiClientOptions {
  baseUrl?: string;
}

export class ApiError extends Error {
  status: number;
  payload: unknown;

  constructor(message: string, status: number, payload: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.payload = payload;
  }
}

export class ConsoleApiClient {
  private readonly baseUrl: string;

  constructor(options: ApiClientOptions = {}) {
    this.baseUrl = options.baseUrl ?? "/console/api";
  }

  async getRuntime(workspace: string): Promise<RuntimeStatus> {
    return this.request<RuntimeStatus>("/runtime", { workspace });
  }

  async getAccess(workspace: string): Promise<AccessDiagnostics> {
    return this.request<AccessDiagnostics>("/access", { workspace });
  }

  async getGlobalBoard(workspace: string): Promise<BoardSnapshot> {
    return this.request<BoardSnapshot>("/global/board", { workspace, limit: 24 });
  }

  async listCampaigns(workspace: string): Promise<CampaignSummary[]> {
    return this.request<CampaignSummary[]>("/campaigns", { workspace, limit: 50 });
  }

  async getCampaign(workspace: string, campaignId: string): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>(`/campaigns/${encodeURIComponent(campaignId)}`, { workspace });
  }

  async getCampaignGraph(workspace: string, campaignId: string): Promise<GraphSnapshot> {
    return this.request<GraphSnapshot>(`/campaigns/${encodeURIComponent(campaignId)}/graph`, { workspace });
  }

  async getCampaignBoard(workspace: string, campaignId: string): Promise<BoardSnapshot> {
    return this.request<BoardSnapshot>(`/campaigns/${encodeURIComponent(campaignId)}/board`, { workspace });
  }

  async getCampaignControlPlane(workspace: string, campaignId: string): Promise<ControlPlaneEnvelope> {
    return this.request<ControlPlaneEnvelope>(`/campaigns/${encodeURIComponent(campaignId)}/control-plane`, { workspace });
  }

  async getCampaignTransitionOptions(workspace: string, campaignId: string): Promise<{ campaign_id: string; options: AuditActionRecord[] }> {
    return this.request<{ campaign_id: string; options: AuditActionRecord[] }>(
      `/campaigns/${encodeURIComponent(campaignId)}/transition-options`,
      { workspace }
    );
  }

  async getCampaignRecoveryCandidates(workspace: string, campaignId: string): Promise<{ campaign_id: string; candidates: AuditActionRecord[] }> {
    return this.request<{ campaign_id: string; candidates: AuditActionRecord[] }>(
      `/campaigns/${encodeURIComponent(campaignId)}/recovery-candidates`,
      { workspace }
    );
  }

  async getCampaignEvents(workspace: string, campaignId: string): Promise<ConsoleEventEnvelope[]> {
    return this.request<ConsoleEventEnvelope[]>(`/campaigns/${encodeURIComponent(campaignId)}/events`, {
      workspace,
      limit: 32
    });
  }

  async getAuditActions(workspace: string, campaignId: string): Promise<AuditActionRecord[]> {
    return this.request<AuditActionRecord[]>(`/campaigns/${encodeURIComponent(campaignId)}/audit-actions`, {
      workspace,
      limit: 50
    });
  }

  async getCampaignPromptSurface(workspace: string, campaignId: string): Promise<PromptSurfaceEnvelope> {
    return this.request<PromptSurfaceEnvelope>(`/campaigns/${encodeURIComponent(campaignId)}/prompt-surface`, { workspace });
  }

  async getAgentPromptSurface(workspace: string, campaignId: string, nodeId: string): Promise<PromptSurfaceEnvelope> {
    return this.request<PromptSurfaceEnvelope>(
      `/campaigns/${encodeURIComponent(campaignId)}/agents/${encodeURIComponent(nodeId)}/prompt-surface`,
      { workspace }
    );
  }

  async patchCampaignPromptSurface(
    workspace: string,
    campaignId: string,
    patch: Record<string, unknown>,
    nodeId?: string
  ): Promise<PromptSurfaceEnvelope> {
    const path = nodeId
      ? `/campaigns/${encodeURIComponent(campaignId)}/agents/${encodeURIComponent(nodeId)}/prompt-surface`
      : `/campaigns/${encodeURIComponent(campaignId)}/prompt-surface`;
    return this.request<PromptSurfaceEnvelope>(path, { workspace }, { method: "PATCH", body: JSON.stringify(patch) });
  }

  async getCampaignWorkflowAuthoring(workspace: string, campaignId: string): Promise<WorkflowAuthoringEnvelope> {
    return this.request<WorkflowAuthoringEnvelope>(`/campaigns/${encodeURIComponent(campaignId)}/workflow-authoring`, { workspace });
  }

  async patchCampaignWorkflowAuthoring(
    workspace: string,
    campaignId: string,
    patch: Record<string, unknown>
  ): Promise<WorkflowAuthoringEnvelope> {
    return this.request<WorkflowAuthoringEnvelope>(
      `/campaigns/${encodeURIComponent(campaignId)}/workflow-authoring`,
      { workspace },
      { method: "PATCH", body: JSON.stringify(patch) }
    );
  }

  async getAgentDetail(workspace: string, campaignId: string, nodeId: string): Promise<AgentDetailEnvelope> {
    return this.request<AgentDetailEnvelope>(
      `/campaigns/${encodeURIComponent(campaignId)}/agents/${encodeURIComponent(nodeId)}/detail`,
      { workspace }
    );
  }

  async getArtifactPreview(
    workspace: string,
    campaignId: string,
    artifactId: string
  ): Promise<PreviewEnvelope> {
    return this.request<PreviewEnvelope>(
      `/campaigns/${encodeURIComponent(campaignId)}/artifacts/${encodeURIComponent(artifactId)}/preview`,
      { workspace }
    );
  }

  async listDrafts(workspace: string): Promise<FrontdoorDraftView[]> {
    return this.request<FrontdoorDraftView[]>("/drafts", { workspace, limit: 50 });
  }

  async getDraft(workspace: string, draftId: string): Promise<FrontdoorDraftView> {
    return this.request<FrontdoorDraftView>(`/drafts/${encodeURIComponent(draftId)}`, { workspace });
  }

  async getDraftWorkflowAuthoring(workspace: string, draftId: string): Promise<WorkflowAuthoringEnvelope> {
    return this.request<WorkflowAuthoringEnvelope>(`/drafts/${encodeURIComponent(draftId)}/workflow-authoring`, { workspace });
  }

  async patchDraft(
    workspace: string,
    draftId: string,
    patch: Partial<FrontdoorDraftView>
  ): Promise<FrontdoorDraftView> {
    return this.request<FrontdoorDraftView>(
      `/drafts/${encodeURIComponent(draftId)}`,
      { workspace },
      {
        method: "PATCH",
        body: JSON.stringify(patch)
      }
    );
  }

  async patchDraftWorkflowAuthoring(
    workspace: string,
    draftId: string,
    patch: Record<string, unknown>
  ): Promise<WorkflowAuthoringEnvelope> {
    return this.request<WorkflowAuthoringEnvelope>(
      `/drafts/${encodeURIComponent(draftId)}/workflow-authoring`,
      { workspace },
      { method: "PATCH", body: JSON.stringify(patch) }
    );
  }

  async getDraftCompilePreview(workspace: string, draftId: string): Promise<CompilePreviewEnvelope> {
    return this.request<CompilePreviewEnvelope>(`/drafts/${encodeURIComponent(draftId)}/compile-preview`, { workspace });
  }

  async postDraftCompilePreview(
    workspace: string,
    draftId: string,
    patch: Record<string, unknown>
  ): Promise<CompilePreviewEnvelope> {
    return this.request<CompilePreviewEnvelope>(
      `/drafts/${encodeURIComponent(draftId)}/compile-preview`,
      { workspace },
      { method: "POST", body: JSON.stringify(patch) }
    );
  }

  async launchDraft(workspace: string, draftId: string): Promise<FrontdoorDraftView> {
    return this.request<FrontdoorDraftView>(
      `/drafts/${encodeURIComponent(draftId)}/launch`,
      { workspace },
      { method: "POST" }
    );
  }

  async postCampaignAction(
    workspace: string,
    campaignId: string,
    request: ControlActionRequest
  ): Promise<ControlActionResult> {
    return this.request<ControlActionResult>(
      `/campaigns/${encodeURIComponent(campaignId)}/actions`,
      { workspace },
      {
        method: "POST",
        body: JSON.stringify(request)
      }
    );
  }

  async getChannelSummary(workspace: string, sessionId: string): Promise<ChannelThreadSummary> {
    return this.request<ChannelThreadSummary>(`/channels/${encodeURIComponent(sessionId)}`, { workspace });
  }

  createEventStream(workspace: string, campaignId: string): EventSource {
    const url = this.url(`/campaigns/${encodeURIComponent(campaignId)}/events/stream`, {
      workspace,
      limit: 32
    });
    return new EventSource(url);
  }

  private async request<T>(
    path: string,
    query: Record<string, string | number | boolean>,
    init: RequestInit = {}
  ): Promise<T> {
    const response = await fetch(this.url(path, query), {
      headers: {
        "Content-Type": "application/json",
        ...(init.headers ?? {})
      },
      ...init
    });

    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      const message =
        typeof payload?.error === "string"
          ? payload.error
          : typeof payload?.detail?.error === "string"
            ? payload.detail.error
            : `Request failed with status ${response.status}`;
      throw new ApiError(message, response.status, payload);
    }
    return payload as T;
  }

  private url(path: string, query: Record<string, string | number | boolean>): string {
    const url = new URL(`${this.baseUrl}${path}`, window.location.origin);
    for (const [key, value] of Object.entries(query)) {
      url.searchParams.set(key, String(value));
    }
    return url.toString();
  }
}

export const consoleApi = new ConsoleApiClient();
