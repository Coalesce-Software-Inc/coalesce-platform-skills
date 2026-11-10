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

async function handle(req, res) {
  const { pathname } = new URL(req.url, "http://localhost");
  const json = (status, data) => {
    res.writeHead(status, { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" });
    res.end(JSON.stringify(data));
  };

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
