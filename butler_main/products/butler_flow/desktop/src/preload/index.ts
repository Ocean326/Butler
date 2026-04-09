import { contextBridge, ipcRenderer } from "electron";
import { DESKTOP_CHANNELS } from "../main/ipc/channels";
import type { ButlerDesktopApi } from "../shared/ipc";

const api: ButlerDesktopApi = {
  getHome: (options) => ipcRenderer.invoke(DESKTOP_CHANNELS.getHome, options),
  getFlow: (options) => ipcRenderer.invoke(DESKTOP_CHANNELS.getFlow, options),
  getDetail: (options) => ipcRenderer.invoke(DESKTOP_CHANNELS.getDetail, options),
  getManageCenter: (options) => ipcRenderer.invoke(DESKTOP_CHANNELS.getManageCenter, options),
  getPreflight: (options) => ipcRenderer.invoke(DESKTOP_CHANNELS.getPreflight, options),
  getThreadHome: (options) => ipcRenderer.invoke(DESKTOP_CHANNELS.getThreadHome, options),
  getManagerThread: (options) => ipcRenderer.invoke(DESKTOP_CHANNELS.getManagerThread, options),
  getSupervisorThread: (options) => ipcRenderer.invoke(DESKTOP_CHANNELS.getSupervisorThread, options),
  getAgentFocus: (options) => ipcRenderer.invoke(DESKTOP_CHANNELS.getAgentFocus, options),
  getTemplateTeam: (options) => ipcRenderer.invoke(DESKTOP_CHANNELS.getTemplateTeam, options),
  getDefaultConfigPath: () => ipcRenderer.invoke(DESKTOP_CHANNELS.getDefaultConfigPath),
  sendManagerMessage: (payload) => ipcRenderer.invoke(DESKTOP_CHANNELS.sendManagerMessage, payload),
  performAction: (payload) => ipcRenderer.invoke(DESKTOP_CHANNELS.performAction, payload),
  chooseConfigPath: () => ipcRenderer.invoke(DESKTOP_CHANNELS.chooseConfigPath),
  openArtifact: (request) => ipcRenderer.invoke(DESKTOP_CHANNELS.openArtifact, request)
};

contextBridge.exposeInMainWorld("butlerDesktop", api);
