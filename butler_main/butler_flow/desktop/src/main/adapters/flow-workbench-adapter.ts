import { execFile } from "node:child_process";
import path from "node:path";
import { promisify } from "node:util";
import type {
  DesktopActionPayload,
  ManageCenterDTO,
  SingleFlowPayload,
  WorkspacePayload
} from "../../shared/dto";
import { MockFlowWorkbenchAdapter } from "./mock-flow-workbench-adapter";

const execFileAsync = promisify(execFile);

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
