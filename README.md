# Hermes AI Presence Agent

A portable [Nous Research Hermes Agent](https://github.com/NousResearch/hermes-agent) distribution for evidence-led AI/ML publishing. It coordinates three isolated specialists:

1. **X account curator** — previews a user-selected date range and, only after exact confirmation, removes posts, replies, reposts, and likes. It can publish one specifically approved draft through an isolated local browser profile.
2. **AI news scout/editor** — scans primary AI/ML sources, arXiv, Hugging Face Daily Papers, selected subreddits, and Sebastian Raschka's Ahead of AI. Scheduled runs create source-linked drafts only.
3. **Paper reimplementation lab** — selects a current paper, creates an isolated local experiment, records successes and failures, and prepares approval-gated GitHub and X artifacts.

The parent agent verifies each specialist's evidence before presenting a result. It never treats a compile, smoke test, scheduled job, or publication click as stronger evidence than it actually is.

## Privacy model

This repository contains no user identity, account handle, credential, OAuth grant, browser state, private message, local memory, Codex workspace state, or absolute home-directory path. Hermes hard-excludes credential and runtime stores during profile installation; `.gitignore` provides a second boundary for local development.

Public actions are never inferred:

- Scheduled jobs create drafts only.
- X cleanup requires a fresh archive preview, active-account match, exact `DELETE RANGE <start> <end>` confirmation, and batches of at most ten actions.
- Posting requires `APPROVE POST <draft-id>` and a returned post ID. An unknown result is not retried automatically.
- GitHub repository creation or push requires a reviewed destination, visibility, license, commit, tests, claims, and disclosure.

See [SECURITY.md](SECURITY.md) for the threat model and [docs/github-agent-investigation.md](docs/github-agent-investigation.md) for the design research.

## Install as a Hermes distribution

Prerequisites: Hermes Agent `>=0.20.1`, Python `>=3.11`, Node.js `>=20`, npm, and Chromium support.

```bash
git clone REPOSITORY_URL hermes-ai-presence-agent
cd hermes-ai-presence-agent
./scripts/bootstrap-profile.sh ai-presence
```

The bootstrap installs or updates the `ai-presence` profile, creates its command alias, installs locked Node dependencies, installs Playwright Chromium, and runs the local test suite. It does not request or copy credentials.

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

# Establish the isolated X browser login interactively
node src/publish-cli.mjs login
```

Runtime state defaults to `runtime/` and is ignored by Git. Override it with `HERMES_PRESENCE_RUNTIME` when needed.

## Approval examples

Approve and publish exactly one draft:

```bash
python3 tools/content_queue.py approve DRAFT_ID \
  --confirmation "APPROVE POST DRAFT_ID"
cd tools/x
node src/publish-cli.mjs post --id DRAFT_ID --username YOUR_X_HANDLE
```

Execute at most ten reviewed cleanup actions:

```bash
cd tools/x
node src/cleanup-cli.mjs --archive /path/to/twitter-archive.zip \
  --start 2025-01-01 --end 2025-12-31 --timezone Europe/Madrid \
  --limit 10 --execute
```

Likes are selected using the liked post's publication timestamp because the official X archive normally omits the time when the Like action occurred.

## Evidence boundary

Tests establish parsing, queuing, installation structure, and fail-closed behavior. They do not establish that current X UI selectors work against a real account, that a provider subscription permits a requested model, that a scheduled draft was published, or that a paper result reproduces the original claim. Those require separate live verification and receipts.
