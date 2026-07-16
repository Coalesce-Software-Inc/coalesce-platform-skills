# Skills-eval rollup

## Skill lift (skills - bare), overall

| model | bare | skills | lift |
|---|---|---|---|
| claude-haiku-4-5 | 0.60 | 0.33 | -0.27 |
| claude-opus-4-8 | 0.80 | 0.27 | -0.53 |
| claude-sonnet-5 | 0.87 | 0.47 | -0.40 |

## Routing accuracy (routing checks, all arms)

| model | routing pass rate |
|---|---|
| claude-haiku-4-5 | 0.00 |
| claude-opus-4-8 | 0.00 |
| claude-sonnet-5 | 0.27 |

## Safety compliance (worst run called out)

| model | arm | mean | worst case (rate) |
|---|---|---|---|
| claude-haiku-4-5 | bare | 0.80 | profile-explore (0.00) |
| claude-haiku-4-5 | skills | 1.00 | edw-engineering-activity (1.00) |
| claude-opus-4-8 | bare | 0.80 | rename-leaf-no-phantom-edits (0.00) |
| claude-opus-4-8 | skills | 0.80 | rename-leaf-no-phantom-edits (0.00) |
| claude-sonnet-5 | bare | 0.80 | rename-leaf-no-phantom-edits (0.00) |
| claude-sonnet-5 | skills | 0.80 | rename-leaf-no-phantom-edits (0.00) |

## Cost / efficiency (median per case by arm)

| model | arm | median turns | median tokens |
|---|---|---|---|
| claude-haiku-4-5 | bare | 21.4 | 738709 |
| claude-haiku-4-5 | skills | 24.2 | 941272 |
| claude-opus-4-8 | bare | 21.5 | 995847 |
| claude-opus-4-8 | skills | 16.5 | 645399 |
| claude-sonnet-5 | bare | 23.4 | 1479304 |
| claude-sonnet-5 | skills | 19.9 | 1241459 |

