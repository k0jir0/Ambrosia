import { rmSync } from "node:fs";
import { join } from "node:path";
import { spawn, spawnSync } from "node:child_process";

rmSync(join(process.cwd(), ".next"), { recursive: true, force: true });

const nextCli = join(process.cwd(), "node_modules", "next", "dist", "bin", "next");
const port = process.env.PORT || "3000";
const child = spawn(process.execPath, [nextCli, "dev", "--port", port], { stdio: "inherit" });

function shutdown(signal) {
  if (process.platform === "win32" && child.pid) {
    spawnSync("taskkill", ["/pid", String(child.pid), "/T", "/F"], { stdio: "ignore" });
    process.exit(0);
  }
  if (!child.killed) {
    child.kill(signal);
  }
  setTimeout(() => process.exit(0), 1000).unref();
}

process.on("SIGINT", () => shutdown("SIGINT"));
process.on("SIGTERM", () => shutdown("SIGTERM"));

child.on("exit", (code) => {
  process.exit(code ?? 0);
});
