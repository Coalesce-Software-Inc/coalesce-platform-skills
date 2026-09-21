---
type: regex
target: {source: file, path: nodes/TARGET-STG_REGION.yml}
match: count:3
flags: m
---
^\s*-?\s*name: R_[A-Z]+\s*$
