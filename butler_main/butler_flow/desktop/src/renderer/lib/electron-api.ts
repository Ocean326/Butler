import type { ButlerDesktopApi } from "../../shared/ipc";

export const electronApi: ButlerDesktopApi = {
  getHome: (options) => window.butlerDesktop.getHome(options),
  getFlow: (options) => window.butlerDesktop.getFlow(options),
  getDetail: (options) => window.butlerDesktop.getDetail(options),
  getManageCenter: (options) => window.butlerDesktop.getManageCenter(options),
  getPreflight: (options) => window.butlerDesktop.getPreflight(options),
  performAction: (payload) => window.butlerDesktop.performAction(payload),
  chooseConfigPath: () => window.butlerDesktop.chooseConfigPath(),
  openArtifact: (request) => window.butlerDesktop.openArtifact(request)
};
