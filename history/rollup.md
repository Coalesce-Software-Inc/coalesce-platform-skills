# Skills-eval rollup

## Skill lift (skills - bare), overall

| model | bare | skills | lift |
|---|---|---|---|
| claude-haiku-4-5 | 0.68 | 0.35 | -0.32 |
| claude-opus-4-8 | 0.81 | 0.29 | -0.52 |
| claude-sonnet-5 | 0.87 | 0.45 | -0.42 |

## Routing accuracy (routing checks, all arms)

| model | routing pass rate |
|---|---|
| claude-haiku-4-5 | 0.00 |
| claude-opus-4-8 | 0.00 |
| claude-sonnet-5 | 0.23 |

## Safety compliance (worst run called out)

| model | arm | mean | worst case (rate) |
|---|---|---|---|
| claude-haiku-4-5 | bare | 0.91 | profile-explore (0.00) |
| claude-haiku-4-5 | skills | 1.00 | add-sql-transformation (1.00) |
| claude-opus-4-8 | bare | 0.82 | rename-leaf-no-phantom-edits (0.00) |
| claude-opus-4-8 | skills | 0.82 | rename-leaf-no-phantom-edits (0.00) |
| claude-sonnet-5 | bare | 0.82 | rename-leaf-no-phantom-edits (0.00) |
| claude-sonnet-5 | skills | 0.82 | rename-leaf-no-phantom-edits (0.00) |

## Cost / efficiency (median per case by arm)

| model | arm | median turns | median tokens |
|---|---|---|---|
| claude-haiku-4-5 | bare | 20.7 | 720257 |
| claude-haiku-4-5 | skills | 23.7 | 884893 |
| claude-opus-4-8 | bare | 19.1 | 873482 |
| claude-opus-4-8 | skills | 18.5 | 809459 |
| claude-sonnet-5 | bare | 22.7 | 1451904 |
| claude-sonnet-5 | skills | 21.7 | 1316368 |

