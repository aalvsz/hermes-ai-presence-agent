# Security and privacy

## Data boundary

Never commit or share:

- `.env`, `auth.json`, OAuth or API credentials
- browser profiles, cookies, passwords, device codes, or session tokens
- official X account archives or cleanup ledgers
- Hermes memories, sessions, databases, logs, or runtime caches
- private messages, local account handles, personal names, or absolute home paths
- paper datasets or repositories whose license does not permit redistribution

The profile distribution contains behavior, skills, deterministic tools, and model-agnostic configuration only. Each installation creates its own local state and authenticates directly with the selected provider.

## External-action boundary

- Cron jobs are draft-only.
- X writes require active-account verification and artifact-specific approval.
- The default X backend is the official `xurl` OAuth/API client; its credential store is local-only and must never be read by the agent.
- Destructive X cleanup is archive-based, preview-first, resumable, delayed, and limited to ten actions per invocation.
- A post is marked published only after its returned ID is captured. Unknown outcomes are quarantined to prevent duplicate retries.
- GitHub and X publication are separate approvals. Local experiment work never implies public-write authority.

## Reporting

Do not open a public issue containing credentials, private archives, browser screenshots, account handles, or logs with sensitive data. Provide a minimal redacted reproduction instead.
