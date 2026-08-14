---
name: ai-presence-orchestrator
description: Coordinate the X curator, AI-news scout/editor, and paper reimplementation lab as isolated Hermes subagents with evidence and approval gates.
metadata:
  hermes:
    tags: [orchestration, social-media, ai-news, papers, delegation]
    requires_toolsets: [delegation, skills, terminal, file]
---

# AI Presence Orchestrator

Use this skill for identity-safe public-presence work. Never combine discovery, approval, and external execution into one unreviewed step.

## Delegation contract

Spawn a bounded batch with one leaf subagent per relevant task. Each child starts with no conversation context, so pass the absolute project path, current request, authority boundary, and tell it to load its named skill first.

1. **X curator**
   - Load `x-account-curator`.
   - Own account cleanup previews, queued-post verification, and X action receipts.
   - Never broaden a date range or infer approval.
2. **AI-news scout/editor**
   - Load `ai-news-scout`.
   - Own fresh-source collection, ranking, claim extraction, and evidence-linked drafts.
   - Treat X/social chatter as leads, not factual evidence.
3. **Paper lab**
   - Load `paper-reimplementation-lab`.
   - Own candidate selection, local implementation, tests, experiment logs, and honest publication manifests.
   - Never push or announce a result.

Require structured results containing `status`, `artifacts`, `evidence`, `risks`, `approval_needed`, and `next_action`. After children return, verify local artifacts and at least the primary source for every public claim.

## Scheduled news cycle

For scheduled cycles, delegate only the AI-news task. Produce at most one queued tweet draft per cycle. End with the draft ID and source URLs. Do not approve or post it.

## User-approved execution

- X post: confirm the exact draft ID and text, record `APPROVE POST <id>`, execute, then read back the returned post ID/URL.
- X cleanup: regenerate the preview for the exact range, present category counts and boundary timestamps, require `DELETE RANGE <start> <end>`, start with at most ten actions, and stop on any UI uncertainty.
- GitHub: show repository name, visibility, license, commit diff, tests, claims, and disclosure; push only after approval.
