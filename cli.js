#!/usr/bin/env node
import { spawnSync, execSync } from "node:child_process";
import { basename } from "node:path";
import process from "node:process";

const BIN_NAME = basename(process.argv[1] || "ai-mcp");
const PKG = "ai-mcp-server";

function fail(msg) {
  process.stderr.write(`\x1b[31m${PKG}\x1b[0m: ${msg}\n`);
  process.exit(1);
}

function info(msg) {
  process.stderr.write(`\x1b[36m${PKG}\x1b[0m: ${msg}\n`);
}

function hasUv() {
  try { execSync("uv --version", { stdio: "ignore" }); return true; }
  catch { return false; }
}

function isInstalled() {
  try {
    const r = execSync("uv tool list --color never", { encoding: "utf-8" });
    return r.includes(PKG);
  } catch { return false; }
}

// -- main --
if (!hasUv()) {
  fail("uv is required. Install: https://docs.astral.sh/uv/getting-started/installation/");
}

if (!isInstalled()) {
  info(`uv tool install ${PKG} …`);
  const r = spawnSync("uv", ["tool", "install", PKG], { stdio: "inherit" });
  if (r.status !== 0) fail(`auto-install failed (exit ${r.status})`);
}

const userArgs = process.argv.slice(2);
let entry, args;

switch (BIN_NAME) {
  case "ai-mcp-ui":
    entry = "ai-mcp";
    args = ["ui", ...userArgs];
    break;
  case "ai-mcp-server":
    entry = "ai-mcp-server";
    args = userArgs;
    break;
  default: // "ai-mcp"
    entry = "ai-mcp";
    args = userArgs;
}

const result = spawnSync("uv", ["tool", "run", "--from", PKG, entry, "--", ...args], {
  stdio: "inherit",
});
process.exit(result.status ?? 1);
