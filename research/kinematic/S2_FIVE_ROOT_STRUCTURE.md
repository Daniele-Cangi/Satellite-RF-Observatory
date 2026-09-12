# S2 five-root target-free structural qualification

## Physical question

Can the exact topology selected offline—ALGO, BOGT, MKEA and PIE1 in the fit,
with GOLD reserved for code-only held-out prediction—materialize a simultaneous
11-endpoint measurement structure on a distinct real day?

## New information produced

This run can establish only source materialization, header/receiver/transform
continuity, complete-day epoch topology, code/phase field presence, phase LLI
continuity and the existence of at least one structurally capable common
window. It cannot establish measurement accuracy, a physical error envelope,
a target identity, an orbit or a position.

## Frozen execution

DOY242 (2026-08-30) is the nearest earlier complete day to the five successful
DOY243 header ledgers. It is frozen before any access to these five artifacts;
there is no alternate date, station, field or retry. DRAO's separately closed
DOY242 artifact is not part of this topology and provides no admission evidence.

Every complete compressed artifact is materialized and SHA-256 hashed before
Hatanaka decoding. The scanner traverses the complete decoded day but interprets
only headers, epoch tags, satellite-row identity, required-field presence and
L1C/L2W LLI characters. It never converts an observation substring to a number.
Decoded and compressed payloads remain ephemeral.

An 11-epoch interval is structurally capable only if all four fit roots retain
at least five stable C1C/C2W/L1C/L2W rows with blank-or-zero phase LLI, GOLD
retains at least five stable C1C/C2W rows, and at least one satellite identity is
common to every root. Removing that unselected common identity must leave at
least four structural reference identities at each root. Candidate identities
are counted but neither selected nor persisted.

The run stops at one of:

- `FIVE_ROOT_STRUCTURE_QUALIFIED`
- `FIVE_ROOT_STRUCTURE_NOT_QUALIFIED`
- `FIVE_ROOT_STRUCTURE_EXECUTION_INVALID`

A pass authorizes only a separately frozen, distinct-artifact reference-only
numerical qualification. It does not authorize a primary target or S3.

## Frozen outcome

The one execution terminated `FIVE_ROOT_STRUCTURE_NOT_QUALIFIED`. All five
artifacts were available, fully materialized and hash-bound before decoding.
ALGO, MKEA and PIE1 passed their header/transform clauses and complete-day
structural scans: each contained 2,880 consecutive 30-second epochs with no
non-nominal gap, and every GPS identity had at least one 11-endpoint usable
segment. No observation substring was converted to a number.

BOGT and GOLD stopped at `PHASE_SHIFT_DIFFERS_FROM_PLAN:L1C`, before either
body entered the structural scanner. The frozen contract required zero default
phase shift and no satellite overrides. The receipt does not distinguish which
part of that composite check differed, so its exact transform remains unknown.

This failure needs clause-level attribution:

- BOGT is a fit root, but a static declared phase offset (default or
  satellite-scoped) can be represented explicitly and cancels from a
  same-satellite endpoint difference when its scope is unchanged. Requiring it
  to be exactly zero was stricter than the physical interval observable. The
  result therefore does not demonstrate that BOGT lacks usable phase structure.
- GOLD is code-only in this topology. Applying any phase-shift clause to GOLD
  was outside the causal path of C1C/C2W and cannot establish failure of its
  required held-out coordinate.

The frozen outcome remains valid under its frozen contract and DOY242 must not
be retried or rescored. Scientifically, however, it is not evidence that the
five-root measurement path is structurally insufficient. The cross-root window
and all numerical/physical clauses remain `NOT_EVALUATED`, not rejected.

The exact result is
[`results/s2_five_root_structure_2026242_v1.json`](results/s2_five_root_structure_2026242_v1.json),
SHA-256 `af13370e6d2537c6497e70ef842662f768f4e2de37f29d8643fda6b1789893d0`.
The separate failure-attribution receipt binds this result and prevents the
descriptive contract error from becoming a physical refusal.

The smallest next step is offline only: freeze role-specific transform
semantics in which fit-root phase offsets are retained as reversible static
metadata and held-out GOLD is evaluated only on code transforms. A later
qualification must use a distinct unopened artifact; it cannot reopen DOY242.
