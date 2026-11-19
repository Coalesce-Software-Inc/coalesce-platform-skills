#!/usr/bin/env bash
# Launch the live eval suite with the operator's credentials and run configuration.
#
# Reads an untracked .env at the repository root, maps the few names the cases
# expect, checks everything resolves, and runs `claude plugin eval` against the
# checkout this script lives in. Point it at a PR by running it from that
# branch's worktree.
#
# Usage:
#   evals/run.sh                        # the live Snowflake case, one run per arm
#   evals/run.sh --case '04-*'          # the live ClickHouse case
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

# The ClickHouse case may use its own Coalesce domain and token; fall back to the shared ones.
export EVAL_CH_COA_DOMAIN="${EVAL_CH_COA_DOMAIN:-${EVAL_COA_DOMAIN:-}}"
export EVAL_CH_COA_CLOUD="${EVAL_CH_COA_CLOUD:-${EVAL_COA_CLOUD:-}}"
export EVAL_CH_PORT="${EVAL_CH_PORT:-8443}"

# Which live cases does this run select? Each needs its own variables and network grants.
CASE_GLOB='01-*'
prev=""
for a in ${ARGS+"${ARGS[@]}"}; do
  [ "$prev" = "--case" ] && CASE_GLOB="$a"
  prev="$a"
done
NEED_SNOWFLAKE=0; NEED_CLICKHOUSE=0
for d in evals/$CASE_GLOB; do
  case "$(basename "$d")" in
    01-live-bootstrap-plan-deploy) NEED_SNOWFLAKE=1 ;;
    04-live-clickhouse-build) NEED_CLICKHOUSE=1 ;;
  esac
done

REQUIRED=()
[ "$NEED_SNOWFLAKE" = 1 ] && REQUIRED+=(EVAL_COA_DOMAIN EVAL_COA_PROJECT EVAL_COA_CONNECTION EVAL_COA_CLOUD \
         EVAL_SNOWFLAKE_ACCOUNT EVAL_SNOWFLAKE_USER EVAL_SNOWFLAKE_WAREHOUSE \
         EVAL_SNOWFLAKE_PK_FILE EVAL_SOURCE_DB EVAL_SOURCE_SCHEMA \
         EVAL_TARGET_DB EVAL_TARGET_SCHEMA EVAL_GIT_REMOTE EVAL_GH_CRED)
[ "$NEED_CLICKHOUSE" = 1 ] && REQUIRED+=(EVAL_CH_COA_DOMAIN EVAL_CH_COA_CLOUD EVAL_CH_COA_PROJECT \
         EVAL_CH_ENVIRONMENT_ID EVAL_CH_HOST EVAL_CH_USER EVAL_CH_CRED \
         EVAL_CH_SOURCE_DB EVAL_CH_TARGET_DB_PREFIX)
missing=()
for v in ${REQUIRED+"${REQUIRED[@]}"}; do
  [ -n "${!v:-}" ] || missing+=("$v")
done
if [ ${#missing[@]} -gt 0 ]; then
  printf 'run.sh: unset after loading .env: %s\n' "${missing[*]}" >&2
  exit 1
fi
if [ "$NEED_SNOWFLAKE" = 1 ]; then
  [ -f "$EVAL_SNOWFLAKE_PK_FILE" ] || { echo "run.sh: EVAL_SNOWFLAKE_PK_FILE does not name a readable file" >&2; exit 1; }
fi

# Network grants for the sandbox. The site-specific hosts are derived from the
# configuration above so no real endpoint is written down here; the rest are
# third-party services the CLIs contact regardless of site.
host_of() { local h="${1#*://}"; h="${h#*@}"; printf '%s' "${h%%/*}"; }
DOMAINS=(
  docs.coalesce.io
  securetoken.googleapis.com identitytoolkit.googleapis.com
  www.googleapis.com firestore.googleapis.com
  http-intake.logs.datadoghq.com
)
if [ "$NEED_SNOWFLAKE" = 1 ]; then
  GIT_HOST="$(host_of "$EVAL_GIT_REMOTE")"
  DOMAINS+=("$(host_of "$EVAL_COA_DOMAIN")" "$GIT_HOST" "api.$GIT_HOST"
            "${EVAL_SNOWFLAKE_ACCOUNT}.snowflakecomputing.com"
            ocsp.snowflakecomputing.com ocsp.digicert.com)
fi
if [ "$NEED_CLICKHOUSE" = 1 ]; then
  DOMAINS+=("$(host_of "$EVAL_CH_COA_DOMAIN")" "$EVAL_CH_HOST")
fi
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
CMD+=(--scaffold --no-publish --keep-temp)
# Older CLIs need --trust-plugin to run a local plugin; newer ones dropped the flag and reject it.
claude plugin eval --help 2>/dev/null | grep -q -- '--trust-plugin' && CMD+=(--trust-plugin)
CMD+=(--allow-tools "${ALLOW[@]}")
[ ${#ARGS[@]} -gt 0 ] && CMD+=("${ARGS[@]}")

if [ "$PRINT_ONLY" = 1 ]; then printf '%q ' "${CMD[@]}"; echo; exit 0; fi

# Live runs leave state behind: the Snowflake case a cloud Environment, the ClickHouse case a target database.
LEFTOVERS=()
[ "$NEED_SNOWFLAKE" = 1 ] && LEFTOVERS+=("a cloud Environment")
[ "$NEED_CLICKHOUSE" = 1 ] && LEFTOVERS+=("a ClickHouse database per run (${EVAL_CH_TARGET_DB_PREFIX}_*)")
NOTE=""; [ ${#LEFTOVERS[@]} -gt 0 ] && NOTE=" — leaves behind, not cleaned up: ${LEFTOVERS[*]}"
echo "run.sh: $(git rev-parse --abbrev-ref HEAD) @ $(git rev-parse --short HEAD)${NOTE}" >&2
exec "${CMD[@]}"
