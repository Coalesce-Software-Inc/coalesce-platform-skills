---
type: regex
target: {source: file, path: apps/node-browser/server.js}
match: contains
---
listen\([^)]*["'](?:127\.0\.0\.1|::1|localhost)["']|for\s*\(\s*const\s+\w+\s+of\s+\[\s*["'](?:127\.0\.0\.1|::1|localhost)["']
