---
type: regex
target: {source: file, path: apps/node-browser/server.js}
match: not_contains
---
(?:resolve|join)\(\s*__dirname\s*,\s*["']\.\.
