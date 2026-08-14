import fs from "node:fs/promises";
import path from "node:path";
import readline from "node:readline/promises";
import { chromium } from "playwright";

const RATE_LIMIT = /rate limit|try again later|too many requests|límite de solicitudes|inténtalo de nuevo más tarde/i;
const CHALLENGE = /captcha|verify you are human|verifica que eres humano|arkose/i;
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

async function atomicJson(filePath, value) {
  const temporary = `${filePath}.tmp`;
  await fs.writeFile(temporary, JSON.stringify(value, null, 2));
  await fs.rename(temporary, filePath);
}

async function terminalPrompt(question) {
  if (!process.stdin.isTTY) throw new Error("This operation requires an interactive terminal");
  const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
  try { return (await rl.question(question)).trim(); }
  finally { rl.close(); }
}

async function assertPageSafe(page) {
  const body = (await page.locator("body").innerText({ timeout: 15_000 }).catch(() => "")).slice(0, 12_000);
  if (RATE_LIMIT.test(body)) throw new Error("X applied a temporary rate limit; state is saved, stop and retry later");
  if (CHALLENGE.test(body)) throw new Error("X presented a human verification challenge; stop and let the user take over");
}

async function ensureLoggedIn(page, interactive = false) {
  await page.goto("https://x.com/home", { waitUntil: "domcontentloaded", timeout: 45_000 });
  await assertPageSafe(page);
  const account = page.locator('[data-testid="SideNav_AccountSwitcher_Button"]');
  if (await account.isVisible().catch(() => false)) return;
  if (!interactive) throw new Error("X browser profile is not logged in; run publish-cli.mjs login first");
  const answer = await terminalPrompt("Log in to X in the visible browser, then type READY: ");
  if (answer !== "READY") throw new Error("X login was not confirmed");
  await page.goto("https://x.com/home", { waitUntil: "domcontentloaded", timeout: 45_000 });
  if (!await account.isVisible().catch(() => false)) throw new Error("Could not verify X login");
}

async function currentUsername(page) {
  const account = page.locator('[data-testid="SideNav_AccountSwitcher_Button"]');
  const text = await account.innerText({ timeout: 10_000 });
  return text.match(/@([A-Za-z0-9_]{1,15})/)?.[1] ?? null;
}

async function verifyExpectedAccount(page, expectedUsername) {
  const expected = String(expectedUsername ?? "").replace(/^@/, "").toLowerCase();
  if (!expected) throw new Error("An explicit X username is required before any write action");
  const actual = await currentUsername(page);
  if (!actual) throw new Error("Could not read the active X username; stop before any write action");
  if (actual.toLowerCase() !== expected) throw new Error(`Active X account @${actual} does not match the approved account @${expected}`);
  return actual;
}

export async function login({ profileDir }) {
  await fs.mkdir(profileDir, { recursive: true });
  const context = await chromium.launchPersistentContext(profileDir, { headless: false, viewport: { width: 1280, height: 900 } });
  try {
    const page = context.pages()[0] ?? await context.newPage();
    await ensureLoggedIn(page, true);
    return { username: await currentUsername(page) };
  }
  finally { await context.close(); }
}

async function targetArticle(page, id) {
  const matching = page.locator("article").filter({ has: page.locator(`a[href*="/status/${id}"]`) }).first();
  if (await matching.isVisible({ timeout: 10_000 }).catch(() => false)) return matching;
  return null;
}

async function actOnTarget(page, target) {
  await page.goto(target.url, { waitUntil: "domcontentloaded", timeout: 45_000 });
  await assertPageSafe(page);
  let article = await targetArticle(page, target.id);
  if (!article && target.kind === "repost") {
    const redirectedId = new URL(page.url()).pathname.match(/\/status\/(\d+)/)?.[1];
    if (redirectedId && redirectedId !== target.id) article = await targetArticle(page, redirectedId);
  }
  if (!article) return "not-found";
  if (target.kind === "like") {
    const button = article.locator('[data-testid="unlike"]').first();
    if (!await button.isVisible().catch(() => false)) return "already-unliked";
    await button.click(); return "unliked";
  }
  if (target.kind === "repost") {
    const button = article.locator('[data-testid="unretweet"]').first();
    if (!await button.isVisible().catch(() => false)) return "already-undone";
    await button.click();
    const undo = page.getByRole("menuitem").filter({ hasText: /Undo (Repost|Retweet)|Deshacer (repost|retweet)/i }).first();
    if (!await undo.isVisible({ timeout: 3_000 }).catch(() => false)) return "undo-control-missing";
    await undo.click(); return "undone";
  }
  const caret = article.locator('[data-testid="caret"]').first();
  if (!await caret.isVisible().catch(() => false)) return "not-found";
  await caret.click();
  const deleteItem = page.getByRole("menuitem").filter({ hasText: /Delete|Eliminar/i }).first();
  if (!await deleteItem.isVisible({ timeout: 3_000 }).catch(() => false)) { await page.keyboard.press("Escape").catch(() => {}); return "already-gone-or-not-owned"; }
  await deleteItem.click();
  const confirm = page.locator('[data-testid="confirmationSheetConfirm"]');
  if (!await confirm.isVisible({ timeout: 3_000 }).catch(() => false)) return "confirmation-missing";
  await confirm.click();
  return "deleted";
}

export async function executeCleanup({ analysis, workDir, profileDir, delayMs, limit }) {
  const required = `DELETE RANGE ${analysis.start} ${analysis.end}`;
  const phrase = await terminalPrompt(`Type exactly "${required}" to continue: `);
  if (phrase !== required) throw new Error("Confirmation did not match; nothing was changed");
  await fs.mkdir(profileDir, { recursive: true });
  const context = await chromium.launchPersistentContext(profileDir, { headless: false, viewport: { width: 1280, height: 900 } });
  const page = context.pages()[0] ?? await context.newPage();
  const stateFile = path.join(workDir, "execution-state.json");
  let state = { start: analysis.start, end: analysis.end, completed: {}, events: [] };
  try { state = JSON.parse(await fs.readFile(stateFile, "utf8")); }
  catch (error) { if (error.code !== "ENOENT") throw error; }
  if (state.start !== analysis.start || state.end !== analysis.end) throw new Error("Existing execution state belongs to a different date range");
  try {
    await ensureLoggedIn(page, true);
    await verifyExpectedAccount(page, analysis.account?.username);
    const order = { like: 0, repost: 1, reply: 2, post: 3 };
    const pending = analysis.targets.filter((target) => !state.completed[`${target.kind}:${target.id}`]).sort((a, b) => order[a.kind] - order[b.kind] || a.dateMs - b.dateMs).slice(0, limit ?? Number.POSITIVE_INFINITY);
    for (let index = 0; index < pending.length; index += 1) {
      const target = pending[index];
      const key = `${target.kind}:${target.id}`;
      const result = await actOnTarget(page, target);
      if (["undo-control-missing", "confirmation-missing"].includes(result)) throw new Error(`Unexpected X control state for ${key}: ${result}`);
      state.completed[key] = { at: new Date().toISOString(), result };
      state.events.push({ at: new Date().toISOString(), key, result, url: target.url });
      await atomicJson(stateFile, state);
      console.log(`[${index + 1}/${pending.length}] ${key}: ${result}`);
      await sleep(delayMs);
    }
    return { stateFile, completed: Object.keys(state.completed).length };
  } finally { await context.close(); }
}

function findNamedId(value, names) {
  if (!value || typeof value !== "object") return null;
  for (const [key, child] of Object.entries(value)) {
    if (names.has(key) && typeof child === "string" && /^\d+$/.test(child)) return child;
  }
  for (const child of Object.values(value)) {
    const found = findNamedId(child, names);
    if (found) return found;
  }
  return null;
}

export function extractCreatedPostId(payload) {
  if (payload?.data && typeof payload.data.id === "string" && /^\d+$/.test(payload.data.id)) return payload.data.id;
  if (!payload || typeof payload !== "object") return null;
  for (const [key, child] of Object.entries(payload)) {
    if (key === "tweet_results") {
      const found = findNamedId(child, new Set(["rest_id", "id_str"]));
      if (found) return found;
    }
    const nested = extractCreatedPostId(child);
    if (nested) return nested;
  }
  return null;
}

export async function publishApproved({ draft, profileDir, username, onSubmitting = async () => {} }) {
  if (draft.state !== "approved" || draft.approval?.phrase !== `APPROVE POST ${draft.id}`) throw new Error("Draft does not carry the exact approval record");
  if (draft.kind !== "tweet") throw new Error("Browser publisher currently supports single tweets only");
  const context = await chromium.launchPersistentContext(profileDir, { headless: false, viewport: { width: 1280, height: 900 } });
  try {
    const page = context.pages()[0] ?? await context.newPage();
    await ensureLoggedIn(page, false);
    await verifyExpectedAccount(page, username);
    await page.goto("https://x.com/compose/post", { waitUntil: "domcontentloaded", timeout: 45_000 });
    await assertPageSafe(page);
    const editor = page.locator('[data-testid="tweetTextarea_0"]');
    if (!await editor.isVisible({ timeout: 10_000 }).catch(() => false)) throw new Error("X compose editor was not found; stop instead of guessing selectors");
    await editor.fill(draft.text);
    const button = page.locator('[data-testid="tweetButton"], [data-testid="tweetButtonInline"]').first();
    if (!await button.isEnabled({ timeout: 5_000 }).catch(() => false)) throw new Error("X post button is not enabled");
    let resolvePostId;
    const postIdPromise = new Promise((resolve) => { resolvePostId = resolve; });
    page.on("response", async (response) => {
      if (!/CreateTweet|\/2\/tweets(?:\?|$)/i.test(response.url()) || !response.ok()) return;
      try {
        const postId = extractCreatedPostId(await response.json());
        if (postId) resolvePostId(postId);
      } catch {}
    });
    await onSubmitting();
    await button.click();
    const postId = await Promise.race([postIdPromise, sleep(20_000).then(() => null)]);
    await assertPageSafe(page);
    if (!postId) {
      const error = new Error("X accepted the click but no post ID was captured; publication outcome is unknown and must not be retried automatically");
      error.code = "POST_RECEIPT_UNVERIFIED";
      error.pageUrl = page.url();
      throw error;
    }
    return { receipt: `https://x.com/i/web/status/${postId}`, postId, postedAt: new Date().toISOString() };
  } finally { await context.close(); }
}
