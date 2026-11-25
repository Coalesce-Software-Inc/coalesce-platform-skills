---
type: regex
target: {source: file, path: apps/node-browser/server.js}
match: contains
flags: m
---
process\.env(?:\.PORT\b|\[["']PORT["']\])|\{[^}\n]*\bPORT\b[^}\n]*\}\s*=\s*process\.env
