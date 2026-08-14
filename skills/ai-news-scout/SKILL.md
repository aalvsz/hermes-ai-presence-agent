---
name: ai-news-scout
description: Scan current AI and ML primary sources, papers, Reddit, X leads, and Sebastian Raschka's Ahead of AI to create evidence-linked draft posts.
metadata:
  hermes:
    tags: [ai, ml, news, research, editorial, social-media]
    requires_toolsets: [web, browser, terminal, file]
    blueprint:
      schedule: "0 9 * * *"
      deliver: local
      prompt: "Run one draft-only AI news cycle. Do not approve or publish anything."
---

# AI News Scout and Editor

## Collect

Run `python3 tools/news_scout.py --since-hours 72 --limit 60 --write-snapshot` from the project root. Use the normalized results as leads. Supplement them with current X discussion only when authenticated tooling is available and the user has explicitly approved any pay-per-use API budget; a scheduled run never authorizes spend. Social posts never replace a primary source.

Coverage must include:

- original lab/company announcements
- arXiv and Hugging Face Daily Papers
- engineering sources such as PyTorch and Hugging Face
- r/MachineLearning and r/LocalLLaMA as community leads
- Sebastian Raschka's Ahead of AI

## Rank

Score candidates for recency, technical relevance to the user's domains, novelty, source quality, evidence availability, and whether the user can add an original observation. Penalize duplicate announcements, vague hype, and claims supported only by social chatter.

## Draft

Prepare one draft with:

- a concrete hook, not clickbait
- one technically meaningful detail
- a clearly marked interpretation or question
- all supporting URLs in the queue ledger
- no claim of personal testing unless a local evidence artifact exists

Enqueue with `python3 tools/content_queue.py enqueue ...`. Scheduled runs stop after returning the draft ID, text, rationale, and sources.

## Interaction

Prefer a small number of thoughtful reply suggestions over generic likes or mass replies. Never auto-follow, auto-like, or manufacture conversations.
