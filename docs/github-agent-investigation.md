# GitHub investigation: Hermes multi-agent patterns

Investigation date: 2026-08-14. Repositories were cloned read-only and inspected at the exact revisions below.

## Repositories inspected

| Repository | Revision | Useful pattern | Boundary applied here |
|---|---|---|---|
| [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent/tree/56a41715dc3b8bf6f50a740ff9416c4036ef4259) | `56a4171` | Native skills, isolated `delegate_task` children, profiles, cron, provider-specific OAuth, persistent gateways | Use one profile, four local skills, flat three-child delegation, pinned cron provider/model |
| [jonortega20/fantasybot](https://github.com/jonortega20/fantasybot/tree/2ab13de40f6ceb7466fa3aed425d07078318453c) | `2ab13de` | Deterministic domain CLI as the toolbox; Hermes supplies memory, judgment, and schedules | Keep account operations deterministic and ledgered; do not copy its broad autonomous transaction authority |
| [shannhk/hermes-agent-control-room](https://github.com/shannhk/hermes-agent-control-room/tree/48a1a5a2c3a64416f51b0199a1acc9aba05e6261) | `48a1a5a` | Orchestrator/specialist separation and explicit task briefs | Every child receives objective, context, constraints, output schema, and approval gates |
| [gabriel-chiappa/.hermes](https://github.com/gabriel-chiappa/.hermes/tree/df44279f631ae56488f4d6e1ace593aff00ac999) | `df44279` | Multiple purpose-built profiles and rich identity/config files | Reuse specialization; reject approval-off and high-autonomy financial/action rhetoric |
| [ellis-guo/daily-news-agent](https://github.com/ellis-guo/daily-news-agent/tree/9c603f123f59ebdca8f52852e8c9529c3c1b39cb) | `9c603f1` | Scheduled collection and synthesis pipeline | Separate collection from editorial judgment; persist source errors and drafts |
| [praveen-ks-2001/hermes-agent-template](https://github.com/praveen-ks-2001/hermes-agent-template/tree/c2d727f27fd188eebefb03cb4c7c01d2b0dde577) | `c2d727f` | Reusable Hermes project/profile skeleton | Keep committed behavior portable and keep local auth/profile state out of Git |
| [alivecontext/alive](https://github.com/alivecontext/alive/tree/e6609886bd4f5e801a6d1bc1533dcae04e60b9b4) | `e660988` | Persistent context and agent-state concepts | Retain only durable editorial/evidence memory; exclude credentials and private messages |

## Current Hermes mechanics that shaped the design

- A skill is the right unit when the agent needs instructions plus existing tools. A custom deterministic CLI is preferable for exact parsing, approval ledgers, archive handling, and browser actions.
- `delegate_task` children have isolated conversation context. The parent must pass the project path, named skill, authority boundary, and requested output explicitly.
- In the inspected revision, model-facing `delegate_task` does not accept per-child skill or toolset arguments. Children inherit the parent's toolsets and can load named skills through the skills toolset.
- Flat delegation (`max_spawn_depth: 1`) is sufficient: the parent coordinates three leaf specialists. More depth would multiply subscription usage without improving the ownership split.
- Cron blueprints in skill metadata describe a possible job; they do not replace an inspected, pinned local cron installation.
- `openai-codex` is Hermes' ChatGPT/Codex subscription route. It uses a device-code grant and its own credential pool; it is distinct from an OpenAI API key.

## Resulting architecture

```text
aipresence parent (evidence and approval verifier)
├── x-account-curator
│   └── official archive parser + isolated visible browser + action ledger
├── ai-news-scout
│   └── balanced feed/API collector + evidence-linked draft queue
└── paper-reimplementation-lab
    └── isolated local lab + evidence levels + disabled publication manifest
```

The parent may invoke all three concurrently for an interactive request. Scheduled news cycles invoke only the news specialist and stop at a local draft. No child can infer public-write authority from a schedule, an earlier approval, or a different date range.

## Deliberately rejected patterns

- Automatic posting, replying, liking, following, or deletion from cron.
- Reusing a general browser profile containing unrelated sessions.
- Scraping an account's timeline to guess the full deletion set.
- Treating Reddit or X chatter as factual evidence rather than a lead.
- Calling a compile, smoke test, or synthetic metric a paper reproduction.
- Letting a paper worker create a public repository or push a branch as part of implementation.
- Retrying a post when the click occurred but no returned post ID was captured.
- Copying OAuth/browser state into a portable Hermes profile or Git repository.

## Known external constraints

- X's official API/CLI route requires a developer application and may require paid access. The implemented browser route avoids requesting those secrets but remains dependent on current UI selectors and must stop on uncertainty.
- X archives generally provide the liked post's publication timestamp, not when the user clicked Like. A date-range cleanup of likes therefore uses and discloses that proxy.
- Reddit may rate-limit anonymous RSS. The collector records the source error and continues; it does not evade the limit.
- A ChatGPT subscription's available models and limits are account-side state. Configuration alone is not proof that a real `gpt-5.6-luna` request is permitted.
