# Starter app template

A zero-dependency workspace app. Write these three files into `apps/<appId>/`,
then set `name` (the same as the folder name) and `description` in
`package.json`, and rename `.my-app/` in `server.js` to the app's own data folder.

## package.json

```json
{
  "name": "my-app",
  "description": "One line shown under the app's name in Coalesce's Apps menu.",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "start": "node server.js"
  }
}
```

## server.js

```js
// Coalesce workspace app starter. Zero dependencies: Coalesce runs `node server.js` on its own
// Node runtime with PORT and WORKSPACE_DIR set, with no npm and no install step.
const http = require("http");
const fs = require("fs");
const path = require("path");

const PORT = Number(process.env.PORT || 4310);
const WORKSPACE = path.resolve(process.env.WORKSPACE_DIR || path.join(__dirname, "../.."));
const MAX_BODY_BYTES = 5 * 1024 * 1024;

// Static files the server will send, by URL path. Anything not listed is a 404.
const STATIC = { "/": "index.html", "/index.html": "index.html" };
const MIME = { ".html": "text/html", ".js": "text/javascript", ".css": "text/css", ".svg": "image/svg+xml" };

// Resolves a workspace-relative path and refuses anything that escapes the workspace.
function wsPath(rel) {
  const abs = path.resolve(WORKSPACE, rel);
  if (abs !== WORKSPACE && !abs.startsWith(WORKSPACE + path.sep)) throw httpError(400, `Path outside workspace: ${rel}`);
  return abs;
}

// Writes only when content changed, via a temp file and rename, so unchanged files stay clean in git.
function writeIfChanged(file, text) {
  let prev = null;
  try {
    prev = fs.readFileSync(file, "utf-8");
  } catch {}
  if (prev === text) return false;
  fs.mkdirSync(path.dirname(file), { recursive: true });
  const tmp = `${file}.${process.pid}.tmp`;
  fs.writeFileSync(tmp, text);
  fs.renameSync(tmp, file);
  return true;
}

function listDir(dir, filter = () => true) {
  try {
    return fs.readdirSync(dir).filter((f) => !f.startsWith(".") && filter(f)).sort();
  } catch {
    return [];
  }
}

// Node files are nodes/<LOCATION>-<NAME>.sql (V2) or .yml (V1). LOCATION has no dashes.
function listNodes() {
  return listDir(wsPath("nodes"), (f) => /\.(sql|yml)$/.test(f)).map((file) => {
    const base = file.replace(/\.(sql|yml)$/, "");
    const dash = base.indexOf("-");
    return { file: `nodes/${file}`, location: base.slice(0, dash), name: base.slice(dash + 1), format: file.endsWith(".sql") ? "v2" : "v1" };
  });
}

function httpError(status, message) {
  return Object.assign(new Error(message), { status });
}

function readJson(req) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    let size = 0;
    req.on("data", (c) => {
      size += c.length;
      if (size > MAX_BODY_BYTES) {
        reject(httpError(413, "Body too large"));
        req.destroy();
      } else chunks.push(c);
    });
    req.on("end", () => {
      try {
        resolve(JSON.parse(Buffer.concat(chunks).toString("utf-8") || "{}"));
      } catch {
        reject(httpError(400, "Invalid JSON"));
      }
    });
    req.on("error", reject);
  });
}

// App-owned data lives in the workspace, outside apps/: a marketplace update replaces apps/<id>/.
const SETTINGS_FILE = () => wsPath(".my-app/settings.json");

// The app's port is open to any web page in the user's browser, not only to Coalesce. Two checks
// stop such pages; neither keeps out local programs, which can forge headers and read the files.
// 1. Host must be a loopback name. A DNS-rebinding page arrives as its own domain.
//    Coalesce's proxy keeps the original Host, "<label>.localhost:<port>".
function isLoopbackHost(host) {
  const hostname = (host || "").replace(/:\d+$/, "").toLowerCase();
  return ["localhost", "127.0.0.1", "[::1]"].includes(hostname) || hostname.endsWith(".localhost");
}
// 2. Writes must come from the app's own page (or a non-browser client, which sends no
//    Sec-Fetch-Site) and be JSON, so a cross-site form or text/plain POST can't trigger them.
function isTrustedWrite(req) {
  const site = req.headers["sec-fetch-site"];
  const type = (req.headers["content-type"] || "").split(";")[0].trim().toLowerCase();
  return (site === undefined || site === "same-origin") && type === "application/json";
}
const SAFE_METHODS = new Set(["GET", "HEAD"]);

async function handle(req, res) {
  const { pathname } = new URL(req.url, "http://localhost");
  // Never add CORS headers (Access-Control-Allow-Origin): the app is for its own page only.
  const json = (status, data) => {
    res.writeHead(status, { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" });
    res.end(JSON.stringify(data));
  };

  if (!isLoopbackHost(req.headers.host)) return json(403, { error: "Forbidden host" });
  if (!SAFE_METHODS.has(req.method) && !isTrustedWrite(req)) {
    return json(403, { error: "Writes must be same-origin JSON requests" });
  }

  try {
    if (pathname === "/api/nodes" && req.method === "GET") {
      return json(200, { workspace: WORKSPACE, nodes: listNodes() });
    }
    if (pathname === "/api/settings" && req.method === "GET") {
      let settings = {};
      try {
        settings = JSON.parse(fs.readFileSync(SETTINGS_FILE(), "utf-8"));
      } catch {}
      return json(200, settings);
    }
    if (pathname === "/api/settings" && req.method === "PUT") {
      const body = await readJson(req);
      if (!body || typeof body !== "object" || Array.isArray(body)) throw httpError(400, "Expected a JSON object");
      const written = writeIfChanged(SETTINGS_FILE(), JSON.stringify(body, null, 2) + "\n");
      return json(200, { written });
    }
    const file = STATIC[pathname];
    if (file && req.method === "GET") {
      res.writeHead(200, { "content-type": `${MIME[path.extname(file)] || "text/plain"}; charset=utf-8`, "cache-control": "no-store" });
      return res.end(fs.readFileSync(path.join(__dirname, file)));
    }
    json(404, { error: "Not found" });
  } catch (e) {
    if (!e.status) console.error(e);
    json(e.status || 500, { error: e.message });
  }
}

// Loopback only, on both families: Coalesce reaches the app at "localhost", which can resolve to
// either 127.0.0.1 or ::1.
let listening = 0;
for (const host of ["127.0.0.1", "::1"]) {
  http
    .createServer(handle)
    .on("error", (e) => console.warn(`Could not listen on ${host}:${PORT}: ${e.message}`))
    .listen(PORT, host, () => {
      if (listening++ === 0) console.log(`App listening on :${PORT}, workspace=${WORKSPACE}`);
    });
}
```

## index.html

```html
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>My App</title>
<style>
  /* The app can't read Coalesce's theme setting (different origin), so it follows the system. */
  :root { --bg: #ffffff; --fg: #1f2329; --muted: #6b7280; --border: #e5e7eb; --accent: #3b5bdb; --error: #c92a2a; }
  @media (prefers-color-scheme: dark) {
    :root { --bg: #1e1f22; --fg: #e8e9eb; --muted: #9aa0a6; --border: #34363b; --accent: #748ffc; --error: #ff8787; }
  }
  * { box-sizing: border-box; }
  html, body { height: 100%; margin: 0; }
  body { display: flex; flex-direction: column; background: var(--bg); color: var(--fg); font: 13px/1.4 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
  header { display: flex; align-items: center; gap: 8px; padding: 8px 12px; border-bottom: 1px solid var(--border); }
  header h1 { font-size: 14px; margin: 0; flex: 1; }
  main { flex: 1; overflow: auto; padding: 12px; }
  button { font: inherit; padding: 4px 10px; border: 1px solid var(--border); border-radius: 4px; background: transparent; color: var(--fg); cursor: pointer; }
  table { border-collapse: collapse; width: 100%; }
  th, td { text-align: left; padding: 4px 8px; border-bottom: 1px solid var(--border); }
  th { color: var(--muted); font-weight: 500; }
  #status { color: var(--muted); }
  #status.error { color: var(--error); }
</style>
</head>
<body>
<header>
  <h1>My App</h1>
  <span id="status"></span>
  <button id="refresh">Refresh</button>
</header>
<main>
  <table>
    <thead><tr><th>Location</th><th>Name</th><th>Format</th></tr></thead>
    <tbody id="rows"></tbody>
  </table>
</main>
<script>
  const $ = (id) => document.getElementById(id);

  // There are no alert/confirm dialogs in the sandboxed tab: report status inline.
  function status(text, isError = false) {
    $("status").textContent = text;
    $("status").className = isError ? "error" : "";
  }

  async function api(path, options) {
    const res = await fetch(path, options);
    const body = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(body.error || `${res.status} ${res.statusText}`);
    return body;
  }

  async function load() {
    status("Loading…");
    try {
      const { nodes } = await api("/api/nodes");
      $("rows").replaceChildren(
        ...nodes.map((n) => {
          const tr = document.createElement("tr");
          for (const v of [n.location, n.name, n.format]) tr.appendChild(document.createElement("td")).textContent = v;
          return tr;
        }),
      );
      status(`${nodes.length} nodes`);
    } catch (e) {
      status(e.message, true);
    }
  }

  $("refresh").addEventListener("click", load);
  load();
</script>
</body>
</html>
```
