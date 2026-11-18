---
type: regex
target: {source: file, path: data.yml}
match: contains
flags: m
---
^platformKind: tdbc-clickhouse\s*$
