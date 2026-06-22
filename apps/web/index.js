/* eslint-disable @typescript-eslint/no-require-imports */
const { spawn } = require("node:child_process");

const nextCli = require.resolve("next/dist/bin/next", { paths: [__dirname, process.cwd()] });
const port = process.env.PORT || "3000";

const child = spawn(
  process.execPath,
  [nextCli, "start", "--hostname", "0.0.0.0", "--port", port],
  {
    cwd: __dirname,
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
