#!/usr/bin/env bash
set -euo pipefail

for command_name in git hermes python3 tar; do
  command -v "$command_name" >/dev/null 2>&1 || {
    echo "Missing required command: $command_name" >&2
    exit 2
  }
done

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
project_root="$(cd "$script_dir/.." && pwd)"
staging_dir="$(mktemp -d "${TMPDIR:-/tmp}/hermes-work-office.XXXXXX")"
trap 'rm -rf "$staging_dir"' EXIT

install_profile() {
  local profile_name="$1"
  mkdir -p "$staging_dir/$profile_name"
  cp -R "$project_root/profiles/$profile_name/." "$staging_dir/$profile_name/"
  hermes profile install "$staging_dir/$profile_name" --name "$profile_name" --alias --force --yes
  local profile_config
  local profile_home
  profile_config="$(hermes -p "$profile_name" config path)"
  profile_home="$(dirname "$profile_config")"
  hermes -p "$profile_name" config set terminal.cwd "$profile_home"
}

install_profile work-queue-briefing
install_profile contribution-reputation-scout

echo
echo "Installed exactly two Hermes profiles:"
echo "  - work-queue-briefing"
echo "  - contribution-reputation-scout"
echo "Configure the model with scripts/configure-model.sh, then schedule the scout with scripts/schedule-scout.sh /path/to/dev."
