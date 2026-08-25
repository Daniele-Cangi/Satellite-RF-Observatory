# G22/G30 DOY 216 value-blind structural scan plan

Status: `FROZEN_BEFORE_NETWORK_ACCESS`.

This is the executable boundary of the reviewed phase structural contract,
not a new gate. It can produce new physical-path information only by deciding
whether the predeclared DOY 216 GOLD/NLIB topology preserves the four-link
phase coordinate required by the selected G22/G30 geometry.

## Exact scope

Only these predeclared locators may be contacted:

```text
GOLD00USA_R_20262160000_01D_30S_MO.crx.gz
NLIB00USA_R_20262160000_01D_30S_MO.crx.gz
```

The raw GPS window is fixed at `2026-08-04 04:47:00--07:59:30`, containing
386 epochs at 30 seconds. The satellites are exactly G22 and G30. DOY 220 is
sealed and is not represented in the live call graph.

Each complete compressed response is held in RAM, byte-counted and SHA-256
hashed before decompression. The Hatanaka/RINEX buffer remains ephemeral and
is overwritten after the scan. No compressed or decoded observation artifact
is written to disk.

The scanner may represent only field occupancy, LLI, epoch/record framing,
header metadata and segment topology. It cannot convert a phase, code, SNR or
other observation scalar. Every relevant row is emitted even after a missing
field; no first-failure stop is allowed. Geometry-free phase health remains
`NOT_EVALUATED` because it requires phase scalars.

There are at most two transport attempts per locator: one initial attempt and
one retry, only before a complete artifact hash exists. After hashing there is
no retry, substitution, window change or field substitution.

A materialization failure is not a structural rejection. A successful scan
can reach only `GNSS_PHASE_STRUCTURE_READY_FOR_HEALTH_REVIEW`; it cannot
authorize phase health, primary access or orbital scoring.

Persisted output is limited to strict JSON structural coverage, summary,
outcome and a Markdown report. Observation values and artifacts persist: zero.
