import type { ButlerDesktopApi } from "../../shared/ipc";

export const electronApi: ButlerDesktopApi = {
  getHome: (options) => window.butlerDesktop.getHome(options),
  getFlow: (options) => window.butlerDesktop.getFlow(options),
  getDetail: (options) => window.butlerDesktop.getDetail(options),
  getManageCenter: (options) => window.butlerDesktop.getManageCenter(options),
  getPreflight: (options) => window.butlerDesktop.getPreflight(options),
  getThreadHome: (options) => window.butlerDesktop.getThreadHome(options),
  getManagerThread: (options) => window.butlerDesktop.getManagerThread(options),
  getSupervisorThread: (options) => window.butlerDesktop.getSupervisorThread(options),
  getAgentFocus: (options) => window.butlerDesktop.getAgentFocus(options),
  getTemplateTeam: (options) => window.butlerDesktop.getTemplateTeam(options),
  sendManagerMessage: (payload) => window.butlerDesktop.sendManagerMessage(payload),
  performAction: (payload) => window.butlerDesktop.performAction(payload),
  chooseConfigPath: () => window.butlerDesktop.chooseConfigPath(),
  openArtifact: (request) => window.butlerDesktop.openArtifact(request)
};
