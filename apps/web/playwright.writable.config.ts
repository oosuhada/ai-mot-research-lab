import path from "node:path";
import { fileURLToPath } from "node:url";

import { defineConfig, devices } from "@playwright/test";


const currentDirectory = path.dirname(fileURLToPath(import.meta.url));
const apiDirectory = path.resolve(currentDirectory, "../api");
const repositoryRoot = path.resolve(currentDirectory, "../..");
const defaultPython = path.join(apiDirectory, ".venv", "bin", "python");
const python = process.env.E2E_PYTHON ?? defaultPython;
const databaseUrl = process.env.E2E_DATABASE_URL
  ?? "postgresql+psycopg://research:research@127.0.0.1:55432/research_lab_e2e";
const apiBaseUrl = "http://127.0.0.1:18100";
const webBaseUrl = "http://127.0.0.1:13100";

export default defineConfig({
  testDir: "./e2e",
  testMatch: "workspace.spec.ts",
  retries: 0,
  workers: 1,
  use: {
    baseURL: webBaseUrl,
    trace: "retain-on-failure",
  },
  webServer: [
    {
      command: `${python} -m uvicorn research_lab.main:app --host 127.0.0.1 --port 18100`,
      cwd: apiDirectory,
      url: `${apiBaseUrl}/health`,
      reuseExistingServer: false,
      timeout: 120_000,
      env: {
        ...process.env,
        DATABASE_URL: databaseUrl,
        APP_ENVIRONMENT: "test",
        READ_ONLY_MODE: "false",
        PUBLIC_API_HOSTS: "",
        EMBEDDING_PROVIDER: "local_hash",
      },
    },
    {
      command: "npm run dev -- --hostname 127.0.0.1 --port 13100",
      cwd: currentDirectory,
      url: webBaseUrl,
      reuseExistingServer: false,
      timeout: 120_000,
      env: {
        ...process.env,
        INTERNAL_API_BASE_URL: apiBaseUrl,
        NEXT_PUBLIC_WORKSPACE_MODE: "personal",
      },
    },
  ],
  projects: [
    {
      name: "chromium-writable",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  outputDir: path.join(repositoryRoot, "artifacts", "playwright", "writable"),
});
