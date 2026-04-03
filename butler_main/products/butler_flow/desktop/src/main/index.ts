import path from "node:path";
import { app } from "electron";
import { FlowWorkbenchAdapter } from "./adapters/flow-workbench-adapter";
import { registerFlowWorkbenchIpc } from "./ipc/register-flow-workbench-ipc";
import { createMainWindow } from "./window";

function resolveRepoRoot(): string {
  return path.resolve(__dirname, "../../../../..");
}

async function bootstrap(): Promise<void> {
  await app.whenReady();
  const mainWindow = createMainWindow();
  const adapter = new FlowWorkbenchAdapter({ repoRoot: resolveRepoRoot() });
  registerFlowWorkbenchIpc(mainWindow, adapter);

  app.on("activate", () => {
    if (mainWindow.isDestroyed()) {
      return;
    }
    if (!mainWindow.isVisible()) {
      mainWindow.show();
    }
  });
}

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});

void bootstrap();
