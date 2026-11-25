---
type: regex
target: trace
match: contains
---
"command":"(?=(?:[^"\\]|\\.)*(?<![A-Z_])PORT=\d+)(?=(?:[^"\\]|\\.)*(?<![A-Z_])WORKSPACE_DIR=)(?=(?:[^"\\]|\\.)*(?:\\n|[\s;&|(])node (?:[^\s"\\]*/)?server\.js\b)
