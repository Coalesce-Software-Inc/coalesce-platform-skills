---
type: regex
target: {source: file, path: apps/node-browser/server.js}
match: contains
---
headers\.host\b|headers\[["']host["']\]
