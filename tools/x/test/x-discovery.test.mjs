import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { classifyApiLike, classifyApiPost, loadTargetsFromXApi, xurlApiArgs } from "../src/x-discovery.mjs";

test("classifies API posts, replies, and reposts", () => {
  const base = { id: "100", created_at: "2025-01-02T10:00:00.000Z", text: "hello" };
  assert.equal(classifyApiPost(base, "user").kind, "post");
  assert.equal(classifyApiPost({ ...base, referenced_tweets: [{ type: "replied_to", id: "90" }] }, "user").kind, "reply");
  const repost = classifyApiPost({ ...base, referenced_tweets: [{ type: "retweeted", id: "80" }] }, "user");
  assert.equal(repost.kind, "repost");
  assert.equal(repost.id, "80");
  assert.equal(repost.ownPostId, "100");
});

test("classifies likes by liked-post publication time", () => {
  const target = classifyApiLike({ id: "77", created_at: "2024-02-03T00:00:00.000Z", text: "liked" });
  assert.equal(target.kind, "like");
  assert.match(target.dateBasis, /publication timestamp/);
});

test("builds OAuth2 xurl API arguments without secrets", () => {
  assert.deepEqual(xurlApiArgs({ app: "app", username: "@user", endpoint: "/2/users/1/tweets" }), ["--app", "app", "--auth", "oauth2", "--username", "user", "/2/users/1/tweets"]);
});

test("paginates posts and likes and filters the inclusive local date range", async () => {
  const workDir = await fs.mkdtemp(path.join(os.tmpdir(), "x-api-discovery-"));
  const calls = [];
  const run = async (args) => {
    calls.push(args);
    if (args.includes("whoami")) return { data: { id: "42", username: "approved" } };
    const endpoint = args.at(-1);
    if (endpoint.includes("/tweets?")) {
      if (!endpoint.includes("pagination_token=")) return { data: [{ id: "100", created_at: "2025-12-31T22:59:59.000Z", text: "keep in target" }], meta: { next_token: "next" } };
      return { data: [{ id: "99", created_at: "2026-01-01T00:00:00.000Z", text: "outside" }], meta: {} };
    }
    return { data: [{ id: "88", created_at: "2020-01-01T00:00:00.000Z", text: "old liked post" }], meta: {} };
  };
  const analysis = await loadTargetsFromXApi({ workDir, start: "2006-03-21", end: "2025-12-31", timezone: "Europe/Madrid", run });
  assert.deepEqual(analysis.targets.map(({ kind, id }) => [kind, id]), [["like", "88"], ["post", "100"]]);
  assert.equal(calls.filter((args) => args.at(-1)?.includes("/tweets?")).length, 2);
  assert.match(analysis.completenessWarning, /3,200/);
});
