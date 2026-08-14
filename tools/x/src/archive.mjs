import fs from "node:fs/promises";
import path from "node:path";
import crypto from "node:crypto";
import AdmZip from "adm-zip";
import { DateTime } from "luxon";

const TWITTER_EPOCH_MS = 1288834974657n;

function parseAssignedJson(text, filePath) {
  const equals = text.indexOf("=");
  const payload = (equals >= 0 ? text.slice(equals + 1) : text).trim().replace(/;\s*$/, "");
  try { return JSON.parse(payload); }
  catch (error) { throw new Error(`Could not parse ${filePath}: ${error.message}`); }
}

async function listFiles(root) {
  const found = [];
  for (const entry of await fs.readdir(root, { withFileTypes: true })) {
    const absolute = path.join(root, entry.name);
    if (entry.isDirectory()) found.push(...await listFiles(absolute));
    else found.push(absolute);
  }
  return found;
}

export function validateArchiveEntryName(entryName) {
  const portable = String(entryName).replaceAll("\\", "/");
  if (!portable || portable.startsWith("/") || /^[A-Za-z]:\//.test(portable)) throw new Error(`Unsafe absolute ZIP entry: ${entryName}`);
  const normalized = path.posix.normalize(portable);
  if (normalized === ".." || normalized.startsWith("../")) throw new Error(`Unsafe parent-path ZIP entry: ${entryName}`);
  return normalized;
}

async function prepareArchive(inputPath, workDir) {
  const absolute = path.resolve(inputPath);
  const stat = await fs.stat(absolute);
  if (stat.isDirectory()) return absolute;
  if (path.extname(absolute).toLowerCase() !== ".zip") throw new Error("--archive must be an official X ZIP or extracted directory");
  const key = crypto.createHash("sha256").update(`${absolute}:${stat.size}:${stat.mtimeMs}`).digest("hex").slice(0, 12);
  const destination = path.join(workDir, `archive-${key}`);
  try { await fs.access(destination); return destination; }
  catch {
    const archive = new AdmZip(absolute);
    for (const entry of archive.getEntries()) {
      validateArchiveEntryName(entry.entryName);
      const unixType = (Number(entry.header.attr) >>> 16) & 0o170000;
      if (unixType === 0o120000) throw new Error(`Symbolic links are not allowed in the X archive: ${entry.entryName}`);
    }
    await fs.mkdir(destination, { recursive: true });
    archive.extractAllTo(destination, true);
    return destination;
  }
}

export function dateRange({ start, end, timezone }) {
  const startLocal = DateTime.fromISO(start, { zone: timezone, setZone: true }).startOf("day");
  const endLocal = DateTime.fromISO(end, { zone: timezone, setZone: true }).endOf("day");
  if (!startLocal.isValid || !endLocal.isValid || !/^\d{4}-\d{2}-\d{2}$/.test(start) || !/^\d{4}-\d{2}-\d{2}$/.test(end)) {
    throw new Error("--start and --end must use YYYY-MM-DD");
  }
  if (startLocal > endLocal) throw new Error("--start must not be after --end");
  const endExclusive = endLocal.plus({ milliseconds: 1 });
  return {
    startMs: startLocal.toUTC().toMillis(),
    endMs: endLocal.toUTC().toMillis(),
    endExclusiveMs: endExclusive.toUTC().toMillis(),
    startUTC: startLocal.toUTC().toISO(),
    endUTC: endLocal.toUTC().toISO(),
    endExclusiveUTC: endExclusive.toUTC().toISO({ suppressMilliseconds: true }),
  };
}

export function snowflakeDateMs(id) {
  if (!/^\d+$/.test(String(id))) throw new Error(`Invalid X id: ${id}`);
  return Number((BigInt(id) >> 22n) + TWITTER_EPOCH_MS);
}

function classifyTweet(tweet) {
  if (/^RT\s+@/i.test(tweet.full_text ?? "")) return "repost";
  if (tweet.in_reply_to_status_id_str || tweet.in_reply_to_user_id_str) return "reply";
  return "post";
}

function accountFromRecords(records) {
  const account = records?.[0]?.account ?? records?.account;
  return account ? { username: account.username, accountId: account.accountId, displayName: account.accountDisplayName } : null;
}

export async function loadTargets({ archivePath, workDir, start, end, timezone }) {
  const range = dateRange({ start, end, timezone });
  const root = await prepareArchive(archivePath, workDir);
  const files = await listFiles(root);
  const tweetFiles = files.filter((file) => /^tweets(?:-part\d+)?\.js$/i.test(path.basename(file)));
  const likeFiles = files.filter((file) => /^likes?(?:-part\d+)?\.js$/i.test(path.basename(file)));
  if (tweetFiles.length === 0) throw new Error("No tweets.js file found in the X archive");
  let account = null;
  const accountFile = files.find((file) => /^account\.js$/i.test(path.basename(file)));
  if (accountFile) account = accountFromRecords(parseAssignedJson(await fs.readFile(accountFile, "utf8"), accountFile));
  const targets = [];
  for (const file of tweetFiles) {
    for (const record of parseAssignedJson(await fs.readFile(file, "utf8"), file)) {
      const tweet = record.tweet ?? record;
      const id = tweet.id_str ?? tweet.id;
      const dateMs = Date.parse(tweet.created_at);
      if (!id || !Number.isFinite(dateMs) || dateMs < range.startMs || dateMs > range.endMs) continue;
      const kind = classifyTweet(tweet);
      targets.push({ kind, id: String(id), dateMs, dateISO: new Date(dateMs).toISOString(), dateBasis: kind === "repost" ? "repost timestamp" : "post timestamp", url: account?.username ? `https://x.com/${account.username}/status/${id}` : `https://x.com/i/web/status/${id}`, text: String(tweet.full_text ?? "").replace(/\s+/g, " ").slice(0, 180) });
    }
  }
  for (const file of likeFiles) {
    for (const record of parseAssignedJson(await fs.readFile(file, "utf8"), file)) {
      const like = record.like ?? record;
      const id = like.tweetId ?? like.tweet_id ?? like.id_str;
      if (!id) continue;
      let dateMs;
      try { dateMs = snowflakeDateMs(id); } catch { continue; }
      if (dateMs < range.startMs || dateMs > range.endMs) continue;
      targets.push({ kind: "like", id: String(id), dateMs, dateISO: new Date(dateMs).toISOString(), dateBasis: "liked post publication timestamp; like-action time is unavailable", url: String(like.expandedUrl ?? `https://x.com/i/web/status/${id}`).replace("twitter.com", "x.com"), text: String(like.fullText ?? "").replace(/\s+/g, " ").slice(0, 180) });
    }
  }
  const seen = new Set();
  const unique = targets.filter((target) => { const key = `${target.kind}:${target.id}`; if (seen.has(key)) return false; seen.add(key); return true; }).sort((a, b) => a.dateMs - b.dateMs);
  return { archiveRoot: root, account, start, end, timezone, ...range, targets: unique };
}

export function summarizeTargets(analysis) {
  const categories = {};
  for (const kind of ["like", "repost", "reply", "post"]) {
    const items = analysis.targets.filter((item) => item.kind === kind);
    categories[kind] = { count: items.length, oldest: items[0]?.dateISO ?? null, newest: items.at(-1)?.dateISO ?? null, samples: [...items.slice(0, 2), ...items.slice(-2)].filter((item, index, array) => array.findIndex((other) => other.id === item.id) === index) };
  }
  return {
    generatedAt: new Date().toISOString(),
    source: analysis.source ?? "x-archive",
    account: analysis.account,
    start: analysis.start,
    end: analysis.end,
    timezone: analysis.timezone,
    startUTC: analysis.startUTC,
    endUTC: analysis.endUTC,
    total: analysis.targets.length,
    categories,
    likeDateWarning: "Likes use the liked post publication time because X does not expose the time of the Like action in the archive or Likes API.",
    completenessWarning: analysis.completenessWarning ?? null,
  };
}
