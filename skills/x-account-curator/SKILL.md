---
name: x-account-curator
description: Safely preview and execute scoped X account cleanup, manage evidence-linked post drafts, and verify X write receipts.
metadata:
  hermes:
    tags: [x, twitter, cleanup, publishing, safety]
    requires_toolsets: [terminal, file]
---

# X Account Curator

Project tools live under `tools/x/` and `tools/content_queue.py`; all persisted artifacts must remain local and identity-safe.

## Cleanup

1. Use either an official X archive or `cleanup-cli.mjs --api`. The API path must use official `xurl` OAuth, never UI scraping, and disclose current X API charges before it runs.
2. Run `cleanup-cli.mjs` without `--execute` for the requested inclusive date range and timezone.
3. Report counts for likes, reposts, replies, and posts plus the oldest/newest boundary examples.
4. Explain that neither the archive nor the Likes API normally identifies when the user clicked Like; selection uses the liked post's publication date. Also disclose the API user-timeline limit of the 3,200 most recent posts.
5. Require the exact phrase `DELETE RANGE <start> <end>`.
6. Default to a first real batch of at most ten actions. If the user explicitly requests automatic cleanup after reviewing the preview and cost, `--execute-all` may continue with a rate-safe delay and checkpoint after every action. `--resume-approved` is valid only when the stored plan hash matches exactly. Stop on authorization errors, unexpected responses, or account warnings; rate-limit stops are resumed later from the ledger.

Never use a different range because an earlier run or memory mentioned one.

## Posting

1. Read the queued draft and its sources.
2. Check technical claims against primary sources.
3. Show the exact final text and character count.
4. Require `APPROVE POST <draft-id>` and record it through `content_queue.py approve`.
5. Publish only that approved ID. Record and read back the returned post URL/ID before claiming success.

Scheduled invocations are never authorized to approve or publish.

## Authentication

Prefer the official `xurl` OAuth/API backend. The user registers the developer app and completes OAuth directly in their terminal/browser. Never request, inspect, print, or export client secrets, `~/.xurl`, tokens, passwords, cookies, or profile files. Verify only through `xurl auth status`, `xurl whoami`, and the expected-account check built into the project CLI.

Browser automation is an explicit fallback only. Never use it to bypass an X automation restriction or import cookies from Safari or another personal browser.
