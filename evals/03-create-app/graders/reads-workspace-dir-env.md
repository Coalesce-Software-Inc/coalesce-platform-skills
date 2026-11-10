---
type: regex
target: {source: file, path: apps/node-browser/server.js}
match: contains
flags: m
---
process\.env(?:\.WORKSPACE_DIR\b|\[["']WORKSPACE_DIR["']\])|\{[^}\n]*\bWORKSPACE_DIR\b[^}\n]*\}\s*=\s*process\.env
