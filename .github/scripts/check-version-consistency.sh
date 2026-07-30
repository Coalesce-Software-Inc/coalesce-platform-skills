#!/usr/bin/env bash
#
# plugin.json's version is Claude Code's update cache key: if it goes missing or
# drifts from the tag marketplace.json pins, users silently stop receiving
# updates. Also rejects a version duplicated in the marketplace entry, which
# Claude Code ignores in favour of plugin.json's. This guards against hand-edits.
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

version=$(jq -r '.version // ""' .claude-plugin/plugin.json)
ref=$(jq -r '.plugins[0].source.ref // ""' .claude-plugin/marketplace.json)
marketplace_version=$(jq -r '.plugins[0].version // "absent"' .claude-plugin/marketplace.json)

printf '%-34s %s\n' \
  '.claude-plugin/plugin.json version' "${version:-<missing>}" \
  'marketplace source.ref' "${ref:-<missing>}"

failed=0

if [ -z "$version" ]; then
  echo "::error::.claude-plugin/plugin.json declares no version. Without it Claude Code falls back to commit-SHA versioning and 'plugin validate --strict' fails."
  failed=1
elif ! printf '%s' "$version" | grep -Eq '^[0-9]+\.[0-9]+\.[0-9]+$'; then
  echo "::error::Version '$version' is not bare semver. Tags in this repo are unprefixed (0.2.0, not v0.2.0)."
  failed=1
fi

if [ "$ref" != "$version" ]; then
  echo "::error::marketplace.json pins source.ref='$ref' but plugin.json declares '$version'. Users would receive content that doesn't match the version they're told they have."
  failed=1
fi

if [ "$marketplace_version" != "absent" ]; then
  echo "::error::The marketplace entry declares version='$marketplace_version'. Claude Code silently prefers plugin.json's value, so this field can only mislead. Remove it."
  failed=1
fi

if [ "$failed" -eq 0 ]; then
  echo "OK: version $version, pinned to tag $version."
fi

exit "$failed"
