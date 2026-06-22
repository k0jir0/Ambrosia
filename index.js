const { spawn } = require("node:child_process");
const { join } = require("node:path");

const webRoot = join(__dirname, "apps", "web");
const nextCli = require.resolve("next/dist/bin/next", { paths: [webRoot, __dirname] });
const port = process.env.PORT || "3000";

const child = spawn(
  process.execPath,
  [nextCli, "start", "--hostname", "0.0.0.0", "--port", port],
  {
    cwd: webRoot,
    stdio: "inherit",
    env: process.env,
  },
);

child.on("exit", (code, signal) => {
  if (signal) {
    process.kill(process.pid, signal);
    return;
  }
  process.exit(code || 0);
});
