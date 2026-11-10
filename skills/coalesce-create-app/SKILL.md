---
name: coalesce-create-app
description: Use when building, changing, or debugging a Coalesce workspace app — a small local web app in a Transform workspace's apps/<id>/ folder that Coalesce Desktop or coa serve runs and opens as a tab from the Build rail's Apps menu (dashboards, modelers, generators, review tools over the workspace's nodes and YAML). Covers the runtime contract (node <file> start script, PORT and WORKSPACE_DIR, no npm), the sandboxed <app>.localhost origin, reading and writing workspace files safely, running coa from an app, and testing.
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
| **Discovery** | Every non-hidden folder in `apps/` with a parseable `package.json` is an app. The folder name is the **app id**. Folders starting with `.` are ignored. |
| **Menu label** | `name` from `package.json`, else the folder name. `description` is shown too. |
| **Start script** | `scripts.start` must be exactly `node <file> [args]`. It is not run by npm or a shell, so no `npm`, `npx`, `vite`, `&&`, pipes, quotes, `$VARS`, globs, or `~`. Anything else fails with "Unsupported start script". |
| **No install step** | Nothing runs `npm install`, and `node_modules/` is not consulted for you. Use Node built-ins, or bundle dependencies into one committed file (see [Dependencies](#dependencies)). |
| **Runtime** | Coalesce's own Node: Electron's Node (v24 at the time of writing) in Desktop, or whatever Node runs `coa` under `coa serve`. Write for Node 20+ and use only built-ins (`http`, `fs`, `path`, `child_process`, `crypto`, global `fetch`). No native `.node` addons. |
| **Environment** | `PORT`: listen on it. `WORKSPACE_DIR`: absolute workspace root. The rest of the parent environment is inherited; in Desktop `PATH` can be the bare system one (`/usr/bin:/bin:...`). Working directory is the app folder. |
| **Readiness** | Coalesce polls `GET http://localhost:$PORT/` every 0.5 s for 15 s; any HTTP response counts. Listen at once and do slow work (scans, warehouse calls) after listening or per request. |
| **Lifetime** | Started on first open, kept running across tab switches, stopped when Coalesce or `coa serve` exits. A crashed app restarts on its next request. Editing `server.js` does not restart a running app (see [Test it](#step-4--test-it)). |
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

The app's port (`localhost:$PORT`) is reachable from any page in the user's
browser, not just from Coalesce. The template includes three checks so only
the app's own page can use it; keep them:

1. **`Host` is a loopback name** (`localhost`, `127.0.0.1`, `[::1]`, or
   `*.localhost`), which rules out DNS rebinding. Requests through Coalesce
   keep their `<label>.localhost` host, so they pass.
2. **Writes are same-origin JSON.** Anything other than `GET`/`HEAD` needs
   `Content-Type: application/json` and a `Sec-Fetch-Site` of `same-origin` or
   none (`curl` sends none). Have the UI set the content type on writes, and
   don't change state on a `GET`.
3. **No CORS headers.**

These checks cover browser pages. Other programs on the machine aren't in
scope, since they can already read the workspace directly.

### Render workspace content as text

Node names, descriptions and SQL come from git, and the app's own page is
trusted to write. Put workspace values on the page with `textContent` (or a
framework's default escaping) rather than `innerHTML` or HTML built from a
template string, as the template's table does. Don't `eval` or `require`
workspace files.

### Run commands without a shell

Use `execFile` or `spawn` with an argument array, as the
[coa snippet](#running-coa-from-an-app) does, rather than `exec` or
`shell: true`. Check values that become arguments (node names, locations,
selectors) against a simple pattern such as `^[A-Za-z0-9_]+$`, and return a
400 otherwise.

### Keep secrets on the server

- Anything an app writes to the workspace ends up in git, so read API keys
  from a file outside it (such as `~/.config/<appId>/`) or an environment
  variable. Desktop opened from the Dock or Finder doesn't see shell profile
  variables, so a file is more reliable there.
- Keep keys out of responses, pages and logs, and don't read `~/.coa/config`.
- If the app sends workspace content to an outside service, say which
  service and what is sent in its README and UI, and send it only when the
  user asks. Check with the user before building one.

## Step 0 — Orient

1. `ls apps/` for existing apps and id collisions. Apps run with the user's
   permissions when opened, so read any app you didn't write before starting it.
2. If `~/.coalesce/desktop/agent.json` exists, `serving.port` is the port apps
   are served on. Otherwise use the port `coa serve` printed.
3. Decide where the app writes:
   - Its own data goes in a folder outside `apps/`, such as `.<appId>/`.
   - `nodes/`, `jobs/` and `subgraphs/` follow `coalesce-pipelines` and need
     the user's OK.
   - Never `data.yml`, `workspace.yml`, `environments/`, `.coa/` or
     `~/.coa/config`.

## Step 1 — Scaffold

Write the three files in [reference/template.md](reference/template.md) into
`apps/<appId>/` verbatim, and set `name` (same as the folder) and
`description` in `package.json`. The template already handles loopback
listening, the port checks, workspace path checks (`wsPath()`) and
write-only-on-change (`writeIfChanged()`).

## Step 2 — Build the server

- Answer `GET /` fast; it's the readiness probe.
- Read workspace files per request so the app sees edits made in Coalesce.
  `coalesce-pipelines` documents the node and node type file shapes.
- Return JSON errors with a 4xx status, and log to stdout/stderr.

### Running coa from an app

`coa` usually isn't on `PATH` in Desktop. Resolve it from `agent.json`:

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
// e.g. await runCoa(["--json", "validate"]); stdout holds the JSON even when ok is false
```

Stick to read-only commands (`validate`, `describe`, `--dry-run`).

## Step 3 — Build the UI

- Plain HTML/JS is usually enough. A framework build must be committed as
  static files; nothing builds inside Coalesce.
- `fetch("/api/...")` with `content-type: application/json` on writes, and
  workspace values rendered with `textContent`.
- Show errors inline (no dialogs), follow `prefers-color-scheme`, and fill
  the tab's height.

## Dependencies

Prefer none. Otherwise bundle into one committed file and start that:

```sh
npx esbuild server.src.js --bundle --platform=node --target=node20 --outfile=dist/server.js
```

## Step 4 — Test it

1. Standalone: `PORT=4310 WORKSPACE_DIR="$WORKSPACE" node server.js`, then
   `curl localhost:4310/` and open it in a browser.
2. Check `scripts.start` is `node <file>`, `node --check` passes, and `name`
   matches the folder.
3. In Coalesce: Build › Apps › your app (reload the page to see a new app).
   Restart Coalesce or `coa serve` after server changes; UI changes only need
   a tab reload. Start failures are shown in the tab.

## Step 5 — Commit

Stage the app folder and its data folder per `coalesce-git-publication`.
Commit and push only with the user's approval.

## Approval gates

- Without asking: reading the workspace, scaffolding the requested app,
  running it standalone, read-only `coa` commands.
- ASK FIRST: apps that write `nodes/`, `jobs/`, `subgraphs/` or other shared
  config, or send workspace content to an outside service; changing another
  app; adding dependencies; committing; pushing.
- NEVER: have an app run deploy, refresh, init or profile commands, read
  `~/.coa/config`, listen beyond loopback, or reach into the Coalesce page.
