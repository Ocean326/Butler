import path from "node:path";
import { app } from "electron";
import { FlowWorkbenchAdapter } from "./adapters/flow-workbench-adapter";
import { registerFlowWorkbenchIpc } from "./ipc/register-flow-workbench-ipc";
import { createMainWindow } from "./window";

function resolveRepoRoot(): string {
  // The compiled Electron main process lives under desktop/dist/main.
  return path.resolve(__dirname, "../../../../../..");
}

function resolveDefaultConfigPath(repoRoot: string): string {
  return path.resolve(repoRoot, "butler_main/butler_bot_code/configs/butler_bot.json");
}

async function bootstrap(): Promise<void> {
  await app.whenReady();
  const repoRoot = resolveRepoRoot();
  const mainWindow = createMainWindow();
  const adapter = new FlowWorkbenchAdapter({ repoRoot });
  registerFlowWorkbenchIpc(mainWindow, adapter, {
    defaultConfigPath: resolveDefaultConfigPath(repoRoot)
  });

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
