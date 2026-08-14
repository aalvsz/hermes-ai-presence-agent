# Hermes AI Presence Agent

A portable [Nous Research Hermes Agent](https://github.com/NousResearch/hermes-agent) distribution for evidence-led AI/ML publishing. It coordinates three isolated specialists:

1. **X account curator** — previews a user-selected date range and, only after exact confirmation, removes posts, replies, reposts, and likes. It publishes specifically approved drafts through X's official `xurl` OAuth/API client.
2. **AI news scout/editor** — scans primary AI/ML sources, arXiv, Hugging Face Daily Papers, selected subreddits, and Sebastian Raschka's Ahead of AI. Scheduled runs create source-linked drafts only.
3. **Paper reimplementation lab** — selects a current paper, creates an isolated local experiment, records successes and failures, and prepares approval-gated GitHub and X artifacts.

The parent agent verifies each specialist's evidence before presenting a result. It never treats a compile, smoke test, scheduled job, or publication click as stronger evidence than it actually is.

## Privacy model

This repository contains no user identity, account handle, credential, OAuth grant, browser state, private message, local memory, Codex workspace state, or absolute home-directory path. Hermes hard-excludes credential and runtime stores during profile installation; `.gitignore` provides a second boundary for local development.

Public actions are never inferred:

- Scheduled jobs create drafts only.
- X cleanup requires a fresh preview, active-account match, and exact `DELETE RANGE <start> <end>` confirmation. The API-only automatic mode is resumable, rate-limited, and reuses approval only when the stored plan hash still matches exactly.
- Posting requires `APPROVE POST <draft-id>` and a returned post ID. An unknown result is not retried automatically.
- GitHub repository creation or push requires a reviewed destination, visibility, license, commit, tests, claims, and disclosure.

See [SECURITY.md](SECURITY.md) for the threat model and [docs/github-agent-investigation.md](docs/github-agent-investigation.md) for the design research.

## Install as a Hermes distribution

Prerequisites: Hermes Agent `>=0.20.1`, Python `>=3.11`, Node.js `>=20`, npm, Chromium support for the optional browser fallback, and the official [`xurl`](https://github.com/xdevplatform/xurl) CLI for X writes.

```bash
git clone REPOSITORY_URL hermes-ai-presence-agent
cd hermes-ai-presence-agent
./scripts/bootstrap-profile.sh ai-presence
```

The bootstrap installs or updates the `ai-presence` profile, creates its command alias, installs locked Node dependencies, installs Playwright Chromium, and runs the local test suite. It does not request or copy credentials.

Install `xurl` from its official package, create an X developer app with Read and Write permission and redirect URI `http://localhost:8080/callback`, then register and authenticate it manually. Never paste its client secret into an agent or commit its local store:

```bash
npm install -g @xdevplatform/xurl
read "xurl_id?Client ID: "
read -s "xurl_secret?Client Secret: "; echo
xurl auth apps add hermes-ai-presence \
  --client-id "$xurl_id" --client-secret "$xurl_secret" \
  --redirect-uri http://localhost:8080/callback
unset xurl_id xurl_secret
xurl auth oauth2 --app hermes-ai-presence
xurl auth default hermes-ai-presence
xurl auth status
```

## Plug in a model

Configure any Hermes-supported provider/model pair:

```bash
./scripts/configure-model.sh ai-presence PROVIDER MODEL xhigh
```

For a ChatGPT/Codex subscription-backed model, one example is:

```bash
./scripts/configure-model.sh ai-presence openai-codex gpt-5.6-luna xhigh
ai-presence auth add openai-codex
```

Authentication is completed directly through the provider's interactive flow. No API key or token belongs in this repository.

After a real one-shot model probe succeeds, install the draft-only schedules and start the local gateway:

```bash
./scripts/activate-profile.sh ai-presence
```

This creates two daily news-draft jobs and one weekly paper-candidate job, pins them to the configured provider/model, and starts the Hermes user service. It does not schedule publishing, replying, liking, following, deletion, GitHub creation, or GitHub pushes.

## Verify

```bash
ai-presence config show
ai-presence skills list --enabled-only
ai-presence cron list
ai-presence gateway status

# Non-mutating model probe
ai-presence --provider PROVIDER --model MODEL --reasoning xhigh \
  --toolsets safe --oneshot "Reply with exactly: MODEL_OK"
```

Never silently substitute another model if the requested model is unavailable.

## Local tools

```bash
# Current news as normalized JSON
python3 tools/news_scout.py --since-hours 72 --limit 40 --per-source-limit 12

# Create and inspect a draft
python3 tools/content_queue.py enqueue --kind tweet \
  --text "Draft text" --source https://example.com
python3 tools/content_queue.py list

# Preview an official X archive; no account action occurs
cd tools/x
node src/cleanup-cli.mjs --archive /path/to/twitter-archive.zip \
  --start 2025-01-01 --end 2025-12-31 --timezone Europe/Madrid

# Or discover the range through the official X API; no archive required.
# This is billable under X's current pay-per-use pricing.
node src/cleanup-cli.mjs --api \
  --start 2006-03-21 --end 2025-12-31 --timezone Europe/Madrid

# Verify the official xurl OAuth connection without exposing credentials.
# Register/authenticate xurl manually first; never paste secrets into an agent.
node src/publish-cli.mjs login --backend xurl --username YOUR_X_HANDLE
```

Runtime state defaults to `runtime/` and is ignored by Git. Override it with `HERMES_PRESENCE_RUNTIME` when needed.

## Approval examples

Approve and publish exactly one draft:

```bash
python3 tools/content_queue.py approve DRAFT_ID \
  --confirmation "APPROVE POST DRAFT_ID"
cd tools/x
node src/publish-cli.mjs post --id DRAFT_ID --username YOUR_X_HANDLE --backend xurl
```

Execute at most ten reviewed cleanup actions:

```bash
cd tools/x
node src/cleanup-cli.mjs --archive /path/to/twitter-archive.zip \
  --start 2025-01-01 --end 2025-12-31 --timezone Europe/Madrid \
  --limit 10 --execute --backend xurl
```

After reviewing an API preview, execute the entire plan automatically with a rate-safe delay and a resumable local ledger:

```bash
cd tools/x
node src/cleanup-cli.mjs --api \
  --start 2006-03-21 --end 2025-12-31 --timezone Europe/Madrid \
  --execute-all

# If X stops the run at a daily limit, resume the exact already-approved plan later:
node src/cleanup-cli.mjs --api \
  --start 2006-03-21 --end 2025-12-31 --timezone Europe/Madrid \
  --execute-all --resume-approved
```

API cleanup has two explicit completeness boundaries. X documents that the user Posts timeline returns at most the 3,200 most recent posts. X also does not expose the time when a Like action occurred, so Likes are selected using the liked post's publication timestamp. The automatic mode defaults to 20 seconds between writes, checkpoints every successful action, stops on the first unexpected response, and can resume without repeating completed actions.

The default write backend is the official [`xurl`](https://github.com/xdevplatform/xurl) OAuth/API client. Browser automation remains an explicit `--backend browser` fallback but is never used to bypass an X automation restriction and never imports cookies from Safari or another personal browser.

## Evidence boundary

Tests establish parsing, queuing, installation structure, and fail-closed behavior. They do not establish that current X UI selectors work against a real account, that a provider subscription permits a requested model, that a scheduled draft was published, or that a paper result reproduces the original claim. Those require separate live verification and receipts.
