# Post-DRAO DOY232 qualification change of abstraction

**DRAO_SINGLE_PRIMARY_ADMISSION_PATH_SELECTED**

This is an offline scientific decision. It does not reopen DOY232, select a
DOY233 observation locator, freeze a primary or authorize observation access.

## BLOCK

Nothing physical failed. The consumed DOY232 run stopped at the bridge

```text
station identity contract
-> header predicate
-> receipt representation
```

before any observation field, measurement clause or orbital hypothesis was
evaluated. The historical
`QUALIFICATION_TOPOLOGY_REJECTED / MARKER_NAME_MISMATCH` record remains
immutable, while the audited physical state remains `NOT_EVALUATED`.

## INFORMATION VALUE

The run produced no information about the orbital hypothesis and no evidence
that the DRAO measurement path is physically unsuitable. It did show that an
exact comparison against `MARKER NAME == DRAO`, performed before retaining
`MARKER NAME` and `MARKER NUMBER`, cannot attribute station identity.

## CURRENT ABSTRACTION

A distinct prior-day qualification is useful insurance against consuming a
primary on a format or capability failure, but it is not part of the physical
causal path. What is necessary is narrower:

```text
every frozen measurement clause passes
-> and only then the held-out orbital comparison runs
```

Those clauses can be evaluated inside the still-unopened primary. If any
clause fails, the orbital comparison remains `NOT_EVALUATED`; if they all
pass, an orbital-negative outcome is not confused with a measurement failure.
This preserves negative interpretability without another qualification
artifact.

## ALTERNATIVES

| Route | Decision | Reason |
|---|---|---|
| repair and reopen DOY232 | forbidden | DOY232 is consumed and the missing receipt cannot be recreated |
| open DOY233 without admission | rejected | a negative would confound measurement and orbital failure |
| select another qualification day before DOY233 | not selected | it adds another non-orbital artifact when the same frozen clauses can guard the primary |
| integrate admission and scoring in one DOY233 execution | selected for offline plan review | it preserves the strongest unused geometry and reaches the physical question with one artifact |
| abandon DRAO | conditional fallback | required if sufficient clauses cannot be frozen before primary access |

## BEST PHYSICAL PATH

Keep the unselected DOY233 geometry:

- DRAO00CAN / DOMES `40105M002`;
- GPS DOY233, `01:14:30--02:23:30`;
- 139 epochs at 30 seconds, prefix 79 and held-out 60;
- frozen orbital family `G07/G08/G09/G21/G27/G30`;
- exactly seven opaque observed tracks and one symmetric clutter exclusion;
- retarded-geometry controlling separation `49,090.485194 m`;
- conditional combined envelope `3,387.960685 m`;
- unchanged guard `7,339.701235 m`;
- remaining model-side margin `3,951.740549 m`.

No new geometry search is needed. The next proof should compose one one-shot
primary in this strict order:

```text
complete artifact hash
-> identity/header receipt
-> full-window structural admission
-> model-blind continuity and same-path witnesses
-> opaque one-clutter score receipt
-> post-hash code-identity reveal
-> one terminal outcome
```

The scorer cannot run unless every admission clause passes. There is no
held-out refit, no post-hash retry, no replacement date, artifact or window,
and no persistence of observation values.

## Identity correction for future work

The future identity contract must bind the frozen artifact site ID
`DRAO00CAN`, DOMES `40105M002` and the independently frozen receiver/antenna
identity. `MARKER NAME` is a descriptive consistency field, not a standalone
station key. Before any decision, the receipt must retain the observed marker
name, marker number, receiver, antenna and first/last observation times.

Any contradiction or incomplete identity evidence terminates a typed
`NOT_EVALUATED` outcome with sufficient attribution. It must not silently
become a physical measurement-path rejection.

## Measurement boundary for future work

Admission must require exactly seven complete opaque tracks on the full grid,
with L1C/L2W phase, zero LLI, C1C/C2W at every admitted epoch, no interpolation
and no gap bridging. Because the one-clutter scorer does not know which track
will be excluded, the complete same-path witness must cover every track that
can enter an assignment. Thresholds and transforms remain those already
frozen; a future plan may narrow them but may not learn replacements from the
primary.

## ACTION

Do not create another qualification gate. The next maximum action is one
offline integrated DOY233 primary plan and sealed executor. It may be reviewed
before any locator is selected. If its identity, admission, witness and
one-clutter boundaries cannot be frozen without inspecting DOY233, abandon the
DRAO route.

Stop before every DOY233 locator request, header, payload byte or observation
value.
