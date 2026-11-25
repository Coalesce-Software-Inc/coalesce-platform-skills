---
type: regex
target: {source: file, path: apps/node-browser/package.json}
match: not_contains
---
"(?:dependencies|devDependencies|peerDependencies)"\s*:\s*\{\s*"
