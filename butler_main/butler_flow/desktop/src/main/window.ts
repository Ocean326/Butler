import path from "node:path";
import { BrowserWindow, app } from "electron";

export function createMainWindow(): BrowserWindow {
  const window = new BrowserWindow({
    width: 1600,
    height: 980,
    minWidth: 1260,
    minHeight: 760,
    backgroundColor: "#0a0d10",
    title: "Butler Desktop",
    webPreferences: {
      contextIsolation: true,
      preload: path.join(app.getAppPath(), "dist/preload/index.js")
    }
  });

  const devServerUrl = process.env.VITE_DEV_SERVER_URL;
  if (devServerUrl) {
    void window.loadURL(devServerUrl);
    window.webContents.openDevTools({ mode: "detach" });
  } else {
    void window.loadFile(path.join(app.getAppPath(), "dist/renderer/index.html"));
  }

  return window;
}
