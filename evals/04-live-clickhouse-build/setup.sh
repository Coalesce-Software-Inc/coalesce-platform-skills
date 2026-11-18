#!/usr/bin/env bash
# Runs as the operator, unconfined, in the empty workspace (<sandbox>/home/cwd) before the agent starts.
# The agent's sandbox cannot read the operator's home directory, so stage into the sandbox home
# (readable by the agent, outside the repo it will create):
#   1. the self-contained coa CLI bundle, with a wrapper at .tools/bin/coa
#   2. a fresh, empty ClickHouse target database for this run, its name written to .tools/clickhouse_target_db
# then initialise the workspace git repository (no remote; this case does not push).
set -euo pipefail

# The scaffold runs with a redirected HOME and a filtered env, so read the repo .env directly.
REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
[ -f "$REPO_ROOT/.env" ] && { set +u; set -a; . "$REPO_ROOT/.env"; set +a; set -u; }

# coa: EVAL_COA_PKG_DIR may name a coa package directory (the folder holding coa.js) to test a specific
# build; otherwise use the coa on the operator PATH. It must support ClickHouse (tdbc-clickhouse).
if [ -n "${EVAL_COA_PKG_DIR:-}" ]; then
  COA_PKG_DIR="$EVAL_COA_PKG_DIR"
else
  COA_BIN="$(command -v coa || true)"
  [ -n "$COA_BIN" ] || { echo "setup.sh: coa not found on the operator PATH and EVAL_COA_PKG_DIR is unset" >&2; exit 1; }
  COA_PKG_DIR="$(dirname "$(readlink -f "$COA_BIN")")"
fi
[ -f "$COA_PKG_DIR/coa.js" ] || { echo "setup.sh: no coa.js in $COA_PKG_DIR" >&2; exit 1; }

TOOLS="$(cd .. && pwd)/.tools"
mkdir -p "$TOOLS/bin"
rm -rf "$TOOLS/coa"
cp -R "$COA_PKG_DIR" "$TOOLS/coa"
cat > "$TOOLS/bin/coa" <<'WRAP'
#!/bin/sh
HERE="$(cd "$(dirname "$0")/.." && pwd)"
# Node ignores HTTP(S)_PROXY unless told to; the eval sandbox routes egress through such a proxy.
export NODE_USE_ENV_PROXY=1
exec node "$HERE/coa/coa.js" "$@"
WRAP
chmod +x "$TOOLS/bin/coa"
echo "setup.sh: staged coa from $COA_PKG_DIR into $TOOLS"

# A fresh target database per sandbox, so the two ablation arms never write to the same tables.
: "${EVAL_CH_HOST:?EVAL_CH_HOST must name the ClickHouse host}"
: "${EVAL_CH_USER:?EVAL_CH_USER must name the ClickHouse user}"
: "${EVAL_CH_CRED:?EVAL_CH_CRED must hold the ClickHouse password}"
: "${EVAL_CH_TARGET_DB_PREFIX:?EVAL_CH_TARGET_DB_PREFIX must name the target database prefix}"
CH_PORT="${EVAL_CH_PORT:-8443}"
SUFFIX="$(date +%Y%m%d%H%M%S)_$(od -An -N3 -tx1 /dev/urandom | tr -d ' \n')"
TARGET_DB="${EVAL_CH_TARGET_DB_PREFIX}_${SUFFIX}"
case "$TARGET_DB" in *[!A-Za-z0-9_]*) echo "setup.sh: target database name '$TARGET_DB' must be letters, digits and _" >&2; exit 1;; esac

# ClickHouse Cloud may be idle and take a minute to wake, so allow a long first request.
if ! curl -sS --fail-with-body --max-time 180 --user "$EVAL_CH_USER:$EVAL_CH_CRED" \
      "https://$EVAL_CH_HOST:$CH_PORT/" --data-binary "CREATE DATABASE $TARGET_DB"; then
  echo "setup.sh: could not create ClickHouse database $TARGET_DB" >&2; exit 1
fi
printf '%s\n' "$TARGET_DB" > "$TOOLS/clickhouse_target_db"
echo "setup.sh: created ClickHouse target database $TARGET_DB (not dropped afterwards)"

# git inside the sandbox cannot read the operator's git template dir or credential helpers, so give the
# sandbox HOME a minimal ~/.gitconfig that disables both. HOME for the agent is the parent of the workspace.
SANDBOX_HOME="$(cd .. && pwd)"
cat > "$SANDBOX_HOME/.gitconfig" <<'GITCFG'
[init]
	templateDir =
	defaultBranch = main
[credential]
	helper =
[advice]
	detachedHead = false
GITCFG

# The sandbox refuses writes to any .git/config, so initialise the repository here with the identity set.
git init -q --template= -b main .
git config user.name "Coalesce Eval Bot"
git config user.email "eval-bot@example.com"
git config credential.helper ""
echo "setup.sh: initialised git repo in $(pwd) (no remote)"
