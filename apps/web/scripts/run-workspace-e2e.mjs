import { spawnSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";


const currentDirectory = path.dirname(fileURLToPath(import.meta.url));
const webDirectory = path.resolve(currentDirectory, "..");
const repositoryRoot = path.resolve(webDirectory, "../..");
const defaultPython = path.resolve(repositoryRoot, "apps/api/.venv/bin/python");
const python = process.env.E2E_PYTHON ?? defaultPython;
const databaseUrl = process.env.E2E_DATABASE_URL
  ?? "postgresql+psycopg://research:research@127.0.0.1:55432/research_lab_e2e";
const env = {
  ...process.env,
  E2E_DATABASE_URL: databaseUrl,
  E2E_PYTHON: python,
};

function run(command, args, cwd = repositoryRoot) {
  const result = spawnSync(command, args, {
    cwd,
    env,
    stdio: "inherit",
  });
  if (result.error) throw result.error;
  if (result.status !== 0) {
    throw new Error(`${command} ${args.join(" ")} exited with status ${result.status}`);
  }
}

let failed = false;
try {
  run(python, ["scripts/e2e_db.py", "setup"]);
  run("npx", ["playwright", "test", "--config=playwright.writable.config.ts"], webDirectory);
  run("npx", ["playwright", "test", "--config=playwright.readonly.config.ts"], webDirectory);
} catch (error) {
  failed = true;
  console.error(error instanceof Error ? error.message : error);
} finally {
  try {
    run(python, ["scripts/e2e_db.py", "cleanup"]);
  } catch (cleanupError) {
    failed = true;
    console.error(cleanupError instanceof Error ? cleanupError.message : cleanupError);
  }
}

process.exitCode = failed ? 1 : 0;
