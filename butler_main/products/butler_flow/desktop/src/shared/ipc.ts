import type {
  DesktopActionPayload,
  ManageCenterDTO,
  SingleFlowPayload,
  WorkspacePayload
} from "./dto";

export interface DesktopRequestOptions {
  configPath?: string;
}

export interface DesktopFlowRequest extends DesktopRequestOptions {
  flowId: string;
}

export interface DesktopArtifactOpenRequest {
  target: string;
}

export interface DesktopChooseConfigResult {
  canceled: boolean;
  configPath?: string;
}

export interface ButlerDesktopApi {
  getHome(options?: DesktopRequestOptions): Promise<WorkspacePayload>;
  getFlow(options: DesktopFlowRequest): Promise<SingleFlowPayload>;
  getDetail(options: DesktopFlowRequest): Promise<Record<string, unknown>>;
  getManageCenter(options?: DesktopRequestOptions): Promise<ManageCenterDTO>;
  getPreflight(options?: DesktopRequestOptions): Promise<Record<string, unknown>>;
  performAction(payload: DesktopActionPayload): Promise<Record<string, unknown>>;
  chooseConfigPath(): Promise<DesktopChooseConfigResult>;
  openArtifact(request: DesktopArtifactOpenRequest): Promise<{ opened: boolean; reason?: string }>;
}

declare global {
  interface Window {
    butlerDesktop: ButlerDesktopApi;
  }
}
