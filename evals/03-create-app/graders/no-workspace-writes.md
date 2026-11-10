---
type: regex
target: trace
match: not_contains
---
"name":"(?:Write|Edit|MultiEdit|NotebookEdit)","input":\{"(?:file_path|notebook_path)":"[^"]*/(?:nodes/|nodeTypes/|environments/|data\.yml"|locations\.yml"|workspace\.yml")
