import type { ButlerDesktopApi } from "../../shared/ipc";

const DESKTOP_BRIDGE_MISSING_MESSAGE =
  "Butler Desktop bridge unavailable. Open this workbench from the Electron app, or verify preload injection.";

function requireDesktopBridge(): ButlerDesktopApi {
  if (typeof window !== "undefined" && window.butlerDesktop) {
    return window.butlerDesktop;
  }
  throw new Error(DESKTOP_BRIDGE_MISSING_MESSAGE);
}

export function isDesktopBridgeAvailable(): boolean {
  return typeof window !== "undefined" && Boolean(window.butlerDesktop);
}

export const electronApi: ButlerDesktopApi = {
  getHome: (options) => requireDesktopBridge().getHome(options),
  getFlow: (options) => requireDesktopBridge().getFlow(options),
  getDetail: (options) => requireDesktopBridge().getDetail(options),
  getManageCenter: (options) => requireDesktopBridge().getManageCenter(options),
  getPreflight: (options) => requireDesktopBridge().getPreflight(options),
  getThreadHome: (options) => requireDesktopBridge().getThreadHome(options),
  getManagerThread: (options) => requireDesktopBridge().getManagerThread(options),
  getSupervisorThread: (options) => requireDesktopBridge().getSupervisorThread(options),
  getAgentFocus: (options) => requireDesktopBridge().getAgentFocus(options),
  getTemplateTeam: (options) => requireDesktopBridge().getTemplateTeam(options),
  sendManagerMessage: (payload) => requireDesktopBridge().sendManagerMessage(payload),
  performAction: (payload) => requireDesktopBridge().performAction(payload),
  chooseConfigPath: () => requireDesktopBridge().chooseConfigPath(),
  openArtifact: (request) => requireDesktopBridge().openArtifact(request)
};
