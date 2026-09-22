#!/usr/bin/env bash
# Launch the live eval suite with the operator's credentials and run configuration.
#
# Reads an untracked .env at the repository root, maps the few names the cases
# expect, checks everything resolves, and runs `claude plugin eval` against the
# checkout this script lives in. Point it at a PR by running it from that
# branch's worktree.
#
# Usage:
#   evals/run.sh                        # the live case, one run per arm
#   evals/run.sh --case '02-*'          # extra flags are appended, last wins
#   evals/run.sh --print                # show the command and exit, run nothing
#
# This repository is public. The script carries variable NAMES only; every
# site-specific value comes from .env at run time.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PRINT_ONLY=0
ARGS=()
for a in "$@"; do
  if [ "$a" = "--print" ]; then PRINT_ONLY=1; else ARGS+=("$a"); fi
done

[ -f .env ] || { echo "run.sh: no .env at $ROOT — see evals/README.md for the variables it must define" >&2; exit 1; }
set -a; . ./.env; set +a

# The sandbox strips variables whose names contain TOKEN, PAT, AUTH, KEY or
# SECRET, so the secrets are re-exported under EVAL_* names the sandbox keeps.
export EVAL_COA_CLOUD="${EVAL_COA_CLOUD:-${AUTH_TOKEN:-}}"
export EVAL_GH_CRED="${EVAL_GH_CRED:-${DEV_AGENT_GITHUB_PAT:-}}"
export EVAL_SNOWFLAKE_ACCOUNT="${EVAL_SNOWFLAKE_ACCOUNT:-${DEV_AGENT_WORKSPACE_SNOWFLAKE_ACCOUNT:-}}"
export EVAL_SNOWFLAKE_USER="${EVAL_SNOWFLAKE_USER:-${DEV_AGENT_WORKSPACE_SNOWFLAKE_USER:-}}"
export EVAL_SNOWFLAKE_PK_FILE="${EVAL_SNOWFLAKE_PK_FILE:-${DEV_AGENT_SNOWFLAKE_PK:-}}"

missing=()
for v in EVAL_COA_DOMAIN EVAL_COA_PROJECT EVAL_COA_CONNECTION EVAL_COA_CLOUD \
         EVAL_SNOWFLAKE_ACCOUNT EVAL_SNOWFLAKE_USER EVAL_SNOWFLAKE_WAREHOUSE \
         EVAL_SNOWFLAKE_PK_FILE EVAL_SOURCE_DB EVAL_SOURCE_SCHEMA \
         EVAL_TARGET_DB EVAL_TARGET_SCHEMA EVAL_GIT_REMOTE EVAL_GH_CRED; do
  [ -n "${!v:-}" ] || missing+=("$v")
done
if [ ${#missing[@]} -gt 0 ]; then
  printf 'run.sh: unset after loading .env: %s\n' "${missing[*]}" >&2
  exit 1
fi
[ -f "$EVAL_SNOWFLAKE_PK_FILE" ] || { echo "run.sh: EVAL_SNOWFLAKE_PK_FILE does not name a readable file" >&2; exit 1; }

# Network grants for the sandbox. The four site-specific hosts are derived from
# the configuration above so no real endpoint is written down here; the rest are
# third-party services the CLIs contact regardless of site.
COA_HOST="${EVAL_COA_DOMAIN#*://}"; COA_HOST="${COA_HOST%%/*}"
GIT_HOST="${EVAL_GIT_REMOTE#*://}"; GIT_HOST="${GIT_HOST#*@}"; GIT_HOST="${GIT_HOST%%/*}"
SNOW_HOST="${EVAL_SNOWFLAKE_ACCOUNT}.snowflakecomputing.com"

DOMAINS=(
  "$COA_HOST" "$GIT_HOST" "api.$GIT_HOST" "$SNOW_HOST"
  ocsp.snowflakecomputing.com ocsp.digicert.com docs.coalesce.io
  securetoken.googleapis.com identitytoolkit.googleapis.com
  www.googleapis.com firestore.googleapis.com
  http-intake.logs.datadoghq.com
)
ALLOW=(Bash Write Edit)
for d in "${DOMAINS[@]}"; do ALLOW+=("WebFetch(domain:$d)"); done

# Defaults, as flag/value pairs. A default is dropped when the caller passes the
# same flag, so `run.sh --case '02-*'` selects one case rather than two.
DEFAULTS=(--case '01-*' --runs 1 --ablation with-without --judge-model opus)
CMD=(claude plugin eval .)
i=0
while [ $i -lt ${#DEFAULTS[@]} ]; do
  flag="${DEFAULTS[$i]}"; value="${DEFAULTS[$((i+1))]}"; i=$((i+2))
  override=0
  for a in ${ARGS+"${ARGS[@]}"}; do [ "$a" = "$flag" ] && override=1; done
  [ "$override" = 0 ] && CMD+=("$flag" "$value")
done
CMD+=(--scaffold --no-publish --keep-temp --trust-plugin --allow-tools "${ALLOW[@]}")
[ ${#ARGS[@]} -gt 0 ] && CMD+=("${ARGS[@]}")

if [ "$PRINT_ONLY" = 1 ]; then printf '%q ' "${CMD[@]}"; echo; exit 0; fi

# Each live run creates a cloud Environment and does not delete it.
echo "run.sh: $(git rev-parse --abbrev-ref HEAD) @ $(git rev-parse --short HEAD) — creates a cloud Environment that is not cleaned up" >&2
exec "${CMD[@]}"
