---
type: regex
target: {source: file, path: apps/node-browser/package.json}
match: contains
---
"start"\s*:\s*"node [^"\s&|;<>$`*~']+(?: [^"&|;<>$`*~']*)?"
