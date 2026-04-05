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
  test("launches, attaches config by path, and defaults into the manager thread", async () => {
    const { app, window } = await launchApp();
    try {
      await expect(window).toHaveTitle(/Butler Desktop/);
      await expectDesktopApiReady(window);
      await window.getByLabel("Config Path Fallback").fill(configPath);
      await window.getByRole("button", { name: "Attach Path" }).click();
      await expect(window.getByText(`Config attached: ${configPath}`)).toBeVisible();
      await expect(window.getByRole("heading", { name: "Desktop 线程工作台" })).toBeVisible();
      await expect(window.getByRole("button", { name: /send to manager/i })).toBeVisible();
    } finally {
      await app.close();
    }
  });

  test("starts from New Flow and automatically enters supervisor after manager send", async () => {
    const { app, window } = await launchApp();
    try {
      await expectDesktopApiReady(window);
      await window.getByLabel("Config Path Fallback").fill(configPath);
      await window.getByRole("button", { name: "Attach Path" }).click();
      await window.getByRole("button", { name: /new flow 新建/i }).click();
      await expect(window.getByRole("heading", { name: "新建 Flow" })).toBeVisible();

      await window.getByLabel("Start with Manager").fill("请创建 desktop 视觉升级 flow");
      await window.getByRole("button", { name: /send to manager/i }).click();

      await expect(window.getByRole("heading", { name: "Butler Flow Desktop" })).toBeVisible();
      await expect(window.getByRole("button", { name: "Pause" })).toBeVisible();
    } finally {
      await app.close();
    }
  });

  test("opens templates and agent focus within the new thread-first shell", async () => {
    const { app, window } = await launchApp();
    try {
      await expectDesktopApiReady(window);
      await window.getByLabel("Config Path Fallback").fill(configPath);
      await window.getByRole("button", { name: "Attach Path" }).click();
      await window.getByRole("button", { name: /templates 模板/i }).click();
      await expect(window.getByRole("heading", { name: "Desktop Shell Template" })).toBeVisible();

      await window.getByRole("button", { name: /Butler Flow Desktop/i }).click();
      await expect(window.getByRole("heading", { name: "Butler Flow Desktop" })).toBeVisible();
      await window.getByRole("button", { name: /implementer/i }).last().click();
      await expect(window.getByRole("heading", { name: "implementer · focus" })).toBeVisible();
    } finally {
      await app.close();
    }
  });

  test("keeps manager context aligned after opening a supervisor thread from history", async () => {
    const { app, window } = await launchApp();
    try {
      await expectDesktopApiReady(window);
      await window.getByLabel("Config Path Fallback").fill(configPath);
      await window.getByRole("button", { name: "Attach Path" }).click();
      await window.getByRole("button", { name: /threads 历史/i }).click();
      await window.getByRole("button", { name: /Visual Refresh Flow/i }).last().click();
      await expect(window.getByRole("heading", { name: "Visual Refresh Flow" })).toBeVisible();

      await window.getByRole("button", { name: /manager 管理台/i }).click();
      await expect(window.getByRole("heading", { name: "视觉升级 Manager 线程" })).toBeVisible();
    } finally {
      await app.close();
    }
  });
});
