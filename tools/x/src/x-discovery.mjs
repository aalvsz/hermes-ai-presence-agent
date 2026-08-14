import crypto from "node:crypto";
import fs from "node:fs/promises";
import path from "node:path";
import { dateRange } from "./archive.mjs";
import { runXurl } from "./x-api.mjs";

async function atomicJson(filePath, value) {
  const temporary = `${filePath}.tmp`;
  await fs.writeFile(temporary, JSON.stringify(value, null, 2));
  await fs.rename(temporary, filePath);
}

function compactText(value) {
  return String(value ?? "").replace(/\s+/g, " ").slice(0, 180);
}

function apiError(payload, label) {
  if (!Array.isArray(payload?.errors) || payload.errors.length === 0) return null;
  const details = payload.errors.map((item) => item?.detail ?? item?.title ?? item?.status).filter(Boolean).join("; ");
  return new Error(`${label} returned API errors; discovery stopped to avoid an incomplete cleanup: ${details || "unknown API error"}`);
}

export function classifyApiPost(post, username) {
  const references = Array.isArray(post?.referenced_tweets) ? post.referenced_tweets : [];
  const repost = references.find((item) => item?.type === "retweeted");
  const reply = references.find((item) => item?.type === "replied_to");
  const kind = repost ? "repost" : reply ? "reply" : "post";
  const id = String(repost?.id ?? post?.id ?? "");
  const ownPostId = String(post?.id ?? "");
  const dateMs = Date.parse(post?.created_at);
  if (!/^\d+$/.test(id) || !/^\d+$/.test(ownPostId) || !Number.isFinite(dateMs)) return null;
  return {
    kind,
    id,
    ownPostId,
    dateMs,
    dateISO: new Date(dateMs).toISOString(),
    dateBasis: kind === "repost" ? "repost timestamp" : "post timestamp",
    url: username ? `https://x.com/${username}/status/${ownPostId}` : `https://x.com/i/web/status/${ownPostId}`,
    text: compactText(post?.text),
  };
}

export function classifyApiLike(post) {
  const id = String(post?.id ?? "");
  const dateMs = Date.parse(post?.created_at);
  if (!/^\d+$/.test(id) || !Number.isFinite(dateMs)) return null;
  return {
    kind: "like",
    id,
    dateMs,
    dateISO: new Date(dateMs).toISOString(),
    dateBasis: "liked post publication timestamp; like-action time is unavailable",
    url: `https://x.com/i/web/status/${id}`,
    text: compactText(post?.text),
  };
}

export function xurlApiArgs({ app, username, endpoint }) {
  return ["--app", app, "--auth", "oauth2", "--username", String(username).replace(/^@/, ""), endpoint];
}

function endpointWithQuery(pathname, query) {
  const params = new URLSearchParams(query);
  return `${pathname}?${params.toString()}`;
}

async function discoverEndpoint({ state, key, endpoint, baseQuery, app, username, run, transform, range, stateFile, onPage }) {
  const section = state.endpoints[key];
  const seenTokens = new Set();
  while (!section.done) {
    const query = { ...baseQuery };
    if (section.nextToken) query.pagination_token = section.nextToken;
    const payload = await run(xurlApiArgs({ app, username, endpoint: endpointWithQuery(endpoint, query) }));
    const error = apiError(payload, key);
    if (error) throw error;
    const records = Array.isArray(payload?.data) ? payload.data : [];
    for (const record of records) {
      const target = transform(record);
      if (target && target.dateMs >= range.startMs && target.dateMs < range.endExclusiveMs) section.targets.push(target);
    }
    section.pages += 1;
    const nextToken = payload?.meta?.next_token;
    if (nextToken && seenTokens.has(nextToken)) throw new Error(`${key} pagination repeated a token; discovery stopped`);
    if (nextToken) seenTokens.add(nextToken);
    section.nextToken = nextToken ?? null;
    section.done = !nextToken;
    state.updatedAt = new Date().toISOString();
    await atomicJson(stateFile, state);
    await onPage({ key, pages: section.pages, found: section.targets.length, done: section.done });
  }
}

export async function loadTargetsFromXApi({ workDir, start, end, timezone, app = "hermes-ai-presence", run = runXurl, onPage = async () => {} }) {
  const range = dateRange({ start, end, timezone });
  const me = await run(["--app", app, "whoami"]);
  const accountId = String(me?.data?.id ?? "");
  const username = String(me?.data?.username ?? "").replace(/^@/, "");
  if (!/^\d+$/.test(accountId) || !username) throw new Error("xurl could not identify the authenticated X account");
  const criteria = { source: "x-api", accountId, start, end, timezone };
  const criteriaHash = crypto.createHash("sha256").update(JSON.stringify(criteria)).digest("hex").slice(0, 16);
  const stateFile = path.join(workDir, `api-discovery-${criteriaHash}.json`);
  let state = {
    version: 1,
    criteria,
    updatedAt: new Date().toISOString(),
    endpoints: {
      posts: { pages: 0, nextToken: null, done: false, targets: [] },
      likes: { pages: 0, nextToken: null, done: false, targets: [] },
    },
  };
  try {
    const existing = JSON.parse(await fs.readFile(stateFile, "utf8"));
    if (JSON.stringify(existing.criteria) !== JSON.stringify(criteria)) throw new Error("X API discovery checkpoint belongs to different criteria");
    state = existing;
  } catch (error) {
    if (error.code !== "ENOENT") throw error;
  }

  await discoverEndpoint({
    state,
    key: "posts",
    endpoint: `/2/users/${accountId}/tweets`,
    baseQuery: { max_results: "100", start_time: range.startUTC, end_time: range.endExclusiveUTC, "tweet.fields": "created_at,referenced_tweets" },
    app,
    username,
    run,
    transform: (post) => classifyApiPost(post, username),
    range,
    stateFile,
    onPage,
  });
  await discoverEndpoint({
    state,
    key: "likes",
    endpoint: `/2/users/${accountId}/liked_tweets`,
    baseQuery: { max_results: "100", "tweet.fields": "created_at" },
    app,
    username,
    run,
    transform: classifyApiLike,
    range,
    stateFile,
    onPage,
  });

  const seen = new Set();
  const targets = [...state.endpoints.posts.targets, ...state.endpoints.likes.targets]
    .filter((target) => {
      const key = `${target.kind}:${target.id}`;
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    })
    .sort((a, b) => a.dateMs - b.dateMs);
  return {
    source: "x-api",
    discoveryStateFile: stateFile,
    completenessWarning: "The user Posts timeline is limited by X to the 3,200 most recent posts. Likes are filtered by the liked post publication time because X does not expose when the Like action occurred.",
    account: { username, accountId },
    start,
    end,
    timezone,
    ...range,
    targets,
  };
}
