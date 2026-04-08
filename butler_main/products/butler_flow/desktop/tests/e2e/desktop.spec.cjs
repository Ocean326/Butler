const path = require("node:path");
const { _electron: electron, test, expect } = require("@playwright/test");

const desktopDir = path.resolve(__dirname, "../..");
const configPath = "/tmp/butler/mock/butler_bot.json";

async function launchApp() {
  const app = await electron.launch({
    args: [".", "--no-sandbox"],
    cwd: desktopDir,
    env: {
      ...process.env,
      BUTLER_DESKTOP_USE_MOCK: "1"
    }
  });
  const window = await app.firstWindow();
  return { app, window };
}

async function expectDesktopApiReady(window) {
  await expect
    .poll(async () => {
      return window.evaluate(() => typeof window.butlerDesktop);
    })
    .toBe("object");
}

test.describe("Butler Desktop Electron", () => {
  test("launches, attaches config by path, and opens the manager thread", async () => {
    const { app, window } = await launchApp();
    try {
      await expect(window).toHaveTitle(/Butler Desktop/);
      await expectDesktopApiReady(window);
      await window.getByLabel("Config Path Fallback").fill(configPath);
      await window.getByRole("button", { name: "Attach Path" }).click();
      await expect(window.getByText(`Config attached: ${configPath}`)).toBeVisible();
      await expect(window.getByRole("button", { name: /Ship Butler Desktop/i })).toBeVisible();

      await window.getByRole("button", { name: /Ship Butler Desktop/i }).click();
      await expect(window.getByRole("heading", { name: "Ship Butler Desktop", level: 2 })).toBeVisible();
      await expect(window.getByRole("button", { name: "Pause", exact: true })).toBeVisible();
    } finally {
      await app.close();
    }
  });

  test("switches to the studio lens inside the same thread", async () => {
    const { app, window } = await launchApp();
    try {
      await expectDesktopApiReady(window);
      await window.getByLabel("Config Path Fallback").fill(configPath);
      await window.getByRole("button", { name: "Attach Path" }).click();
      await window.getByRole("button", { name: /Ship Butler Desktop/i }).click();
      await window.getByRole("button", { name: "Studio", exact: true }).click();

      await expect(window.getByText("Desktop Shell V1").first()).toBeVisible();
      await expect(window.getByText(/Promote the shell only after bridge and real payloads render cleanly/i).first()).toBeVisible();
    } finally {
      await app.close();
    }
  });
});
