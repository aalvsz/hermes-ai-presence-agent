# Hermes Multiverse Work Office

A portable, privacy-conscious Hermes setup with exactly two simple office bots:

1. **Work Queue Briefing** — summarizes open GitHub issues and pull requests plus GitLab issues and merge requests assigned to the authenticated user.
2. **Contribution Reputation Scout** — periodically catalogs repository metadata under a user-selected development root and matches it to evidence-backed contribution opportunities in major AI/ML repositories.

Both profiles are read-only and report/draft-only. They do not create child agents, edit source, commit, push, contact maintainers, launch compute, or change GitHub/GitLab state.

## Privacy model

This repository contains no user name, account handle, credentials, OAuth grant, browser state, private messages, Codex memory, Hermes sessions, absolute home path, or local runtime report. The local `/dev` catalog records repository metadata only; it does not copy full source trees or execute project code.

Provider authentication remains inside Hermes. Do not commit `.env`, token stores, browser profiles, archives, logs, or generated reports. See [SECURITY.md](SECURITY.md).

## Install the two profiles

Prerequisites: Hermes Agent `>=0.20.1`, Python `>=3.11`, Git, and authenticated read-only `gh`/`glab` CLIs for the providers you want to scan.

```bash
git clone https://github.com/aalvsz/hermes-ai-presence-agent.git
cd hermes-ai-presence-agent
./scripts/bootstrap-office.sh
```

Configure the requested model identifiers for both profiles. Authentication happens through Hermes and is never stored in this repository:

```bash
./scripts/configure-model.sh work-queue-briefing openai-codex gpt-5.6-luna xhigh
./scripts/configure-model.sh contribution-reputation-scout openai-codex gpt-5.6-luna xhigh
```

Then authenticate directly through Hermes, if needed:

```bash
hermes -p work-queue-briefing auth add openai-codex
hermes -p contribution-reputation-scout auth add openai-codex
```

The profiles remain usable as read-only assistants even when one provider is unavailable; the affected provider is reported as unavailable.

## Work Queue Briefing

Run a live metadata-only summary:

```bash
hermes -p work-queue-briefing
```

Ask it to refresh the queue. The underlying scanner is:

```bash
python3 tools/work_queue_scan.py --output-dir runtime/work-queue
```

The scanner uses the authenticated `gh` and `glab` CLIs, requests only open assigned-item metadata, and never fetches descriptions, comments, diffs, files, artifacts, or credentials.

## Contribution Reputation Scout

Set the development root locally and schedule the read-only scan twice weekly:

```bash
./scripts/schedule-scout.sh /path/to/dev
```

The scheduler writes the selected path only to the local Hermes profile, not to Git. It runs Monday and Thursday at 08:15 in the configured local timezone. Each run:

1. inventories repository paths, Git state, languages, manifests, and sanitized origins;
2. scans the configured public Google, NVIDIA, Ultralytics, vLLM, llama.cpp, Unsloth, Hugging Face, PyTorch, JAX, MLX, Ray, and related repositories;
3. ranks contribution friendliness using current public evidence;
4. writes a local report and recommends a small number of candidates.

```bash
python3 tools/dev_inventory.py --root /path/to/dev --output-dir runtime/dev-inventory
python3 tools/github_scout.py --config config/repositories.json --output-dir runtime/scans
hermes -p contribution-reputation-scout
```

The score is **contribution friendliness**, never acceptance probability. Missing evidence, stale issues, assignments, linked work, unclear process, or large compute requirements lower confidence. Discovery never claims issues or opens pull requests.

## Tests

```bash
python3 -m unittest discover -s tests -v
python3 -m py_compile tools/*.py
```

The tests cover parsing, redaction boundaries, provider failure handling, metadata-only inventory, and bounded reports. They do not prove external account permissions or maintainer acceptance.
