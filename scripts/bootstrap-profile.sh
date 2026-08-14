#!/usr/bin/env bash
set -euo pipefail

profile_name="${1:-ai-presence}"
if [[ ! "$profile_name" =~ ^[a-z0-9][a-z0-9_-]*$ ]]; then
  echo "Profile name must use lowercase letters, numbers, dashes, or underscores." >&2
  exit 2
fi

for command_name in git hermes python3 npm npx tar; do
  command -v "$command_name" >/dev/null 2>&1 || {
    echo "Missing required command: $command_name" >&2
    exit 2
  }
done

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
project_root="$(cd "$script_dir/.." && pwd)"
staging_dir="$(mktemp -d "${TMPDIR:-/tmp}/hermes-ai-presence.XXXXXX")"
trap 'rm -rf "$staging_dir"' EXIT

git -C "$project_root" archive HEAD | tar -xf - -C "$staging_dir"
hermes profile install "$staging_dir" --name "$profile_name" --alias --force --yes
profile_config="$(hermes -p "$profile_name" config path)"
profile_home="$(dirname "$profile_config")"
x_tools="$profile_home/tools/x"
hermes -p "$profile_name" config set terminal.cwd "$profile_home"

npm --prefix "$x_tools" ci
(
  cd "$x_tools"
  npx playwright install chromium
  npm run check
  npm audit --audit-level=high
)

if python3 -c 'import pytest' >/dev/null 2>&1; then
  python3 -m pytest -q "$project_root/tests"
else
  echo "pytest is not installed; skipped the optional Python test runner." >&2
fi

hermes -p "$profile_name" config check >/dev/null

echo
echo "Profile '$profile_name' is installed without credentials."
echo "Next: $project_root/scripts/configure-model.sh $profile_name PROVIDER MODEL xhigh"
