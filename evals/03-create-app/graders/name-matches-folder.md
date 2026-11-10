---
type: regex
target: {source: file, path: apps/node-browser/package.json}
match: contains
---
"name"\s*:\s*"node-browser"
