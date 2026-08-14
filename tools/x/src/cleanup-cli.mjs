#!/usr/bin/env node
import fs from "node:fs/promises";
import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";
import { loadTargets, summarizeTargets } from "./archive.mjs";
import { executeCleanupXurl, normalizeXBackend } from "./x-api.mjs";
import { loadTargetsFromXApi } from "./x-discovery.mjs";

export function parseArgs(argv) {
  const args = { timezone: "Europe/Madrid", execute: false, executeAll: false, resumeApproved: false, api: false, backend: process.env.HERMES_X_BACKEND ?? "xurl", app: process.env.HERMES_X_APP ?? "hermes-ai-presence" };
  for (let i = 0; i < argv.length; i += 1) {
    const token = argv[i];
    if (token === "--archive") args.archivePath = argv[++i];
    else if (token === "--api") args.api = true;
    else if (token === "--start") args.start = argv[++i];
    else if (token === "--end") args.end = argv[++i];
    else if (token === "--timezone") args.timezone = argv[++i];
    else if (token === "--username") args.username = argv[++i];
    else if (token === "--delay-ms") args.delayMs = Number(argv[++i]);
    else if (token === "--limit") args.limit = Number(argv[++i]);
    else if (token === "--profile") args.profileDir = argv[++i];
    else if (token === "--backend") args.backend = argv[++i];
    else if (token === "--app") args.app = argv[++i];
    else if (token === "--execute") args.execute = true;
    else if (token === "--execute-all") { args.execute = true; args.executeAll = true; }
    else if (token === "--resume-approved") args.resumeApproved = true;
    else throw new Error(`Unknown option: ${token}`);
  }
  if ((!args.api && !args.archivePath) || (args.api && args.archivePath) || !args.start || !args.end) throw new Error("Choose exactly one of --api or --archive, and pass --start and --end");
  args.backend = normalizeXBackend(args.backend);
  if (args.api && args.backend !== "xurl") throw new Error("--api discovery requires the xurl backend");
  args.delayMs ??= args.executeAll ? 20000 : 3500;
  if (!Number.isFinite(args.delayMs) || args.delayMs < 2000) throw new Error("--delay-ms must be at least 2000");
  if (args.limit !== undefined && (!Number.isInteger(args.limit) || args.limit < 1)) throw new Error("--limit must be a positive integer");
  if (args.executeAll && args.limit !== undefined) throw new Error("--execute-all cannot be combined with --limit");
  if (args.executeAll && args.delayMs < 18000) throw new Error("--execute-all requires --delay-ms of at least 18000 to respect X write-rate limits");
  if (args.execute && !args.executeAll && (args.limit === undefined || args.limit > 10)) throw new Error("--execute requires --limit between 1 and 10, or use --execute-all after reviewing the preview");
  if (args.resumeApproved && !args.executeAll) throw new Error("--resume-approved is valid only with --execute-all");
  return args;
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const projectRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../..");
  const runtimeRoot = path.resolve(process.env.HERMES_PRESENCE_RUNTIME ?? path.join(projectRoot, "runtime"));
  const workDir = path.join(runtimeRoot, "x-cleanup");
  await fs.mkdir(workDir, { recursive: true });
  const analysis = args.api
    ? await loadTargetsFromXApi({ workDir, start: args.start, end: args.end, timezone: args.timezone, app: args.app, onPage: ({ key, pages, found, done }) => console.error(`[discover] ${key} page ${pages}: ${found} matching${done ? " (complete)" : ""}`) })
    : await loadTargets({ archivePath: args.archivePath, workDir, start: args.start, end: args.end, timezone: args.timezone });
  if (!analysis.account && args.username) analysis.account = { username: args.username };
  const summary = summarizeTargets(analysis);
  const previewFile = path.join(workDir, `preview-${new Date().toISOString().replace(/[:.]/g, "-")}.json`);
  await fs.writeFile(previewFile, JSON.stringify({ summary, targets: analysis.targets }, null, 2));
  console.log(JSON.stringify({ mode: "preview", changed: false, previewFile, summary }, null, 2));
  if (!args.execute) return;
  if (!analysis.account?.username) throw new Error("The archive has no account username; pass --username so the active account can be verified");
  const { executeCleanup } = await import("./x-browser.mjs");
  const result = args.backend === "xurl"
    ? await executeCleanupXurl({ analysis, workDir, delayMs: args.delayMs, limit: args.executeAll ? undefined : args.limit, app: args.app, reuseApproval: args.resumeApproved })
    : await executeCleanup({ analysis, workDir, profileDir: path.resolve(args.profileDir ?? path.join(runtimeRoot, "browser-profile")), delayMs: args.delayMs, limit: args.limit });
  console.log(JSON.stringify({ mode: "execute", result }, null, 2));
}

main().catch((error) => { console.error(`error: ${error.message}`); process.exitCode = 1; });
