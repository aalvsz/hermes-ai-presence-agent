import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { cleanupResult, commandForTarget, executeCleanupXurl, extractXurlPostId, normalizeXBackend, publishApprovedXurl, verifyXurlAccount } from "../src/x-api.mjs";

test("normalizes the official API backend", () => {
  assert.equal(normalizeXBackend(), "xurl");
  assert.equal(normalizeXBackend("browser"), "browser");
  assert.throws(() => normalizeXBackend("cookies"), /xurl or browser/);
});

test("maps cleanup targets to official xurl commands", () => {
  assert.deepEqual(commandForTarget({ kind: "post", id: "1" }), ["delete", "1"]);
  assert.deepEqual(commandForTarget({ kind: "reply", id: "2" }), ["delete", "2"]);
  assert.deepEqual(commandForTarget({ kind: "like", id: "3" }), ["unlike", "3"]);
  assert.deepEqual(commandForTarget({ kind: "repost", id: "4" }), ["unrepost", "4"]);
});

test("accepts only verified cleanup receipts", () => {
  assert.equal(cleanupResult("delete", { data: { deleted: true } }), "deleted");
  assert.equal(cleanupResult("unlike", { data: { liked: false } }), "unliked");
  assert.equal(cleanupResult("unrepost", { data: { retweeted: false } }), "undone");
  assert.throws(() => cleanupResult("delete", { data: { deleted: false } }), /no verified delete receipt/);
});

test("extracts an xurl post receipt", () => {
  assert.equal(extractXurlPostId({ data: { id: "1234567890" } }), "1234567890");
  assert.equal(extractXurlPostId({ data: { id: "not-an-id" } }), null);
});

test("fails closed on an authenticated-account mismatch", async () => {
  const run = async () => ({ data: { username: "other-account" } });
  await assert.rejects(verifyXurlAccount({ expectedUsername: "approved-account", run }), /does not match/);
});

test("publishes only an approved draft and captures the receipt", async () => {
  const calls = [];
  const run = async (args) => {
    calls.push(args);
    if (args.includes("whoami")) return { data: { username: "approved-account" } };
    return { data: { id: "1234567890" } };
  };
  const result = await publishApprovedXurl({
    draft: { id: "draft-1", kind: "tweet", state: "approved", text: "hello", approval: { phrase: "APPROVE POST draft-1" } },
    username: "approved-account",
    run,
  });
  assert.equal(result.postId, "1234567890");
  assert.equal(calls.length, 2);
});

test("rejects an unapproved draft before calling xurl", async () => {
  let calls = 0;
  const run = async () => { calls += 1; return {}; };
  await assert.rejects(publishApprovedXurl({
    draft: { id: "draft-2", kind: "tweet", state: "draft", text: "blocked" },
    username: "approved-account",
    run,
  }), /exact approval/);
  assert.equal(calls, 0);
});

test("rejects cleanup before account lookup when confirmation is wrong", async () => {
  let calls = 0;
  const run = async () => { calls += 1; return {}; };
  await assert.rejects(executeCleanupXurl({
    analysis: { start: "2025-01-01", end: "2025-01-02", account: { username: "approved-account" }, targets: [] },
    workDir: "/unused",
    delayMs: 2000,
    limit: 10,
    run,
    confirm: async () => "NO",
  }), /nothing was changed/);
  assert.equal(calls, 0);
});

test("stores exact-plan approval and resumes without repeating completed actions", async () => {
  const workDir = await fs.mkdtemp(path.join(os.tmpdir(), "x-cleanup-"));
  const analysis = {
    start: "2025-01-01",
    end: "2025-01-02",
    account: { username: "approved-account" },
    targets: [{ kind: "post", id: "1", dateMs: 1, url: "https://x.com/i/web/status/1" }],
  };
  const calls = [];
  const run = async (args) => {
    calls.push(args);
    if (args.includes("whoami")) return { data: { username: "approved-account" } };
    return { data: { deleted: true } };
  };
  await executeCleanupXurl({ analysis, workDir, delayMs: 0, run, confirm: async () => "DELETE RANGE 2025-01-01 2025-01-02" });
  const firstDeleteCount = calls.filter((args) => args.includes("delete")).length;
  await executeCleanupXurl({ analysis, workDir, delayMs: 0, run, reuseApproval: true, confirm: async () => { throw new Error("must not prompt"); } });
  assert.equal(firstDeleteCount, 1);
  assert.equal(calls.filter((args) => args.includes("delete")).length, 1);
});
