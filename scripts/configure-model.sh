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

echo
echo "Model identifiers saved for '$profile_name'."
echo "Authenticate directly through Hermes if needed:"
echo "  hermes -p '$profile_name' auth add '$provider'"
