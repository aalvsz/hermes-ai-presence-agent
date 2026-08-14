---
name: x-account-curator
description: Safely preview and execute scoped X account cleanup, manage evidence-linked post drafts, and verify X write receipts.
metadata:
  hermes:
    tags: [x, twitter, cleanup, publishing, safety]
    requires_toolsets: [terminal, file, browser]
---

# X Account Curator

Project tools live under `tools/x/` and `tools/content_queue.py`; all persisted artifacts must remain local and identity-safe.

## Cleanup

1. Require an official X archive ZIP or extracted archive. Never crawl the whole account and guess dates from the UI.
2. Run `cleanup-cli.mjs` without `--execute` for the requested inclusive date range and timezone.
3. Report counts for likes, reposts, replies, and posts plus the oldest/newest boundary examples.
4. Explain that X archives usually identify the liked post's publication date, not the date the user clicked Like.
5. Require the exact phrase `DELETE RANGE <start> <end>`.
6. First real batch is at most ten actions. Maintain the execution ledger and stop on CAPTCHA, rate limit, unexpected controls, or account warnings.

Never use a different range because an earlier run or memory mentioned one.

## Posting

1. Read the queued draft and its sources.
2. Check technical claims against primary sources.
3. Show the exact final text and character count.
4. Require `APPROVE POST <draft-id>` and record it through `content_queue.py approve`.
5. Publish only that approved ID. Record and read back the returned post URL/ID before claiming success.

Scheduled invocations are never authorized to approve or publish.

## Authentication

The user completes X login in the visible isolated browser. Never request, inspect, or export passwords, cookies, profile files, or tokens.
