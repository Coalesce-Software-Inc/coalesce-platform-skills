#!/usr/bin/env bash
#
# Writes a new version into plugin.json and the tag marketplace.json pins. Does
# not commit, tag or push — the release workflow does that, so this is safe to run
# locally to preview a release. Both fields must move together: the version is
# what Claude Code compares for updates, the ref is what it actually fetches.
set -euo pipefail

version="${1:?usage: prepare-release.sh <new-version>}"

if ! printf '%s' "$version" | grep -Eq '^[0-9]+\.[0-9]+\.[0-9]+$'; then
  echo "error: '$version' is not a bare semver version (expected e.g. 0.2.0, no 'v' prefix)" >&2
  exit 1
fi

cd "$(git rev-parse --show-toplevel)"

# --indent 2 round-trips both manifests byte-for-byte apart from the edited value,
# so this stays a one-line diff instead of a whole-file reformat.
edit_json() {
  local file="$1" filter="$2"
  jq --indent 2 "$filter" "$file" >"$file.tmp"
  mv "$file.tmp" "$file"
}

edit_json .claude-plugin/plugin.json ".version = \"$version\""
edit_json .claude-plugin/marketplace.json ".plugins[0].source.ref = \"$version\""

echo "Prepared release $version"
echo "  .claude-plugin/plugin.json       version    -> $version"
echo "  .claude-plugin/marketplace.json  source.ref -> $version"
