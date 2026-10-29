import { defineConfig, firefox } from "@playwright/test";
import path from "node:path";
export default defineConfig({
  testDir: "tests",
  workers: 1,
  timeout: 90000,
  fullyParallel: false,
  use: {
    baseURL: "https://127.0.0.1:8443",
    headless: true,
    browserName:
      process.env.HAVEN_BROWSER === "firefox" ? "firefox" : "chromium",
    trace: "off",
    launchOptions: {
      executablePath:
        process.env.HAVEN_BROWSER === "firefox"
          ? firefox.executablePath()
          : "/usr/bin/google-chrome",
      args:
        process.env.HAVEN_BROWSER === "firefox"
          ? []
          : ["--use-fake-device-for-media-stream"],
      env: {
        PATH: process.env.PATH || "/usr/bin:/bin",
        LANG: "C.UTF-8",
        HOME: path.resolve("../../.local/browser-home"),
        LD_LIBRARY_PATH: path.resolve(
          "../../.local/browser-libs/usr/lib/x86_64-linux-gnu",
        ),
      },
    },
  },
  reporter: [
    ["list"],
    ["json", { outputFile: "../../docs/evidence/browser-results.json" }],
  ],
});
