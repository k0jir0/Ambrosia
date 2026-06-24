import { existsSync, mkdirSync, openSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { spawn, spawnSync } from "node:child_process";
import { createRequire } from "node:module";

const repoRoot = process.cwd();
const webRoot = join(repoRoot, "apps", "web");
const stateDir = join(repoRoot, ".local");
const pidFile = join(stateDir, "ambrosia-web.pid");
const logFile = join(stateDir, "ambrosia-web.log");
const port = process.env.PORT || "3000";
const url = `http://127.0.0.1:${port}`;
const webRequire = createRequire(join(webRoot, "package.json"));
const nextCli = requireResolveFromWeb("next/dist/bin/next");

function requireResolveFromWeb(modulePath) {
  return webRequire.resolve(modulePath);
}

function ensureStateDir() {
  mkdirSync(stateDir, { recursive: true });
}

function processExists(pid) {
  if (!pid || Number.isNaN(pid)) return false;
  const result = spawnSync("powershell", ["-NoProfile", "-Command", `Get-Process -Id ${pid} | Out-Null`], {
    stdio: "ignore",
  });
  return result.status === 0;
}

async function waitForServer(timeoutMs = 120000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const response = await fetch(url);
      if (response.ok) {
        return true;
      }
    } catch {
      // Keep polling until the server responds or times out.
    }
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  return false;
}

function readPid() {
  if (!existsSync(pidFile)) return null;
  const raw = readFileSync(pidFile, "utf8").trim();
  const pid = Number.parseInt(raw, 10);
  return Number.isNaN(pid) ? null : pid;
}

function clearPidFile() {
  if (existsSync(pidFile)) {
    rmSync(pidFile, { force: true });
  }
}

function ensureBuild() {
  const buildId = join(webRoot, ".next", "BUILD_ID");
  if (existsSync(buildId)) {
    return;
  }

  const build = spawnSync("pnpm.cmd", ["build:web"], {
    cwd: repoRoot,
    stdio: "inherit",
    shell: false,
  });

  if (build.status !== 0) {
    process.exit(build.status ?? 1);
  }
}

async function startServer() {
  ensureStateDir();
  const existingPid = readPid();
  if (existingPid && processExists(existingPid)) {
    const ready = await waitForServer(3000);
    if (ready) {
      console.log(`Ambrosia web is already running at ${url}`);
      return;
    }
    clearPidFile();
  }

  ensureBuild();

  const stdoutFd = openSync(logFile, "a");
  const child = spawn(process.execPath, [nextCli, "start", "--hostname", "0.0.0.0", "--port", port], {
    cwd: webRoot,
    detached: true,
    windowsHide: true,
    stdio: ["ignore", stdoutFd, stdoutFd],
    env: process.env,
  });

  child.on("error", (error) => {
    console.error(`Failed to launch Ambrosia web: ${error.message}`);
    process.exit(1);
  });

  if (!child.pid) {
    console.error("Failed to launch Ambrosia web: no process id returned.");
    process.exit(1);
  }

  child.unref();
  writeFileSync(pidFile, `${child.pid}`, "utf8");

  const ready = await waitForServer();
  if (!ready) {
    console.error(`Ambrosia web did not become ready on ${url}. Check ${logFile}`);
    process.exit(1);
  }

  console.log(`Ambrosia web is running at ${url}`);
  console.log(`PID: ${child.pid}`);
  console.log(`Log: ${logFile}`);
}

function stopServer() {
  const pid = readPid();
  if (!pid || !processExists(pid)) {
    clearPidFile();
    console.log("Ambrosia web is not running.");
    return;
  }

  spawnSync("taskkill", ["/pid", String(pid), "/T", "/F"], { stdio: "ignore" });
  clearPidFile();
  console.log("Ambrosia web stopped.");
}

async function statusServer() {
  const pid = readPid();
  const alive = pid ? processExists(pid) : false;
  const ready = alive ? await waitForServer(3000) : false;

  if (alive && ready) {
    console.log(`Ambrosia web is running at ${url}`);
    console.log(`PID: ${pid}`);
    console.log(`Log: ${logFile}`);
    return;
  }

  if (alive && !ready) {
    console.log(`Ambrosia web process exists (PID ${pid}) but is not responding on ${url}`);
    console.log(`Log: ${logFile}`);
    return;
  }

  console.log("Ambrosia web is not running.");
}

const command = process.argv[2] || "start";
try {
  if (command === "start") {
    await startServer();
  } else if (command === "stop") {
    stopServer();
  } else if (command === "status") {
    await statusServer();
  } else {
    console.error(`Unknown command: ${command}`);
    process.exit(1);
  }
} catch (error) {
  console.error(error instanceof Error ? error.message : String(error));
  process.exit(1);
}
