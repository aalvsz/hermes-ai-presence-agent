#!/usr/bin/env bash
set -euo pipefail

profile_name="${1:-ai-presence}"
provider="$(hermes -p "$profile_name" config get model.provider)"
model="$(hermes -p "$profile_name" config get model.default)"
reasoning="$(hermes -p "$profile_name" config get agent.reasoning_effort)"

if [[ -z "$provider" || -z "$model" ]]; then
  echo "Configure the provider and model before activation." >&2
  exit 2
fi

probe="$(hermes -p "$profile_name" --provider "$provider" --model "$model" \
  --reasoning "$reasoning" --toolsets safe \
  --oneshot 'Reply with exactly: MODEL_OK')"
if [[ "$probe" != "MODEL_OK" ]]; then
  echo "Model probe failed closed; expected MODEL_OK, received: $probe" >&2
  echo "Verify provider authentication and exact model availability before retrying." >&2
  exit 2
fi

profile_config="$(hermes -p "$profile_name" config path)"
profile_home="$(dirname "$profile_config")"
existing_jobs="$(hermes -p "$profile_name" cron list)"

create_job_if_missing() {
  local job_name="$1"
  shift
  if [[ "$existing_jobs" != *"$job_name"* ]]; then
    hermes -p "$profile_name" cron create "$@"
  fi
}

news_prompt='Load ai-presence-orchestrator and ai-news-scout. Run one draft-only AI/ML news cycle. Collect fresh sources, compare the local queue to avoid duplicates, and enqueue at most one evidence-linked tweet draft. Do not approve, publish, reply, like, repost, follow, delete, create a repository, or push. Return the draft ID, exact text, source URLs, fetch errors, and why the item is worth discussing. If no sufficiently strong or novel candidate exists, create no draft and say so.'
paper_prompt='Load ai-presence-orchestrator and paper-reimplementation-lab. Review current primary paper sources and propose one tractable candidate. You may create a local scaffold and bounded reproduction plan, but do not start expensive compute, create a remote repository, push, or post. Return paper and code URLs, license, scoped claim, metric, compute estimate, risks, and approval needed.'

create_job_if_missing "ai-news-draft-morning" \
  "0 9 * * *" "$news_prompt" --name "ai-news-draft-morning" \
  --deliver local --skill ai-presence-orchestrator --skill ai-news-scout \
  --workdir "$profile_home" --provider "$provider" --model "$model"

create_job_if_missing "ai-news-draft-evening" \
  "0 17 * * *" "$news_prompt" --name "ai-news-draft-evening" \
  --deliver local --skill ai-presence-orchestrator --skill ai-news-scout \
  --workdir "$profile_home" --provider "$provider" --model "$model"

create_job_if_missing "paper-candidate-weekly" \
  "30 10 * * 1" "$paper_prompt" --name "paper-candidate-weekly" \
  --deliver local --skill ai-presence-orchestrator --skill paper-reimplementation-lab \
  --workdir "$profile_home" --provider "$provider" --model "$model"

gateway_status="$(hermes -p "$profile_name" gateway status 2>&1)"
if [[ "$gateway_status" == *"not running"* || "$gateway_status" == *"not installed"* ]]; then
  hermes -p "$profile_name" gateway install --start-now --start-on-login
fi

hermes -p "$profile_name" cron list
hermes -p "$profile_name" gateway status
echo "Profile '$profile_name' is active; scheduled jobs remain draft-only."
