# S2 phase-transform header audit

## Physical information sought

The closed DOY253 qualification showed that a fixed root can expose a phase
convention which the measurement parser has not frozen.  The smallest next
question is therefore not whether the phase residual passes.  It is whether the
headers of the exact eight-root capability set describe a reversible and
unambiguous coordinate for `C1C/C2W/L1C/L2W` before any observation value is read.

The distinct, predeclared artifact is DOY251 (2026-09-08).  It is not a retry of
DOY252 or DOY253 and it cannot qualify the measurement values.  The target remains
reserved as `G14`; no navigation product is needed or allowed.

## Frozen access boundary

`phase_transform_header_audit_plan.json` fixes the date, eight station roots,
filenames, byte and line limits, fields and terminals.  Each complete `.crx.gz`
artifact is materialized in RAM and SHA-256 hashed before parsing.  A streaming
gzip reader exposes only the CRINEX preamble and RINEX header and stops at `END OF
HEADER`.  The Hatanaka body decoder is not imported.  Neither an observation row
nor a numeric measurement has a representation in this program.

Receipts precede admission.  The program attempts every predeclared root once so
that one rejected header cannot hide the topology of later roots.  It never
retries, substitutes a station/date, downloads navigation or persists payloads.

## Frozen transform semantics

The two similarly named scale mechanisms are kept separate:

- RINEX 3 `SYS / SCALE FACTOR` is a numeric storage transform.  The stored
  observable is divided by the declared factor before use; missing means one.
- RINEX 2 `WAVELENGTH FACT L1/2` defines the ambiguity-wavelength divisor for
  GPS L1/L2.  RINEX still stores carrier phase in carrier cycles.  The legacy
  record therefore does not authorize rescaling the stored phase number.
  Factor zero on required L2 is fatal; satellite overrides are retained.
- `SYS / PHASE SHIFT` is an additive cycle transform with an explicit satellite
  scope.  Both required phase observables must have a known declaration.
- Every nonblank/nonzero future LLI breaks the segment.  No half-cycle or
  opposite-factor epoch is repaired or interpolated.
- Applied GPS DCB/PCV corrections remain unqualified unless their independent
  correction products are separately frozen.  Receiver clock correction must
  remain zero or absent.

This interpretation follows the official RINEX 2.11 and 3.05 specifications.
It narrows an overstatement in the closed DOY253 report: a wavelength factor can
change the ambiguity lattice and LLI interpretation without itself multiplying
the stored carrier-cycle coordinate.  The old terminal remains immutable because
that distinction was not in its frozen ledger.

## Outcomes

`PHASE_TRANSFORM_HEADERS_QUALIFIED` means only that all eight frozen headers have
an explicit transform ledger.  It does not qualify receiver continuity, phase
values, atmosphere, navigation, residuals, an inverse solution or S3.

`PHASE_TRANSFORM_HEADERS_NOT_QUALIFIED` is an exact source/header refusal.
`HEADER_AUDIT_EXECUTION_INVALID` separates transport/software failure from a
capability rejection.

## First execution audit and repair

The frozen v1 runner materialized and hashed all eight DOY251 products, then
rejected every one before entering its RINEX header.  The cause was an exact
whitelist typo: the standard label is `CRINEX VERS   / TYPE`, while the runner
and its synthetic fixture used `CRINEX VERS / TYPE`.  This is a description
error, not eight capability failures.  The generated result is preserved, but
the authoritative terminal is `HEADER_AUDIT_EXECUTION_INVALID`; DOY251 cannot
be reused.

The bounded repair changes only that label and the synthetic fixture.  Plan v2
freezes distinct DOY254 evidence with the same roots, fields, transform rules,
limits and stopping policy.  It does not weaken a scientific parameter.

Plan v2 was itself invalid: it requested complete DOY254 daily files at
23:19:49 UTC, before the declared final 23:59:30 GPST epoch.  No artifact was
materialized and the eight HTTP 404 responses cannot reject the roots.  Its
authoritative terminal is also `HEADER_AUDIT_EXECUTION_INVALID`.

The final v3 repair adds a conservative 48-hour maturity check before network
access and freezes DOY243.  HTTP absence is now reported as
`SOURCE_PRODUCT_UNAVAILABLE`, not `CAPABILITY_REJECTED`.  V3 is the last attempt
in this bounded task regardless of outcome; there is no date search.

## Final outcome

The mature DOY243 run reached:

```text
PHASE_TRANSFORM_HEADERS_NOT_QUALIFIED
```

All eight complete compressed artifacts were materialized and SHA-256 hashed in
RAM.  Five roots—ALGO, BOGT, MKEA, PIE1 and GOLD—passed the frozen header audit.
Their required `C1C/C2W/L1C/L2W` coordinates use divisor one, zero declared
required phase shifts, no legacy wavelength-factor record and no applied GPS
DCB/PCV correction product.

DRAO, STJO and YELL failed `UNSUPPORTED_OBSERVATION_FORMAT`, which is the frozen
composite of allowed version (3.04/3.05), observation-file type and GPS/mixed
system declaration.  The v3 failure receipt did not retain the offending raw
descriptor component, so it does not authorize a more specific claim about
their RINEX version or transform.  Their transform ledgers remain unknown; they
must not be filled from another date after this outcome.

No observation body line, Hatanaka value, navigation product, target value,
residual or fit was exposed.  Result evidence is
`results/phase_transform_header_audit_2026243_v1.json`, SHA-256
`1d8a0bd32cf22106070b74ae73ec83afd1e910cc0b4ac14e51e4d70161078a5b`.
The fixed eight-root path is closed for this attempt and S3 remains blocked.
