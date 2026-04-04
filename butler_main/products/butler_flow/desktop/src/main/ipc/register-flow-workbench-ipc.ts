import { dialog, ipcMain, shell } from "electron";
import type { BrowserWindow } from "electron";
import { DESKTOP_CHANNELS } from "./channels";
import { FlowWorkbenchAdapter } from "../adapters/flow-workbench-adapter";

export function registerFlowWorkbenchIpc(window: BrowserWindow, adapter: FlowWorkbenchAdapter): void {
  ipcMain.handle(DESKTOP_CHANNELS.getHome, async (_event, options?: { configPath?: string }) => {
    return adapter.getHome(options?.configPath);
  });
  ipcMain.handle(DESKTOP_CHANNELS.getFlow, async (_event, options: { configPath?: string; flowId: string }) => {
    return adapter.getFlow(options?.configPath, options.flowId);
  });
  ipcMain.handle(DESKTOP_CHANNELS.getDetail, async (_event, options: { configPath?: string; flowId: string }) => {
    return adapter.getDetail(options?.configPath, options.flowId);
  });
  ipcMain.handle(DESKTOP_CHANNELS.getManageCenter, async (_event, options?: { configPath?: string }) => {
    return adapter.getManageCenter(options?.configPath);
  });
  ipcMain.handle(DESKTOP_CHANNELS.getPreflight, async (_event, options?: { configPath?: string }) => {
    return adapter.getPreflight(options?.configPath);
  });
  ipcMain.handle(DESKTOP_CHANNELS.getThreadHome, async (_event, options?: { configPath?: string }) => {
    return adapter.getThreadHome(options?.configPath);
  });
  ipcMain.handle(
    DESKTOP_CHANNELS.getManagerThread,
    async (_event, options?: { configPath?: string; managerSessionId?: string }) => {
      return adapter.getManagerThread(options?.configPath, options?.managerSessionId);
    }
  );
  ipcMain.handle(DESKTOP_CHANNELS.getSupervisorThread, async (_event, options: { configPath?: string; flowId: string }) => {
    return adapter.getSupervisorThread(options?.configPath, options.flowId);
  });
  ipcMain.handle(
    DESKTOP_CHANNELS.getAgentFocus,
    async (_event, options: { configPath?: string; flowId: string; roleId: string }) => {
      return adapter.getAgentFocus(options?.configPath, options.flowId, options.roleId);
    }
  );
  ipcMain.handle(DESKTOP_CHANNELS.getTemplateTeam, async (_event, options?: { configPath?: string; assetId?: string }) => {
    return adapter.getTemplateTeam(options?.configPath, options?.assetId);
  });
  ipcMain.handle(DESKTOP_CHANNELS.sendManagerMessage, async (_event, payload) => {
    return adapter.sendManagerMessage(payload);
  });
  ipcMain.handle(DESKTOP_CHANNELS.performAction, async (_event, payload) => {
    return adapter.performAction(payload);
  });
  ipcMain.handle(DESKTOP_CHANNELS.chooseConfigPath, async () => {
    const result = await dialog.showOpenDialog(window, {
      title: "Select Butler config",
      properties: ["openFile"],
      filters: [{ name: "JSON", extensions: ["json"] }]
    });
    if (result.canceled || result.filePaths.length === 0) {
      return { canceled: true };
    }
    return {
      canceled: false,
      configPath: result.filePaths[0]
    };
  });
  ipcMain.handle(DESKTOP_CHANNELS.openArtifact, async (_event, request: { target: string }) => {
    const target = String(request?.target || "").trim();
    if (!target) {
      return { opened: false, reason: "empty_target" };
    }
    if (target.startsWith("http://") || target.startsWith("https://")) {
      await shell.openExternal(target);
      return { opened: true };
    }
    const openedPath = await shell.openPath(target);
    if (openedPath) {
      return { opened: false, reason: openedPath };
    }
    return { opened: true };
  });
}
