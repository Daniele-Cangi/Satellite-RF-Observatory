# KIRU–MAT1 independent GNSS qualification

## Outcome

`GNSS_QUALIFICATION_ADMITTED`

This is a structure-only qualification of the two authorized DOY 214
artifacts. It is not a prospective-plan freeze, a primary observation, a
measurement-valid result or an orbital claim. The distinct DOY 215 KIRU/MAT1
primary remains completely unopened.

The frozen machine receipt is
`GNSS_INDEPENDENT_QUALIFICATION_RECEIPT.json`, SHA-256
`5e2d319ba633dce788bfa0a8b8961fa228a4b6ffd0ed47787b92c59520b37f0d`.
Its parser manifest SHA-256 is
`bcd504f9e3a0e2b70bf62ee566fdcdc6154e43a7063d6bbe8921ad2ba292210c`.

## Exact artifacts opened

| Station | Compressed bytes | Compressed SHA-256 | Ephemeral decompressed bytes | Ephemeral decompressed SHA-256 |
|---|---:|---|---:|---|
| KIRU00SWE | 5,126,492 | `06db32b758483448fa4420758a0783a1ede144e6812e794f2b5311aeef0547c0` | 42,779,722 | `b19850b60fb610ac910399a3845f78c0d875905d4418b094a2f346433a5d07e4` |
| MAT100ITA | 4,237,763 | `3e1a55a4be23ec5a6b7c62589366f444cd0d3777a9a7ad37daad4757e28dfae2` | 32,934,298 | `6548e17846b027fe524b23024e937c8364116f3abc0b3c43cfd23af169cca790` |

Each complete compressed artifact was checked by filename, byte count and
SHA-256 before decompression. The decompressed artifact was hashed in RAM,
parsed and overwritten; zero decompressed bytes were persisted.

## Header and time evidence

KIRU declares RINEX 4.01 / CRINEX 3.0, marker `KIRU00SWE`, a SEPT POLARX5TR
5.6.0 receiver and 30-second GPS-system epochs. `RCV CLOCK OFFS APPL` is absent,
so the parser retains the RINEX-standard default `0` with that provenance.
MAT1 declares RINEX 3.04 / CRINEX 3.0, marker `MAT100ITA`, a LEICA GR30
4.83/7.900 receiver, 30-second GPS-system epochs and an explicit
`RCV CLOCK OFFS APPL = 0` record.

Both files contain exactly 2,880 monotonically increasing flag-0 epoch records
from `2026-08-02T00:00:00 GPS` through `23:59:30 GPS`; all 2,879 transitions
are exactly 30 seconds. Qualification does not reinterpret these labels as UTC
and does not estimate station clock error. The existing direct
`t ± 15 s` physical envelope therefore remains unchanged.

## Frozen field topology

The predeclared preference order selected the first common dual-frequency
family before occupancy was scanned:

```text
C1C / L1C / S1C
C2W / L2W / S2W
```

The parser treats each RINEX observation as a 14-character value coordinate
plus optional LLI/SSI characters, but tests only whether value characters are
blank. It does not convert the text to a number and does not inspect LLI, SSI
or SNR magnitude. The exact Hatanaka 2.8.1 output uses long satellite records,
with no continuation lines in these products, and may omit the final two blank
LLI/SSI characters at end of line. It may also stop before declared trailing
fields when all remaining fields are absent. Those cases are now recorded as
structural absence, not mislabeled as numeric truncation.

The initial implementation correctly stopped as `QUALIFICATION_ERROR` on the
14-character end-of-line form. A bounded line-length audit showed the same
`14 mod 16` form throughout both decoder outputs. Correcting that descriptive
boundary changed no target, signal family, continuity requirement, threshold
or physical hypothesis. A software description error was never promoted to
`CAPABILITY_REJECTED`.

## Continuity admission

For the frozen G20/G22 family:

- KIRU has 493 structurally complete joint-target epochs;
- MAT1 has 676 structurally complete joint-target epochs;
- their intersection is one uninterrupted run of 493 records;
- the run is `2026-08-02T15:41:00 GPS` through `19:47:00 GPS`;
- duration between first and last record is 14,760 seconds;
- the prospective primary coordinate requires 380 raw records, so the
  qualification surplus is 113 records.

This proves only that the exact station/decoder path can materialize the
predeclared two-satellite, two-frequency field topology for at least the future
window length. It does not prove that G20/G22 or those fields are present in
the sealed primary.

## Value-blind boundary

The receipt records:

- numeric observation values decoded: `0`;
- observation value text retained: `0`;
- LLI values decoded: `0`;
- SSI values decoded: `0`;
- SNR magnitudes decoded: `0`;
- decompressed RINEX persisted bytes: `0`;
- primary headers opened: `0`;
- primary payload bytes opened: `0`.

Occupancy is a Boolean structural property only. No carrier phase, code,
Doppler, SNR magnitude, feature, residual or orbital score was produced.

## What remains unknown

The qualification does not establish primary-day occupancy, cycle-slip state,
phase continuity, multipath level, SNR adequacy, numerical measurement
validity or preference among G20, the affine null and G14. It also does not
turn receiver epoch labels into an independently calibrated absolute-time
witness.

The next exact blocker is therefore:

`FREEZE_ONE_PRIMARY_PLAN_AND_OBTAIN_SEPARATE_DOY_215_ACCESS_AUTHORITY`

Before any primary access, one prospective plan must bind the already selected
KIRU/MAT1 geometry, G20/G22 coordinate, G14 and affine nulls, the now frozen
signal family and parser, prefix/suffix split, value-level admission rules,
outcomes and zero-retry policy. No DOY 215 access is authorized by this result.
