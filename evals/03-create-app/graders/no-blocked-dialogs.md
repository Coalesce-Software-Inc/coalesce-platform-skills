---
type: regex
target: {source: file, path: apps/node-browser/index.html}
match: not_contains
---
(?:^|[^.\w])(?:window\.)?(?:alert|confirm|prompt)\s*\(
