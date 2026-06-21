#!/bin/sh
# Install the Coalesce Agent Skills into a skills directory
# (default: ~/.claude/skills/).
#
# - Skills are copied as coalesce-* directories.
# - An existing skill directory WITHOUT the coalesce-node-managed marker in
#   its SKILL.md (i.e. user-customized) is never overwritten.
# - Stale coalesce-* skills that carry the marker but are no longer in this
#   package are removed.
#
# Usage: ./install.sh [target-dir]

set -eu

MARKER="coalesce-node-managed: true"

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
SRC_DIR="$SCRIPT_DIR/skills"
TARGET_DIR="${1:-$HOME/.claude/skills}"

if [ ! -d "$SRC_DIR" ]; then
    echo "error: $SRC_DIR not found — run install.sh from the coalesce-agent-skills package" >&2
    exit 1
fi

mkdir -p "$TARGET_DIR" || {
    echo "error: cannot create $TARGET_DIR" >&2
    exit 1
}

# Returns 0 if the skill dir at $1 is managed (marker in the first 10 lines
# of its SKILL.md) or has no SKILL.md at all.
is_managed() {
    skill_md="$1/SKILL.md"
    [ -f "$skill_md" ] || return 0
    head -n 10 "$skill_md" | grep -qF "$MARKER"
}

installed=0
skipped=0

for src in "$SRC_DIR"/coalesce-*/; do
    [ -d "$src" ] || continue
    name=$(basename "$src")
    dest="$TARGET_DIR/$name"

    if [ -d "$dest" ] && ! is_managed "$dest"; then
        echo "skip (user-customized): $name"
        skipped=$((skipped + 1))
        continue
    fi

    rm -rf "$dest"
    cp -R "$src" "$dest"
    echo "installed: $name"
    installed=$((installed + 1))
done

# Remove stale managed coalesce-* skills not present in this package.
removed=0
for dest in "$TARGET_DIR"/coalesce-*/; do
    [ -d "$dest" ] || continue
    name=$(basename "$dest")
    if [ ! -d "$SRC_DIR/$name" ] && is_managed "$dest" && [ -f "$dest/SKILL.md" ]; then
        rm -rf "$dest"
        echo "removed (stale managed skill): $name"
        removed=$((removed + 1))
    fi
done

echo "done: $installed installed, $skipped skipped, $removed removed -> $TARGET_DIR"
