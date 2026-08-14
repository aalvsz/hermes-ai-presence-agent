import fs from "node:fs/promises";
import path from "node:path";
import readline from "node:readline/promises";
import { execFile } from "node:child_process";
import { promisify } from "node:util";

const execFileAsync = promisify(execFile);
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

export function normalizeXBackend(value = "xurl") {
  const backend = String(value).trim().toLowerCase();
  if (!["xurl", "browser"].includes(backend)) throw new Error("--backend must be xurl or browser");
  return backend;
}

export function commandForTarget(target) {
  if (["post", "reply"].includes(target.kind)) return ["delete", String(target.id)];
  if (target.kind === "like") return ["unlike", String(target.id)];
  if (target.kind === "repost") return ["unrepost", String(target.id)];
  throw new Error(`Unsupported X cleanup target kind: ${target.kind}`);
}

export function extractXurlPostId(payload) {
  const id = payload?.data?.id ?? payload?.id;
  return typeof id === "string" && /^\d+$/.test(id) ? id : null;
}

async function terminalPrompt(question) {
  if (!process.stdin.isTTY) throw new Error("This operation requires an interactive terminal");
  const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
  try { return (await rl.question(question)).trim(); }
  finally { rl.close(); }
}

async function atomicJson(filePath, value) {
  const temporary = `${filePath}.tmp`;
  await fs.writeFile(temporary, JSON.stringify(value, null, 2));
  await fs.rename(temporary, filePath);
}

export async function runXurl(args) {
  let stdout;
  try {
    ({ stdout } = await execFileAsync("xurl", args, { encoding: "utf8", maxBuffer: 8 * 1024 * 1024 }));
  } catch (error) {
    const message = String(error.stderr || error.message || "xurl failed").trim().split("\n").slice(-3).join(" ");
    throw new Error(`xurl command failed without changing local approval state: ${message}`);
  }
  const trimmed = stdout.trim();
  if (!trimmed) return {};
  try { return JSON.parse(trimmed); }
  catch { throw new Error("xurl returned a non-JSON response; stop instead of guessing the result"); }
}

export async function verifyXurlAccount({ expectedUsername, app = "hermes-ai-presence", run = runXurl }) {
  const expected = String(expectedUsername ?? "").replace(/^@/, "").toLowerCase();
  if (!expected) throw new Error("An explicit X username is required before any write action");
  const payload = await run(["--app", app, "whoami"]);
  const actual = String(payload?.data?.username ?? "").replace(/^@/, "");
  if (!actual) throw new Error("xurl could not verify the authenticated X account");
  if (actual.toLowerCase() !== expected) throw new Error("The authenticated X account does not match the approved account");
  return actual;
}

export async function publishApprovedXurl({ draft, username, app = "hermes-ai-presence", run = runXurl, onSubmitting = async () => {} }) {
  if (draft.state !== "approved" || draft.approval?.phrase !== `APPROVE POST ${draft.id}`) throw new Error("Draft does not carry the exact approval record");
  if (draft.kind !== "tweet") throw new Error("The X publisher currently supports single tweets only");
  await verifyXurlAccount({ expectedUsername: username, app, run });
  await onSubmitting();
  const payload = await run(["--app", app, "post", draft.text, "--auth", "oauth2", "--username", String(username).replace(/^@/, "")]);
  const postId = extractXurlPostId(payload);
  if (!postId) {
    const error = new Error("X returned no post ID; publication outcome is unknown and must not be retried automatically");
    error.code = "POST_RECEIPT_UNVERIFIED";
    throw error;
  }
  return { receipt: `https://x.com/i/web/status/${postId}`, postId, postedAt: new Date().toISOString() };
}

export async function executeCleanupXurl({ analysis, workDir, delayMs, limit, app = "hermes-ai-presence", run = runXurl, confirm = terminalPrompt }) {
  const required = `DELETE RANGE ${analysis.start} ${analysis.end}`;
  const phrase = await confirm(`Type exactly "${required}" to continue: `);
  if (phrase !== required) throw new Error("Confirmation did not match; nothing was changed");
  await verifyXurlAccount({ expectedUsername: analysis.account?.username, app, run });
  const stateFile = path.join(workDir, "execution-state.json");
  let state = { start: analysis.start, end: analysis.end, completed: {}, events: [] };
  try { state = JSON.parse(await fs.readFile(stateFile, "utf8")); }
  catch (error) { if (error.code !== "ENOENT") throw error; }
  if (state.start !== analysis.start || state.end !== analysis.end) throw new Error("Existing execution state belongs to a different date range");
  const order = { like: 0, repost: 1, reply: 2, post: 3 };
  const pending = analysis.targets
    .filter((target) => !state.completed[`${target.kind}:${target.id}`])
    .sort((a, b) => order[a.kind] - order[b.kind] || a.dateMs - b.dateMs)
    .slice(0, limit ?? Number.POSITIVE_INFINITY);
  for (let index = 0; index < pending.length; index += 1) {
    const target = pending[index];
    const key = `${target.kind}:${target.id}`;
    const [command, id] = commandForTarget(target);
    await run(["--app", app, command, id, "--auth", "oauth2", "--username", String(analysis.account.username).replace(/^@/, "")]);
    const result = command === "delete" ? "deleted" : command === "unlike" ? "unliked" : "undone";
    state.completed[key] = { at: new Date().toISOString(), result };
    state.events.push({ at: new Date().toISOString(), key, result, url: target.url });
    await atomicJson(stateFile, state);
    console.log(`[${index + 1}/${pending.length}] ${key}: ${result}`);
    await sleep(delayMs);
  }
  return { stateFile, completed: Object.keys(state.completed).length };
}
