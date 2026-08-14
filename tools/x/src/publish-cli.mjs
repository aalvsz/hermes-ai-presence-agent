#!/usr/bin/env node
import fs from "node:fs/promises";
import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";
import { login, publishApproved } from "./x-browser.mjs";

async function atomicJson(filePath, value) {
  const temporary = `${filePath}.tmp`;
  await fs.writeFile(temporary, `${JSON.stringify(value, null, 2)}\n`);
  await fs.rename(temporary, filePath);
}

function parse(argv) {
  const [command, ...rest] = argv;
  const args = { command };
  for (let i = 0; i < rest.length; i += 1) {
    if (rest[i] === "--id") args.id = rest[++i];
    else if (rest[i] === "--profile") args.profileDir = rest[++i];
    else if (rest[i] === "--username") args.username = rest[++i];
    else throw new Error(`Unknown option: ${rest[i]}`);
  }
  if (!["login", "post"].includes(command)) throw new Error("command must be login or post");
  if (command === "post" && !args.id) throw new Error("post requires --id");
  if (command === "post" && !args.username) throw new Error("post requires --username so the active X account can be verified");
  return args;
}

async function main() {
  const args = parse(process.argv.slice(2));
  const projectRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../..");
  const runtimeRoot = path.resolve(process.env.HERMES_PRESENCE_RUNTIME ?? path.join(projectRoot, "runtime"));
  const profileDir = path.resolve(args.profileDir ?? path.join(runtimeRoot, "browser-profile"));
  if (args.command === "login") { const account = await login({ profileDir }); console.log(JSON.stringify({ status: "logged-in-profile-verified", profileDir, ...account })); return; }
  const draftPath = path.join(runtimeRoot, "content", `${args.id}.json`);
  const draft = JSON.parse(await fs.readFile(draftPath, "utf8"));
  let submitting = false;
  try {
    const result = await publishApproved({
      draft,
      profileDir,
      username: args.username,
      onSubmitting: async () => {
        submitting = true;
        draft.state = "publishing";
        draft.publication = { status: "submitting", started_at: new Date().toISOString() };
        await atomicJson(draftPath, draft);
      },
    });
    draft.state = "published";
    draft.publication = { status: "confirmed", receipt: result.receipt, post_id: result.postId, published_at: result.postedAt };
    await atomicJson(draftPath, draft);
    console.log(JSON.stringify({ status: "posted", draftId: args.id, ...result }, null, 2));
  } catch (error) {
    if (submitting) {
      draft.state = "publication_unknown";
      draft.publication = { status: "unknown", error: error.message, page_url: error.pageUrl ?? null, checked_at: new Date().toISOString() };
      await atomicJson(draftPath, draft);
    }
    throw error;
  }
}

main().catch((error) => { console.error(`error: ${error.message}`); process.exitCode = 1; });
