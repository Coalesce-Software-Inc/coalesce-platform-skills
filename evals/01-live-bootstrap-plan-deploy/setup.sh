#!/usr/bin/env bash
# Runs as the operator, unconfined, in the empty workspace (<sandbox>/home/cwd) before the agent starts.
# The agent's sandbox cannot read the operator's home directory, so stage two things into the sandbox
# home (readable by the agent, outside the repo it will create):
#   1. the self-contained coa CLI bundle, with a wrapper at .tools/bin/coa
#   2. the Snowflake private key file named by DEV_AGENT_SNOWFLAKE_PK in the repo .env (or EVAL_SNOWFLAKE_PK_FILE)
set -euo pipefail

COA_BIN="$(command -v coa || true)"
[ -n "$COA_BIN" ] || { echo "setup.sh: coa not found on the operator PATH" >&2; exit 1; }
COA_PKG_DIR="$(dirname "$(readlink -f "$COA_BIN")")"

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

# The scaffold runs with a redirected HOME and a filtered env, so resolve the key path from the repo .env
# (path only; the file itself is copied below) and expand ~ against the operator's real home.
REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
[ -f "$REPO_ROOT/.env" ] && { set +u; set -a; . "$REPO_ROOT/.env"; set +a; set -u; }
REAL_HOME="$(dscl . -read "/Users/$(id -un)" NFSHomeDirectory 2>/dev/null | awk '{print $2}')"; [ -n "$REAL_HOME" ] || REAL_HOME="/Users/$(id -un)"
KEY_SRC="${EVAL_SNOWFLAKE_PK_FILE:-${DEV_AGENT_SNOWFLAKE_PK:-}}"
KEY_SRC="${KEY_SRC/#\~/$REAL_HOME}"; KEY_SRC="${KEY_SRC/#$HOME\//$REAL_HOME/}"
[ -n "$KEY_SRC" ] && [ -f "$KEY_SRC" ] || { echo "setup.sh: EVAL_SNOWFLAKE_PK_FILE or DEV_AGENT_SNOWFLAKE_PK (from .env) must name a readable key file (HOME=$HOME REAL_HOME=$REAL_HOME, got: '$KEY_SRC')" >&2; exit 1; }
install -m 600 "$KEY_SRC" "$TOOLS/snowflake_rsa_key.p8"

echo "setup.sh: staged coa from $COA_PKG_DIR and the Snowflake key into $TOOLS"

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
echo "setup.sh: wrote $SANDBOX_HOME/.gitconfig"

# The sandbox refuses writes to any .git/config or .git/hooks, so `git init` and `git remote add` cannot
# run inside it. Initialise the workspace repository here (unconfined) with the remote and identity set;
# the agent can still add, commit, branch, and push (passing credentials on the command line).
git init -q --template= -b main .
git remote add origin "${EVAL_GIT_REMOTE:?EVAL_GIT_REMOTE must name the push target repository}"
git config user.name "Coalesce Eval Bot"
git config user.email "eval-bot@example.com"
git config credential.helper ""
echo "setup.sh: initialised git repo in $(pwd) with origin $(git remote get-url origin)"
