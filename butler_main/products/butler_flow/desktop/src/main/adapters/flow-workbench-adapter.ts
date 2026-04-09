import { execFile } from "node:child_process";
import path from "node:path";
import { promisify } from "node:util";
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
} from "../../shared/dto";
import type { ManagerMessageStreamEvent, ManagerMessageStreamStart } from "../../shared/ipc";
import { MockFlowWorkbenchAdapter } from "./mock-flow-workbench-adapter";

const execFileAsync = promisify(execFile);
const MANAGER_STREAM_CHUNK_SIZE = 180;

interface FlowWorkbenchAdapterOptions {
  repoRoot: string;
}

export class FlowWorkbenchAdapter {
  private readonly mockAdapter = new MockFlowWorkbenchAdapter();

  constructor(private readonly options: FlowWorkbenchAdapterOptions) {}

  private useMock(): boolean {
    return process.env.BUTLER_DESKTOP_USE_MOCK === "1";
  }

  private resolvePythonBinary(): string {
    if (process.env.BUTLER_FLOW_PYTHON) {
      return process.env.BUTLER_FLOW_PYTHON;
    }
    const venv = process.env.VIRTUAL_ENV;
    if (venv) {
      return process.platform === "win32" ? path.join(venv, "Scripts", "python.exe") : path.join(venv, "bin", "python");
    }
    return process.platform === "win32" ? "python" : "python3";
  }

  private withConfig(configPath?: string): string[] {
    return configPath ? ["--config", configPath] : [];
  }

  private async invokeBridge<T>(args: string[]): Promise<T> {
    if (this.useMock()) {
      throw new Error("mock_enabled");
    }
    const python = this.resolvePythonBinary();
    const pythonPath = [this.options.repoRoot, process.env.PYTHONPATH].filter(Boolean).join(path.delimiter);
    try {
      const { stdout } = await execFileAsync(
        python,
        ["-m", "butler_main.butler_flow.desktop_bridge", ...args],
        {
          cwd: this.options.repoRoot,
          env: {
            ...process.env,
            PYTHONPATH: pythonPath
          },
          maxBuffer: 8 * 1024 * 1024
        }
      );
      return JSON.parse(stdout) as T;
    } catch (error) {
      const stderr = typeof error === "object" && error && "stderr" in error ? String(error.stderr || "") : "";
      if (stderr.trim()) {
        try {
          const parsed = JSON.parse(stderr) as { message?: string };
          throw new Error(parsed.message || stderr.trim());
        } catch {
          throw new Error(stderr.trim());
        }
      }
      throw error;
    }
  }

  async getHome(configPath?: string): Promise<WorkspacePayload> {
    if (this.useMock()) {
      return this.mockAdapter.getHome();
    }
    return this.invokeBridge<WorkspacePayload>([...this.withConfig(configPath), "home"]);
  }

  async getFlow(configPath: string | undefined, flowId: string): Promise<SingleFlowPayload> {
    if (this.useMock()) {
      return this.mockAdapter.getFlow();
    }
    return this.invokeBridge<SingleFlowPayload>([...this.withConfig(configPath), "flow", "--flow-id", flowId]);
  }

  async getDetail(configPath: string | undefined, flowId: string): Promise<Record<string, unknown>> {
    if (this.useMock()) {
      return this.mockAdapter.getDetail();
    }
    return this.invokeBridge<Record<string, unknown>>([
      ...this.withConfig(configPath),
      "detail",
      "--flow-id",
      flowId
    ]);
  }

  async getManageCenter(configPath?: string): Promise<ManageCenterDTO> {
    if (this.useMock()) {
      return this.mockAdapter.getManageCenter();
    }
    return this.invokeBridge<ManageCenterDTO>([...this.withConfig(configPath), "manage"]);
  }

  async getPreflight(configPath?: string): Promise<Record<string, unknown>> {
    if (this.useMock()) {
      return this.mockAdapter.getPreflight();
    }
    return this.invokeBridge<Record<string, unknown>>([...this.withConfig(configPath), "preflight"]);
  }

  async getThreadHome(configPath?: string): Promise<ThreadHomeDTO> {
    if (this.useMock()) {
      return this.mockAdapter.getThreadHome();
    }
    return this.invokeBridge<ThreadHomeDTO>([...this.withConfig(configPath), "thread-home"]);
  }

  async getManagerThread(configPath: string | undefined, managerSessionId?: string): Promise<ManagerThreadDTO> {
    if (this.useMock()) {
      return this.mockAdapter.getManagerThread(managerSessionId);
    }
    const args = [...this.withConfig(configPath), "manager-thread"];
    if (managerSessionId) {
      args.push("--manager-session-id", managerSessionId);
    }
    return this.invokeBridge<ManagerThreadDTO>(args);
  }

  async getSupervisorThread(configPath: string | undefined, flowId: string): Promise<SupervisorThreadDTO> {
    if (this.useMock()) {
      return this.mockAdapter.getSupervisorThread(flowId);
    }
    return this.invokeBridge<SupervisorThreadDTO>([
      ...this.withConfig(configPath),
      "supervisor-thread",
      "--flow-id",
      flowId
    ]);
  }

  async getAgentFocus(configPath: string | undefined, flowId: string, roleId: string): Promise<AgentFocusDTO> {
    if (this.useMock()) {
      return this.mockAdapter.getAgentFocus(flowId, roleId);
    }
    return this.invokeBridge<AgentFocusDTO>([
      ...this.withConfig(configPath),
      "agent-focus",
      "--flow-id",
      flowId,
      "--role-id",
      roleId
    ]);
  }

  async getTemplateTeam(configPath?: string, assetId?: string): Promise<TemplateTeamDTO> {
    if (this.useMock()) {
      return this.mockAdapter.getTemplateTeam(assetId);
    }
    const args = [...this.withConfig(configPath), "template-team"];
    if (assetId) {
      args.push("--asset-id", assetId);
    }
    return this.invokeBridge<TemplateTeamDTO>(args);
  }

  async sendManagerMessage(payload: ManagerMessagePayload): Promise<ManagerMessageResult> {
    if (this.useMock()) {
      return this.mockAdapter.sendManagerMessage(payload);
    }
    const args = [
      ...this.withConfig(payload.configPath),
      "manager-message",
      "--instruction",
      payload.instruction
    ];
    if (payload.manageTarget) {
      args.push("--manage", payload.manageTarget);
    }
    if (payload.managerSessionId) {
      args.push("--manager-session-id", payload.managerSessionId);
    }
    return this.invokeBridge<ManagerMessageResult>(args);
  }

  private chunkManagerResponse(text: string): string[] {
    const token = String(text || "").trim();
    if (!token) {
      return [];
    }
    const chunks: string[] = [];
    for (let index = 0; index < token.length; index += MANAGER_STREAM_CHUNK_SIZE) {
      chunks.push(token.slice(index, index + MANAGER_STREAM_CHUNK_SIZE));
    }
    return chunks;
  }

  private managerResponseText(result: ManagerMessageResult): string {
    const payload = result.message || {};
    const messageText = String(payload.response || payload.message || "").trim();
    if (messageText) {
      return messageText;
    }
    const latestResponse = String(result.thread?.latest_response || "").trim();
    if (latestResponse) {
      return latestResponse;
    }
    const flowSummary = String(result.launched_flow?.summary || result.launched_flow?.flow_id || "").trim();
    return flowSummary || "Manager updated.";
  }

  async streamManagerMessage(
    payload: ManagerMessagePayload,
    requestId: string,
    emit: (event: ManagerMessageStreamEvent) => void
  ): Promise<ManagerMessageStreamStart> {
    emit({
      requestId,
      type: "started",
      managerSessionId: payload.managerSessionId,
      timestamp: new Date().toISOString()
    });

    try {
      const finalResult = await this.sendManagerMessage(payload);
      for (const chunkText of this.chunkManagerResponse(this.managerResponseText(finalResult))) {
        emit({
          requestId,
          type: "chunk",
          managerSessionId: finalResult.manager_session_id,
          chunkText,
          timestamp: new Date().toISOString()
        });
      }
      emit({
        requestId,
        type: "completed",
        managerSessionId: finalResult.manager_session_id,
        finalResult,
        timestamp: new Date().toISOString()
      });
    } catch (error) {
      emit({
        requestId,
        type: "failed",
        managerSessionId: payload.managerSessionId,
        error: String((error as Error)?.message || error || "Manager stream failed."),
        timestamp: new Date().toISOString()
      });
    }

    return { requestId };
  }

  async performAction(payload: DesktopActionPayload): Promise<Record<string, unknown>> {
    if (this.useMock()) {
      return this.mockAdapter.performAction(payload);
    }
    const args = [
      ...this.withConfig(payload.configPath),
      "action",
      "--flow-id",
      payload.flowId,
      "--type",
      payload.type
    ];
    if (payload.instruction) {
      args.push("--instruction", payload.instruction);
    }
    if (payload.repoContractPath) {
      args.push("--repo-contract-path", payload.repoContractPath);
    }
    return this.invokeBridge<Record<string, unknown>>(args);
  }
}
