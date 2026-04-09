import type {
  AgentFocusDTO,
  DesktopActionPayload,
  ManageCenterDTO,
  ManagerMessagePayload,
  ManagerMessageResult,
  ManagerThreadDTO,
  SingleFlowPayload,
  SupervisorThreadDTO,
  TemplateTeamDTO,
  ThreadHomeDTO,
  WorkspacePayload
} from "./dto";

export interface DesktopRequestOptions {
  configPath?: string;
}

export interface DesktopFlowRequest extends DesktopRequestOptions {
  flowId: string;
}

export interface ManagerThreadRequest extends DesktopRequestOptions {
  managerSessionId?: string;
}

export interface AgentFocusRequest extends DesktopFlowRequest {
  roleId: string;
}

export interface TemplateTeamRequest extends DesktopRequestOptions {
  assetId?: string;
}

export interface DesktopArtifactOpenRequest {
  target: string;
}

export interface DesktopChooseConfigResult {
  canceled: boolean;
  configPath?: string;
}

export interface DesktopDefaultConfigResult {
  configPath?: string;
}

export type ManagerMessageStreamEventType = "started" | "chunk" | "completed" | "failed";

export interface ManagerMessageStreamStart {
  requestId: string;
}

export interface ManagerMessageStreamEvent {
  requestId: string;
  type: ManagerMessageStreamEventType;
  managerSessionId?: string;
  chunkText?: string;
  finalResult?: ManagerMessageResult;
  error?: string;
  timestamp?: string;
}

export type ManagerMessageStreamListener = (event: ManagerMessageStreamEvent) => void;

export interface ButlerDesktopApi {
  getHome(options?: DesktopRequestOptions): Promise<WorkspacePayload>;
  getFlow(options: DesktopFlowRequest): Promise<SingleFlowPayload>;
  getDetail(options: DesktopFlowRequest): Promise<Record<string, unknown>>;
  getManageCenter(options?: DesktopRequestOptions): Promise<ManageCenterDTO>;
  getPreflight(options?: DesktopRequestOptions): Promise<Record<string, unknown>>;
  getThreadHome(options?: DesktopRequestOptions): Promise<ThreadHomeDTO>;
  getManagerThread(options?: ManagerThreadRequest): Promise<ManagerThreadDTO>;
  getSupervisorThread(options: DesktopFlowRequest): Promise<SupervisorThreadDTO>;
  getAgentFocus(options: AgentFocusRequest): Promise<AgentFocusDTO>;
  getTemplateTeam(options?: TemplateTeamRequest): Promise<TemplateTeamDTO>;
  getDefaultConfigPath(): Promise<DesktopDefaultConfigResult>;
  sendManagerMessage(payload: ManagerMessagePayload): Promise<ManagerMessageResult>;
  sendManagerMessageStream(payload: ManagerMessagePayload): Promise<ManagerMessageStreamStart>;
  onManagerMessageEvent(listener: ManagerMessageStreamListener): () => void;
  performAction(payload: DesktopActionPayload): Promise<Record<string, unknown>>;
  chooseConfigPath(): Promise<DesktopChooseConfigResult>;
  openArtifact(request: DesktopArtifactOpenRequest): Promise<{ opened: boolean; reason?: string }>;
}

declare global {
  interface Window {
    butlerDesktop: ButlerDesktopApi;
  }
}
