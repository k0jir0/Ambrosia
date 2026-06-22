import { spawn, spawnSync } from "node:child_process";
import { rmSync } from "node:fs";
import { join } from "node:path";

const root = process.cwd();
const url = "http://127.0.0.1:3000";
const nextCli = join(root, "node_modules", "next", "dist", "bin", "next");
const playwrightCli = join(root, "node_modules", "@playwright", "test", "cli.js");

rmSync(join(root, ".next"), { recursive: true, force: true });

const server = spawn(process.execPath, [nextCli, "dev", "--port", "3000"], {
  cwd: root,
  stdio: "inherit"
});

function killServer() {
  if (process.platform === "win32" && server.pid) {
    spawnSync("taskkill", ["/pid", String(server.pid), "/T", "/F"], { stdio: "ignore" });
    return;
  }
  if (!server.killed) {
    server.kill("SIGTERM");
  }
}

async function waitForServer() {
  const deadline = Date.now() + 120_000;
  while (Date.now() < deadline) {
    try {
      const response = await fetch(url);
      if (response.ok) return;
    } catch {
      // Keep polling until Next is ready.
    }
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  throw new Error(`Timed out waiting for ${url}`);
}

try {
  await waitForServer();
  const result = spawnSync(process.execPath, [playwrightCli, "test"], {
    cwd: root,
    stdio: "inherit",
    env: { ...process.env, PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD: "1" }
  });
  killServer();
  process.exit(result.status ?? 1);
} catch (error) {
  killServer();
  console.error(error instanceof Error ? error.message : error);
  process.exit(1);
}
