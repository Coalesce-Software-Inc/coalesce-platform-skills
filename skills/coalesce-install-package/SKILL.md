---
name: coalesce-install-package
description: Use when adding a published Coalesce Marketplace package (e.g. @coalesce/snowflake/cortex, base node types, dynamic tables) to a Transform workspace with the coa CLI — find the package and release in the registry, write packages/<alias>.yml, run coa install, verify the hydrated node types. Also covers upgrading or removing a declared package.
---
<!-- coalesce-node-managed: true -->

> **Prerequisite — load `coalesce-pipelines` first.** If you have not already
> loaded the `coalesce-pipelines` skill in this session, load it now, read its
> "Orient first" step and Rules, then return here.

# Install a Marketplace package

A **package** is a versioned bundle of node types (and sometimes macros)
published to the Coalesce package registry and browsable in the
[Marketplace](https://docs.coalesce.io/docs/marketplace). A workspace uses a
package by committing a small **declaration** file under `packages/` that
points at one exact **release** of the package; `coa install` then downloads
that release into the gitignored `.coa/cache/` so `create`/`run` can render its
node types. Nothing about a package is authored by hand except this pointer.

Three identifiers, easy to confuse:

| Term | Example | Where it comes from |
|---|---|---|
| **Package ID** | `@coalesce/snowflake/cortex` | The Marketplace listing. Form is `@<publisher>/<platform>/<name>`. Goes in the declaration as both `id` and `packageID`. |
| **Registry slug** | `coalesce_snowflake_cortex` | The Package ID with the leading `@` dropped and every `/` replaced by `_`. This is the `{packageID}` path segment the registry API expects and the docs URL slug. |
| **Release ID** | `5625047f-0da2-485a-865f-66d37d9e3de8` | A UUID for one published version (the Marketplace shows the version, `4.2.0`; the declaration needs the UUID). |

> If `coa --help` lists a `packages` command, prefer `coa packages add
> <packageID>` and skip to Step 4. As of coa 7.43.0 it does not exist and the
> steps below are the supported path.

## Step 0 — Orient

1. Confirm the workspace platform: `platformKind` in `data.yml` (absent means
   `snowflake`). Only install packages whose `platformKind` matches; the
   platform is also the middle segment of a V2 Package ID.
2. `ls packages/` — see what is already declared. Each file is one package,
   named after its alias. If the package is already declared, this is an
   upgrade (see below), not an install.
3. `coa profile list -d <dir>` — note the active profile. The registry calls
   below use that profile's `token` and `domain` from `~/.coa/config`, exactly
   as `coa install` itself does. Read them into shell variables; NEVER echo,
   log, or paste the token:

   ```sh
   PROFILE=$(coa --json profile list -d <dir> | jq -r .data.active.profileName)
   COA_DOMAIN=$(awk -v p="$PROFILE" -F= '/^\[/{s=($0=="["p"]")} s && $1~/^[ \t]*domain[ \t]*$/{gsub(/^[ \t]+|[ \t]+$/,"",$2);print $2}' ~/.coa/config)
   COA_TOKEN=$(awk -v p="$PROFILE" -F= '/^\[/{s=($0=="["p"]")} s && $1~/^[ \t]*token[ \t]*$/{gsub(/^[ \t]+|[ \t]+$/,"",$2);print $2}' ~/.coa/config)
   COA_DOMAIN=${COA_DOMAIN:-https://app.coalescesoftware.io}
   ```

   If the profile has no token, stop: the user needs `coa init` / `coa profile
   set-cloud` first (see coalesce-cloud-api). Do not ask them to paste a token
   into chat.

## Step 1 — Identify the package and its latest release

The registry is read-only here; every call below is a GET and safe to run
without asking. Endpoints (scheduler OpenAPI, tag `PackageRegistry`):

- `GET /api/v1/packageRegistry/{slug}` — one package: `packageID`, `name`,
  `description`, `platformKind`, `latestRelease` (a release ID), `certified`,
  `tags`.
- `GET /api/v1/packageRegistry/{slug}/releases/{releaseID}` — one release:
  `version` (semver), `changeLog`, `privacy`, `createdAt`.
- `GET /api/v1/packageRegistry/{slug}/releases/privacy/public` — every public
  release, for choosing a version other than the latest. (`private`,
  `unlisted` and `all` return 401 unless your org owns the package.)
- `GET /api/v1/packageRegistry/all` — the whole registry (~5,400 rows,
  ~5 MB, including every org's test packages). Search fallback only.

**1a. You know the Package ID** (the user gave it, or it is in the
[Marketplace docs](https://docs.coalesce.io/llms-marketplace.txt) — each
listed page is `docs.coalesce.io/docs/marketplace/package/<slug>.md` and
shows Package ID, platform, and latest version):

```sh
PKG="@coalesce/snowflake/cortex"
SLUG=$(printf '%s' "$PKG" | sed 's/^@//; s#/#_#g')
curl -sf -H "Authorization: Bearer $COA_TOKEN" "$COA_DOMAIN/api/v1/packageRegistry/$SLUG" \
  | jq '{packageID,name,platformKind,latestRelease,certified}'
```

A 404 means the slug is wrong or the package is not in this environment's
registry (lower environments do not mirror production). Fall back to 1b.

**1b. You only know roughly what the user wants** ("the Cortex package",
"something for dynamic tables"). Search the full listing, restricted to
certified Coalesce-published V2 packages for the workspace platform:

```sh
PK=snowflake   # from data.yml
curl -sf -H "Authorization: Bearer $COA_TOKEN" "$COA_DOMAIN/api/v1/packageRegistry/all" \
  | jq -r --arg q "cortex" --arg pk "$PK" '
      .[] | select(.platformKind==$pk and .certified==true
                   and (.packageID|startswith("@coalesce/"+$pk+"/"))
                   and ((.name+" "+.description+" "+(.tags|join(" ")))|ascii_downcase|contains($q|ascii_downcase)))
          | [.packageID,.name,.latestRelease] | @tsv'
```

Loosen the filters only if that returns nothing (the registry also holds
older two-segment IDs like `@coalesce/cortex` and copies such as `cortex-dev`;
prefer the certified three-segment ID for the platform). If more than one
plausible package matches, show the candidates (Package ID, name, one-line
description) and let the user pick — do not guess between, say,
`base-node-types` and `base-node-types-sql`.

**1c. Resolve the release.** Use `latestRelease` unless the user asked for a
specific version; then confirm what it is:

```sh
RID=$(curl -sf -H "Authorization: Bearer $COA_TOKEN" "$COA_DOMAIN/api/v1/packageRegistry/$SLUG" | jq -r .latestRelease)
curl -sf -H "Authorization: Bearer $COA_TOKEN" "$COA_DOMAIN/api/v1/packageRegistry/$SLUG/releases/$RID" \
  | jq '{version,releaseID,privacy,createdAt,changeLog}'
```

For a specific version, list public releases and pick its `releaseID`:

```sh
curl -sf -H "Authorization: Bearer $COA_TOKEN" "$COA_DOMAIN/api/v1/packageRegistry/$SLUG/releases/privacy/public" \
  | jq -r 'sort_by(.createdAt) | reverse | .[] | [.version,.releaseID,.createdAt] | @tsv'
```

Report Package ID, name, version and release ID to the user before writing
anything.

## Step 2 — Write the declaration

Pick an **alias**: the filename, the key the workspace uses for the package,
the prefix in every node type id (`<alias>:::<id>`), and the Jinja import
name for the package's macros. Default to the last segment of the Package ID
(`cortex`, `dynamic-tables`); use only `[A-Za-z0-9_-]`; it must be unique in
`packages/`. Never reuse an existing alias for a different package.

Create `packages/<alias>.yml` — filename must equal `name`:

```yaml
fileVersion: 1
type: Package
id: "@coalesce/snowflake/cortex"
name: cortex
packageID: "@coalesce/snowflake/cortex"
releaseID: "5625047f-0da2-485a-865f-66d37d9e3de8"
config:
  packageVariables: ""
  entities:
    nodeTypes: {}
```

- `id` and `packageID` are both the full Package ID (not the slug).
- `releaseID` is the UUID from Step 1c, quoted.
- `config` starts empty exactly as shown. `packageVariables` is the package's
  configuration string (Marketplace "Edit Config"); `entities.nodeTypes` is
  populated by the UI per node type (`defaultStorageLocation`, `isDisabled`).
  Leave both empty on install; edit them only when the user asks for a
  specific package configuration.

This is shared workspace config. The user's request to add the package is the
approval to write it; if you searched (1b) and had to choose, confirm the
match first. Anything else under `packages/` is out of scope — never edit a
different package's declaration to make this one work.

## Step 3 — Install

```sh
coa install -d <dir>
```

Safe to run without asking; it only downloads into `.coa/cache/`. Expected
output names every declared alias with a check mark and ends
`Installed N package(s)`. Investigate anything else:

- `No packages to install.` — the declaration was not read. Check the path
  (`packages/<alias>.yml`, `.yml` extension), `type: Package`, and that
  `data.yml` is the one `coa init` wrote (a hand-made `data.yml` can make the
  loader skip the workspace's package files).
- `<alias>: no package contents available (not hydrated, not cached)` — the
  registry could not serve that `packageID`/`releaseID` pair for this token's
  domain. Re-check Step 1 (wrong release ID, or a production-only package
  against a lower environment).
- `Install failed: workspace.yml is required` — the workspace has no local
  bootstrap yet; see coalesce-cloud-api (`coa doctor --fix` / `coa init`, ask
  first).

## Step 4 — Verify

1. `ls .coa/cache/packages/<alias>/nodeTypes/` — one `<Name>-<id>/` folder per
   node type, each with `definition.yml` (its `id:` is the `<alias>:::<id>`
   value for `@nodeType()`), `create.sql.j2` and `run.sql.j2`. Read a
   `definition.yml` or two and tell the user what the package added; names
   vary by package, so never assume.
2. `coa validate -d <dir>` — must still pass.
3. `git status` — the only new tracked file is `packages/<alias>.yml`;
   `.coa/` is gitignored and never committed.

Then commit per coalesce-git-publication (stage the one file explicitly;
push only with approval):

```sh
git add packages/<alias>.yml
git commit -m "Add <alias> package (<packageID> <version>)"
```

Every other clone of the repo must run `coa install` after pulling to get the
contents; say so in the commit message or to the user.

## Upgrade a declared package

1. Resolve the new release ID with Step 1c (`latestRelease`, or a chosen
   version from the public releases list) and show the `changeLog`.
2. Edit only `releaseID` in the existing `packages/<alias>.yml`. Keep the
   alias and `config` — that is what preserves the workspace's node type
   settings and every node's `@nodeType(<alias>:::<id>)` reference.
3. `coa install -d <dir>`, then re-run Step 4. Node type ids are stable
   across releases in practice, but confirm with `coa validate` and a
   `coa create -d <dir> --dry-run` on a node that uses the package — an
   upgrade is a shared-config change, so ASK FIRST if the user did not
   explicitly request it.

## Remove a declared package

Only when the user asks, and only after `grep -rl "<alias>:::" nodes/` is
empty — a node type that disappears leaves its nodes failing with
`missingNodeType`. Delete `packages/<alias>.yml` and run `coa install -d
<dir>`; the cache tree for that alias is pruned automatically. Commit the
deletion.

## Approval gates

- Without asking: every `GET` to `/api/v1/packageRegistry/...`, reading the
  Marketplace docs, `coa install`, `coa validate`, `--dry-run`, and the
  verification steps.
- Implicitly approved by the request: writing `packages/<alias>.yml` for the
  package the user named, with its latest release.
- ASK FIRST: choosing between multiple matching packages, pinning a
  non-latest release, upgrading or removing a package the user did not name,
  editing `config`, committing (per coalesce-git-publication) or pushing.
- NEVER: print the token, put it in a file, or hand-edit `.coa/cache/`;
  author node types to stand in for a package that will not hydrate (fall back
  to V1 `.yml` nodes instead — see coalesce-pipelines Rule 4).
