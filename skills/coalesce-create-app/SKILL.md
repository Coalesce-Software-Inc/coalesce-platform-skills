---
name: coalesce-create-app
description: Use when building, changing, debugging, or publishing a Coalesce workspace app — a small local web app in a Transform workspace's apps/<id>/ folder that Coalesce Desktop or coa serve runs and opens as a tab from the Build rail's Apps menu (dashboards, modelers, generators, review tools over the workspace's nodes and YAML). Covers the runtime contract (node <file> start script, PORT and WORKSPACE_DIR, no npm), the sandboxed <app>.localhost origin, reading and writing workspace files safely, running coa from an app, testing, and the GitHub release layout the app marketplace installs from.
---
<!-- coalesce-node-managed: true -->

# Create a Coalesce workspace app

A **workspace app** is a folder `apps/<appId>/` inside a Transform workspace
(the folder with `data.yml`) containing a `package.json` and a Node server.
When the workspace is open in Coalesce Desktop or `coa serve`, the watch server
lists every such folder under **Apps** on the Build rail. Opening one starts
its server on demand and shows it in a canvas tab, in an iframe served from the
app's own origin. The app reads and writes the workspace on disk, so whatever
it saves shows up in Coalesce and in git like any other edit.

Apps run only in local mode (Desktop or `coa serve`), never in the cloud
Coalesce app.

If the app reads or writes Coalesce files (`nodes/`, `jobs/`, `nodeTypes/`,
`locations.yml`), also load `coalesce-pipelines` for the file formats and
authoring rules.

## The runtime contract

These rules come from the watch server's app manager. Break one and the app
fails to start or never appears.

| Rule | Detail |
|---|---|
| **Discovery** | Every non-hidden folder in `apps/` with a parseable `package.json` is an app. The folder name is the **app id**. Folders starting with `.` are ignored (install staging uses them). |
| **Menu label** | `name` from `package.json`, else the folder name. `description` is shown too. |
| **Start script** | `scripts.start` must be exactly `node <file> [args]`. It is not run by npm or a shell, so no `npm`, `npx`, `vite`, `&&`, pipes, quotes, `$VARS`, globs, or `~`. Anything else fails with "Unsupported start script". |
| **No install step** | Nothing runs `npm install`, and `node_modules/` is not consulted for you. Use Node built-ins, or bundle dependencies into one committed file (see [Dependencies](#dependencies)). |
| **Runtime** | Coalesce's own Node: Electron's Node (v24 at the time of writing) in Desktop, or whatever Node runs `coa` under `coa serve`. Write for Node 20+ and use only built-ins (`http`, `fs`, `path`, `child_process`, `crypto`, global `fetch`). No native `.node` addons. |
| **Environment** | `PORT`: listen on it. `WORKSPACE_DIR`: absolute workspace root. The rest of the parent environment is inherited; in Desktop `PATH` can be the bare system one (`/usr/bin:/bin:...`). Working directory is the app folder. |
| **Readiness** | Coalesce polls `GET http://localhost:$PORT/` every 0.5 s for 15 s; any HTTP response counts. Listen at once and do slow work (scans, warehouse calls) after listening or per request. |
| **Lifetime** | Started on first open, kept running across tab switches, stopped when Coalesce or `coa serve` exits. A crashed app restarts on its next request. Editing `server.js` does not restart a running app (see [Test it](#4--test-it)). |
| **Logs** | stdout and stderr go to the Coalesce log as `[App:<appId>]`. If the app exits before it is ready, the tail of stderr is shown in the tab. |
| **Host name** | Served at `http://<label>.localhost:<watch port>/`, where `<label>` is the app id lowercased with every run of other characters turned into `-`. Two folders whose ids map to the same label collide and neither opens. Use a lowercase `[a-z0-9-]` id and make `name` the same. |

### The sandbox the UI runs in

The tab is an iframe with `sandbox="allow-scripts allow-same-origin
allow-forms allow-popups"` on the app's own origin. In practice:

- **No access to Coalesce.** `window.parent` is cross-origin: the app cannot
  read Coalesce's DOM, theme, storage, auth, selection, or the watch API from
  the browser. Older apps that reached into the parent (to follow the selected
  node or the theme) stopped working when apps moved to their own origin. Do
  not build on that.
- **Blocked:** `alert`, `confirm`, `prompt` (no `allow-modals`; they return
  immediately without showing), file downloads (no `allow-downloads`; save
  output into the workspace instead), and navigating the top window.
- **Allowed:** scripts, forms, `fetch` to the app's own server, its own
  `localStorage`, and `window.open` / `target="_blank"` links.
- **Theme:** follow `prefers-color-scheme`. The app cannot read Coalesce's
  light/dark setting.
- **Paths:** the app is served at `/` of its own origin. Root-relative
  (`/api/...`) and relative URLs both work; no `<base>` tricks or `/proxy`
  prefixes are needed (those were for the old path-prefixed proxy).
- Coalesce refuses requests to `<label>.localhost` from other websites, but
  the app also listens directly on `localhost:$PORT`, and that port has no
  guard. See the next section.

### Guard the app's own port

Any web page open in the user's browser can send requests to
`localhost:$PORT`. Without checks, a page can make the app write files with a
forged `POST` (a `text/plain` or form body goes out without a CORS
preflight), or read the app's responses by DNS rebinding. Every app server
must:

1. **Check `Host` on every request.** Accept only `localhost`, `127.0.0.1`,
   `[::1]`, or a name ending in `.localhost`, on any port, and answer 403
   otherwise. Coalesce's proxy keeps the original `Host`, so requests through
   Coalesce pass.
2. **Check every request that changes something** (anything but `GET`/`HEAD`).
   Accept it only when `Sec-Fetch-Site` is `same-origin` or absent (absent
   means a non-browser client such as `curl`) and `Content-Type` is
   `application/json`. Never change state on a `GET`. The UI must send
   `content-type: application/json` on its writes.
3. **Never send CORS headers.** No `Access-Control-Allow-Origin`, and certainly
   not `*`.

The template does all three (`isLoopbackHost`, `isTrustedWrite`). These checks
stop web pages. They do not stop other programs on the machine, which can set
any header and can read the workspace directly anyway; that is outside what
an app can defend against.

## Step 0 — Orient

1. Find the workspace root (`data.yml`) and `ls apps/` to see existing apps
   and avoid an id or label collision.
2. Read `~/.coalesce/desktop/agent.json` if it exists: `serving.workspaceDir`
   says whether Desktop is showing this workspace, and `serving.port` is the
   port apps are served on. Otherwise the user is on `coa serve` (port from its
   output, often 8082).
3. Pin down what the app reads and writes. Reading is free. Writing is the
   design decision:
   - **App-owned data** (settings, annotations, layouts) goes in one folder
     the app owns, outside `apps/`, such as `model/` or `.<appId>/`, and is
     committed with the workspace. Never store data inside `apps/<appId>/`:
     a marketplace update replaces that folder wholesale.
   - **Coalesce files** (`nodes/`, `jobs/`, `subgraphs/`): the app is
     authoring workspace content, so it must follow the `coalesce-pipelines`
     rules and validate what it writes (see [Running coa](#running-coa-from-an-app)).
     Have the user confirm before an app writes these; they change the pipeline.
   - **Never write** `data.yml`, `workspace.yml`, `environments/`, `.coa/`, or
     `~/.coa/config` from an app.

## Step 1 — Scaffold

Pick an app id (lowercase letters, digits, dashes) and write the three files
in [reference/template.md](reference/template.md) into `apps/<appId>/`
verbatim, then set `name` (same as the folder) and `description` in
`package.json`. Start from the template rather than writing the server from
scratch. It is a zero-dependency server with:

- loopback-only listening on both `127.0.0.1` and `::1` (Coalesce reaches the
  app at `localhost`, which may resolve to either);
- a static file allowlist and a JSON API under `/api/`;
- `wsPath()`, which resolves a workspace-relative path and refuses anything
  outside `WORKSPACE_DIR`;
- `writeIfChanged()`, which writes atomically and only when content changed,
  so the app doesn't leave untouched files modified in git;
- an `index.html` that follows the system theme and calls the API.

Folder layout for anything bigger:

```
apps/<appId>/
  package.json      name, description, version, scripts.start = "node server.js"
  server.js         HTTP server: static files + /api/*
  index.html        UI (plain HTML/JS, or a bundled build output)
  *.js / *.css      more static files, listed in the server's allowlist
  README.md         what it does, what it reads and writes
  CHANGELOG.md      per release, if published
```

## Step 2 — Build the server

- Answer `GET /` quickly; that is also the readiness probe.
- Read the workspace on each request (or cache keyed by file mtimes) instead
  of once at start, so the app sees edits made in Coalesce. To show the user
  outside edits, expose a cheap signature (hash of paths, mtimes, sizes) and
  let the UI poll it.
- Parse YAML without a dependency: write a small parser for the subset you
  need, or bundle one (`yaml` / `js-yaml`). Node files are
  `nodes/<LOCATION>-<NAME>.sql` (V2) or `.yml` (V1); node types are under
  `nodeTypes/` and `.coa/cache/packages/<alias>/nodeTypes/`, plus the built-in
  `Source`. `coalesce-pipelines` and its `reference/` docs describe each shape.
- Keep the `Host` and write checks from the template on every route (see
  [Guard the app's own port](#guard-the-apps-own-port)).
- Validate every input that turns into a path (`wsPath()`), cap request body
  sizes, and return JSON errors (`{ "error": "..." }`) with a 4xx status.
- Log to stdout/stderr; the user finds the logs in Coalesce's log.

### Running coa from an app

To validate or inspect what it wrote, an app can run the CLI. Don't assume
`coa` is on `PATH` (in Desktop it usually isn't):

```js
const { execFile } = require("child_process");
const os = require("os"), fs = require("fs"), path = require("path");

function coaCommand() {
  try {
    const a = JSON.parse(fs.readFileSync(path.join(os.homedir(), ".coalesce/desktop/agent.json"), "utf-8"));
    const [cmd, ...pre] = a.coa.runInvocation;
    return { cmd, pre, env: { ...process.env, ...a.coa.env } };
  } catch {
    return { cmd: "coa", pre: [], env: process.env };
  }
}

function runCoa(args) {
  const { cmd, pre, env } = coaCommand();
  return new Promise((resolve) =>
    execFile(cmd, [...pre, ...args, "-d", WORKSPACE], { env, maxBuffer: 20 << 20 }, (err, stdout, stderr) =>
      resolve({ ok: !err, stdout, stderr })));
}
// e.g. await runCoa(["--json", "validate"])
```

A failing command exits non-zero (`ok: false`) but still prints its `--json`
result on stdout. Parse stdout either way and show the user the findings.

Keep it to read-only and local commands (`validate`, `describe`, `create
--dry-run`). An app must not run `deploy`, `refresh`, `init`, or `profile`
commands, push to git, or touch credentials.

## Step 3 — Build the UI

- Plain HTML, CSS and JS served by the app is enough for most apps. If you use
  a framework, build it to static files, commit the output, and serve it; the
  build step never runs inside Coalesce.
- Use `fetch("/api/...")`. Show errors inline; there are no dialogs.
- Keep unsaved state client-side and save explicitly (a Save button, Cmd/Ctrl+S),
  or save each change atomically on the server. Tabs stay mounted, so state
  survives switching tabs but not a reload.
- Follow the system theme with `prefers-color-scheme` and CSS variables, as
  the template does. Fit the tab: full height, no outer page scroll, one
  scroller per pane.
- Deep links into Coalesce aren't available; link out with `target="_blank"`
  if you must.

## Dependencies

Prefer none. If you need packages:

```sh
cd apps/<appId>
npm init -y >/dev/null; npm i -D esbuild <pkg>
npx esbuild server.src.js --bundle --platform=node --target=node20 --outfile=dist/server.js
```

Set `scripts.start` to `node dist/server.js`, commit `dist/server.js`, keep the
packages in `devDependencies`, and gitignore `node_modules/`. Bundle browser
code the same way (`--platform=browser`) into a static file. Native addons
cannot be bundled.

## Step 4 — Test it

1. **Standalone**, the fast loop. No Coalesce needed:

   ```sh
   cd "$WORKSPACE/apps/$APP"
   PORT=4310 WORKSPACE_DIR="$WORKSPACE" node server.js
   curl -sf localhost:4310/ >/dev/null && echo ok
   curl -s localhost:4310/api/<route>
   ```

   Open `http://localhost:4310/` in a browser for the UI. Restart `node` after
   each server change.
2. **Contract check** before handing over: `scripts.start` matches
   `node <file>`, the file exists, `node --check <file>` passes, `name` equals
   the folder name, and there is no `node_modules` requirement at runtime.
3. **In Coalesce:** open the workspace in Desktop or `coa serve`, then Build ›
   Apps › your app. You can also open `http://<label>.localhost:<port>/`
   directly. A new app folder shows up after a page reload. A running app keeps
   running old server code, so after changing `server.js` restart Coalesce or
   `coa serve`. UI-only changes (HTML, CSS, client JS served from disk) only
   need a reload of the tab.
4. If it fails to open, the tab shows the reason: an unsupported start script,
   the stderr tail of a crash, a 15 s start timeout (it didn't listen on
   `PORT`), or a host-name collision.

## Step 5 — Commit

The app is part of the workspace repository. Stage the app folder (and any
data folder it created) explicitly, per `coalesce-git-publication`; commit and
push only with the user's approval.

## Publishing to the app marketplace

A marketplace that installs apps into `apps/` from GitHub is being built
(Build Settings › Apps, behind a feature flag). Its install code expects:

- A **public repository in the `coalesceio` GitHub org**, named exactly the
  app id (lowercase `[a-z0-9-]`), unarchived, with the topic **`coalesce-app`**.
  Publishing there needs org access; the user arranges it.
- **Exactly one app at `apps/<appId>/`** in the repository. The rest of the
  repo (README, CI, sources) is not installed.
- **Releases are git tags `v<semver>`**, such as `v1.2.0`. Prereleases
  (`v1.3.0-beta.1`) and other tags are ignored.
- On install, Coalesce downloads the tag's source zip, refuses symlinks, checks
  the start script, writes `version` and `repository` into the installed
  `package.json`, and replaces `apps/<appId>/` entirely. Still keep `version`
  in `package.json` in step with the tag, and add a `CHANGELOG.md` entry per
  release.
- An existing `apps/<appId>/` that wasn't installed from that repository is
  never overwritten, so a locally built app and a published one with the same
  id conflict.

Check with the user whether the marketplace is live in their Coalesce version
before promising they can install from it.

## Approval gates

- Without asking: reading the workspace, scaffolding a new `apps/<appId>/`
  the user asked for, running it standalone, `coa validate` / `describe` /
  `--dry-run`.
- ASK FIRST: an app that writes to `nodes/`, `jobs/`, `subgraphs/`,
  `nodeTypes/` or other shared config; changing or deleting another app's
  folder; adding dependencies; committing; pushing; creating the GitHub repo,
  topics, or tags.
- NEVER: have an app run deploy, refresh, init or profile commands, read or
  return credentials from `~/.coa/config`, listen on a non-loopback interface,
  or try to reach into the Coalesce page from the iframe.
