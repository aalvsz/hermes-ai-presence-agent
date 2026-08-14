import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { loadTargets, snowflakeDateMs, summarizeTargets, validateArchiveEntryName } from "../src/archive.mjs";

async function fixture() {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), "x-range-test-"));
  const data = path.join(root, "data");
  await fs.mkdir(data);
  await fs.writeFile(path.join(data, "account.js"), `window.YTD.account.part0 = ${JSON.stringify([{ account: { username: "tester", accountId: "1" } }])}`);
  await fs.writeFile(path.join(data, "tweets.js"), `window.YTD.tweets.part0 = ${JSON.stringify([
    { tweet: { id_str: "100", created_at: "Wed Jan 01 12:00:00 +0000 2025", full_text: "post" } },
    { tweet: { id_str: "101", created_at: "Thu Jan 02 12:00:00 +0000 2025", full_text: "reply", in_reply_to_status_id_str: "90" } },
    { tweet: { id_str: "102", created_at: "Fri Jan 03 12:00:00 +0000 2025", full_text: "RT @x: repost" } },
    { tweet: { id_str: "103", created_at: "Sat Jan 04 12:00:00 +0000 2025", full_text: "outside" } }
  ])}`);
  const likedMs = Date.UTC(2025, 0, 2, 10);
  const likedId = String((BigInt(likedMs) - 1288834974657n) << 22n);
  await fs.writeFile(path.join(data, "like.js"), `window.YTD.like.part0 = ${JSON.stringify([{ like: { tweetId: likedId, fullText: "liked" } }])}`);
  return { root, likedId, likedMs };
}

test("derives a snowflake timestamp", async () => {
  const { likedId, likedMs } = await fixture();
  assert.equal(snowflakeDateMs(likedId), likedMs);
});

test("selects an inclusive range and classifies all categories", async () => {
  const { root } = await fixture();
  const analysis = await loadTargets({ archivePath: root, workDir: path.join(root, "work"), start: "2025-01-01", end: "2025-01-03", timezone: "Europe/Madrid" });
  assert.deepEqual(analysis.targets.map((target) => target.kind).sort(), ["like", "post", "reply", "repost"]);
  assert.equal(analysis.targets.some((target) => target.id === "103"), false);
  assert.equal(summarizeTargets(analysis).total, 4);
});

test("rejects a reversed range", async () => {
  const { root } = await fixture();
  await assert.rejects(loadTargets({ archivePath: root, workDir: root, start: "2025-02-01", end: "2025-01-01", timezone: "UTC" }), /must not be after/);
});

test("rejects parent traversal and absolute ZIP entries", () => {
  assert.throws(() => validateArchiveEntryName("../../auth.json"), /Unsafe parent-path/);
  assert.throws(() => validateArchiveEntryName("/tmp/auth.json"), /Unsafe absolute/);
  assert.throws(() => validateArchiveEntryName("C:\\secrets\\auth.json"), /Unsafe absolute/);
  assert.equal(validateArchiveEntryName("data/tweets.js"), "data/tweets.js");
});
