const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { _electron: electron, test, expect } = require("@playwright/test");

const desktopDir = path.resolve(__dirname, "../..");
const configPath = "/tmp/butler/mock/butler_bot.json";

async function launchApp() {
  const isolatedHome = fs.mkdtempSync(path.join(os.tmpdir(), "butler-desktop-e2e-"));
  const app = await electron.launch({
    args: [".", "--no-sandbox"],
    cwd: desktopDir,
    env: {
      ...process.env,
      HOME: isolatedHome,
      BUTLER_DESKTOP_USE_MOCK: "1",
      XDG_CONFIG_HOME: isolatedHome,
      XDG_DATA_HOME: isolatedHome
    }
  });
  const window = await app.firstWindow();
  return { app, window, isolatedHome };
}

async function expectDesktopApiReady(window) {
  await expect
    .poll(async () => {
      return window.evaluate(() => typeof window.butlerDesktop);
    })
    .toBe("object");
}

test.describe("Butler Desktop Electron", () => {
  test("launches, attaches config by path, and opens the workbench", async () => {
    const { app, window, isolatedHome } = await launchApp();
    try {
      await expect(window).toHaveTitle(/Butler Desktop/);
      await expectDesktopApiReady(window);
      await window.getByLabel("Config Path Fallback").fill(configPath);
      await window.getByRole("button", { name: "Attach Path" }).click();
      await expect(window.getByText(`Config attached: ${configPath}`)).toBeVisible();
      await expect(window.getByRole("button", { name: /flow_mock_desktop/i })).toBeVisible();

      await window.getByRole("button", { name: /flow_mock_desktop/i }).click();
      await expect(window.getByRole("heading", { name: "Ship Butler Desktop" })).toBeVisible();
      await expect(window.getByRole("button", { name: "Pause" })).toBeVisible();
    } finally {
      await app.close();
      fs.rmSync(isolatedHome, { recursive: true, force: true });
    }
  });

  test("navigates to manage center after config attach", async () => {
    const { app, window, isolatedHome } = await launchApp();
    try {
      await expectDesktopApiReady(window);
      await window.getByLabel("Config Path Fallback").fill(configPath);
      await window.getByRole("button", { name: "Attach Path" }).click();
      await window.getByRole("button", { name: "Manage" }).click();

      await expect(window.getByRole("heading", { name: "Assets and execution guidance" })).toBeVisible();
      await expect(window.getByRole("heading", { name: "Desktop Shell V1" })).toBeVisible();
    } finally {
      await app.close();
      fs.rmSync(isolatedHome, { recursive: true, force: true });
    }
  });
});
