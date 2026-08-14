#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 3 || $# -gt 4 ]]; then
  echo "Usage: $0 PROFILE PROVIDER MODEL [REASONING]" >&2
  exit 2
fi

profile_name="$1"
provider="$2"
model="$3"
reasoning="${4:-xhigh}"

case "$reasoning" in
  none|minimal|low|medium|high|xhigh|max|ultra) ;;
  *) echo "Unsupported reasoning level: $reasoning" >&2; exit 2 ;;
esac

hermes profile show "$profile_name" >/dev/null
hermes -p "$profile_name" config set model.provider "$provider"
hermes -p "$profile_name" config set model.default "$model"
hermes -p "$profile_name" config set --force agent.reasoning_effort "$reasoning"
hermes -p "$profile_name" config set delegation.provider "$provider"
hermes -p "$profile_name" config set delegation.model "$model"
hermes -p "$profile_name" config set delegation.reasoning_effort "$reasoning"
hermes -p "$profile_name" config set delegation.max_concurrent_children 3
hermes -p "$profile_name" config set delegation.max_spawn_depth 1
hermes -p "$profile_name" config set delegation.subagent_auto_approve false

echo
echo "Model configuration saved for '$profile_name'."
echo "Authenticate directly with the provider, then activate the schedules:"
echo "  hermes -p '$profile_name' auth add '$provider'"
echo "  $(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/activate-profile.sh '$profile_name'"
