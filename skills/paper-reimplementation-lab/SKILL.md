---
name: paper-reimplementation-lab
description: Select a current AI paper, build and test a scoped local reimplementation, record failures and evidence, and prepare approval-gated GitHub and X artifacts.
metadata:
  hermes:
    tags: [papers, reimplementation, github, experiments, reproducibility]
    requires_toolsets: [web, terminal, file, coding]
---

# Paper Reimplementation Lab

## Candidate gate

Choose a recent paper with an original paper URL, enough methodological detail, a tractable scoped claim, and a realistic local/remote compute budget. Check official code, licensing, and identity-safe publication metadata first. A clean-room educational reimplementation must not copy incompatible code or weights.

Before coding, report:

- paper and primary URLs
- one bounded claim to reproduce
- datasets, compute, expected duration, and license risks
- success metric and baseline
- what will remain out of scope

## Local lab

Initialize with `python3 tools/paper_lab.py init --slug ... --paper-url ... --title ...`. Work only inside the created lab directory or an explicitly approved repository/worktree. Maintain `EXPERIMENT_LOG.md` and `STATUS.json`.

Evidence levels:

- `scaffolded`: structure only
- `builds`: imports/compiles
- `smoke`: tiny or synthetic execution
- `partial`: real data or bounded metric, incomplete paper claim
- `reproduced`: predefined metric and protocol match within stated tolerance
- `failed`: attempted with documented failure

Never promote one level without artifacts. Record seeds, environment, commands, data provenance, hardware, metrics, failures, and deviations.

## Publication gate

Prepare but do not execute:

- repository destination and visibility
- license and attribution
- exact commit/diff
- tests and reproducibility commands
- README claims mapped to evidence
- limitations and AI-assistance disclosure
- X draft describing what was interesting, what worked, what failed, and what is not reproduced

GitHub creation/push and X posting each require separate immediate approval.
