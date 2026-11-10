#!/usr/bin/env bash
# Runs as the operator, unconfined, in the empty workspace (<sandbox>/home/cwd) before the agent starts.
# Stages the eight-node medallion-greenfield sample workspace so the agent has real nodes to build an app over.
# Offline: no cloud, warehouse, or git remote is touched.
set -euo pipefail

SRC="$(cd "$(dirname "$0")/../medallion-greenfield" && pwd)"
# coa/ holds a credentials template for other harnesses; it is not part of the workspace.
tar -C "$SRC" --exclude ./coa -cf - . | tar -xf -
command -v node >/dev/null || { echo "setup.sh: node not found on the operator PATH" >&2; exit 1; }
echo "setup.sh: staged $(ls nodes | wc -l | tr -d ' ') nodes from $SRC into $(pwd)"
