# S2 five-root local-feasibility audit

This bounded offline audit asks one question before any new target or observation
access: can the five roots whose phase-transform headers were qualified support
the local information geometry of the current interval inverse model?

It does **not** select a target, date, orbit or primary. The geometry family is
an explicitly synthetic set of broad geocentric shells, deterministic directions
and four non-orbital motion templates. Terrestrial coordinates are copied into
the frozen plan from the already retained G14 structural artifact; no observation
value is read.

The audit keeps four clauses separate:

1. local fit identifiability over every jointly visible synthetic case;
2. a conditional local margin under the frozen Gaussian design assumptions and
   a separate persistent per-root code/rate affine box;
3. availability of an independent held-out root;
4. availability of a total physical error envelope.

A local pass cannot satisfy clauses 3 or 4. With exactly five fit roots, the
current 36-parameter model has no sixth root left for an excluded-receiver test.
Receiver errors, atmosphere, unflagged phase discontinuities, kinematic
truncation, nonlinear coverage and global alternative branches remain outside
the conditional local calculation.

The plan is `five_root_feasibility_plan.json`. The runner refuses target/date or
target-radius fields, writes strict JSON and records every generated and rejected
synthetic case. Its terminal is intentionally
`FIVE_ROOT_PROSPECTIVE_VERTICAL_INCOMPLETE`: this is a design audit, not S3.

## Frozen result

The source was frozen at commit `09a7273a648c9a0eb6398da7c7924f08e1652f41`
before execution. Of 2,304 generated cases, 181 met the 5-degree joint-visibility
condition at every root and endpoint. Every admitted case had all 36 local
parameters identifiable under the frozen scaled-rank threshold. This establishes
local rank, not global uniqueness.

The 10 km conditional local envelope was not uniform. At +60 seconds, code plus
interval phase gave 0.501 km best, 17.164 km median and 83.332 km worst. Sixty-five
of 181 cases were within 10 km. The shell breakdown exposes far-field geometric
amplification rather than a parser or optimizer failure:

| Synthetic geocentric shell | Joint-visible cases | <=10 km at +60 s | Median envelope | Range |
|---:|---:|---:|---:|---:|
| 12,000 km | 4 | 4 | 0.587 km | 0.501–0.805 km |
| 20,000 km | 28 | 28 | 2.816 km | 1.499–5.688 km |
| 30,000 km | 44 | 33 | 8.083 km | 4.195–17.747 km |
| 45,000 km | 50 | 0 | 19.922 km | 10.893–37.097 km |
| 60,000 km | 55 | 0 | 37.094 km | 20.785–83.332 km |

No 8,000 km case was jointly visible to all five roots. Phase information never
worsened the local Gaussian radius, but the deliberately separate interval-rate
bias box introduces sensitivities absent from code-only. The total conditional
envelope improved in 179 of 181 cases; its median remained above 10 km because
persistent per-root affine terms dominate much of the high-shell family.

The frozen clauses therefore read:

- `LOCAL_FIT_IDENTIFIABILITY = SATISFIED`;
- `CONDITIONAL_LOCAL_MARGIN = NOT_SATISFIED`;
- `INDEPENDENT_HELDOUT_ROOT = UNSATISFIED`;
- `TOTAL_PHYSICAL_ERROR_ENVELOPE = UNRESOLVED`.

The exact result is
[`results/s2_five_root_feasibility_v1.json`](results/s2_five_root_feasibility_v1.json),
SHA-256 `58df177228f5fb5afdac91c92eed7925a932b3b59e37fca214126a9449503c7b`.
The plan SHA-256 is
`8c988f24ed5b3f19906f1a196863dddf210912deed8fc5fbab44938dd2074132`.

The smallest remaining topology is the same five fit roots plus one distinct,
predeclared, independently qualified code-coordinate root reserved only for
held-out prediction. That does not by itself close the receiver, propagation,
continuity, truncation or nonlinear/global error envelope. No root, target or
date is selected by this audit.
