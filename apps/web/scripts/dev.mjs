import { rmSync } from "node:fs";
import { join } from "node:path";
import { spawn } from "node:child_process";

rmSync(join(process.cwd(), ".next"), { recursive: true, force: true });

const child = spawn("next dev --port 3000", {
  stdio: "inherit",
  shell: true
});

child.on("exit", (code) => {
  process.exit(code ?? 0);
});