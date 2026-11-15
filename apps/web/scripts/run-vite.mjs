import { execFileSync, spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { resolve } from "node:path";

const root = process.cwd();
const args = process.argv.slice(2);
let workingRoot = root;
let vite = resolve(root, "node_modules/vite/bin/vite.js");
let drive = null;

if (process.platform === "win32" && root.includes("#")) {
  const workspaceRoot = resolve(root, "../..");
  const appPath = resolve(workspaceRoot, "apps/web");
  for (const letter of "ZYXWVUTSRQPONMLKJIHGFED") {
    if (!existsSync(`${letter}:\\`)) {
      drive = `${letter}:`;
      break;
    }
  }
  if (!drive) throw new Error("Cannot find an unused drive letter to run Vite from this # path.");
  execFileSync("subst", [drive, workspaceRoot], { stdio: "ignore" });
  workingRoot = resolve(`${drive}\\`, "apps/web");
  vite = resolve(workingRoot, "node_modules/vite/bin/vite.js");
}

const child = spawn(process.execPath, [vite, ...args], {
  cwd: workingRoot,
  env: process.env,
  stdio: "inherit",
});
let cleaned = false;

function cleanup() {
  if (cleaned || !drive) return;
  cleaned = true;
  execFileSync("subst", [drive, "/D"], { stdio: "ignore" });
}

child.on("error", (error) => {
  cleanup();
  throw error;
});
child.on("exit", (code, signal) => {
  cleanup();
  process.exitCode = code ?? (signal ? 1 : 0);
});
for (const signal of ["SIGINT", "SIGTERM"]) {
  process.on(signal, () => child.kill(signal));
}
