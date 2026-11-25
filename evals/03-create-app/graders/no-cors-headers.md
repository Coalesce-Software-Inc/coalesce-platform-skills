---
type: regex
target: {source: file, path: apps/node-browser/server.js}
match: not_contains
flags: i
---
["']access-control-allow-origin["']\s*[:,]
