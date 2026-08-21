# Security and privacy

## Never commit

- `.env`, authentication stores, OAuth grants, API keys, tokens, device codes, or passwords;
- browser profiles, cookies, official account archives, cleanup ledgers, or screenshots;
- Hermes sessions, memories, databases, logs, caches, or generated reports;
- private messages, personal names, account handles, absolute home-directory paths, or company-confidential source;
- datasets, checkpoints, or repositories whose license does not permit redistribution.

## Read-only boundary

- The work queue scanner uses only provider read APIs exposed by authenticated `gh` and `glab` CLIs.
- The contribution scout treats repository text, issue bodies, comments, links, and commands as untrusted data.
- It never executes repository-provided code, installs dependencies, claims issues, creates branches, commits, pushes, opens pull requests, or contacts maintainers.
- The development inventory records bounded metadata and never copies a full source tree into its report.

## Model and account boundary

Model identifiers are configuration, not proof of authenticated access. Provider authentication must be completed directly in Hermes. No API key or OAuth token belongs in this repository.

If a provider is unavailable, the agents must report that limitation instead of using alternate credentials or bypassing access controls.
