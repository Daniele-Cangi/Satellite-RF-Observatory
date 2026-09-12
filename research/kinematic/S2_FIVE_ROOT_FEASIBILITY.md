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
