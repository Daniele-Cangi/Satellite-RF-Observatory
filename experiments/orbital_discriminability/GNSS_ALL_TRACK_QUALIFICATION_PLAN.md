# GNSS all-track structural qualification plan

## State

```text
QUALIFICATION_ARTIFACT_SELECTED
PAYLOAD_UNOPENED
PRIMARY_UNSELECTED
```

This is a bounded continuation of the merged all-track geometry screen.  It
creates no gate.  It freezes one qualification artifact and the maximum
structural scan that may later be executed under separate authorization.  It
does not authorize product download, decompression or observation access.

## Physical question

Can the ALGO receiver product materialize the exact six-track, value-blind
measurement topology required by the orbit-only result?

## Information gain

A positive qualification would establish that a real receiver product can
deliver all and only six complete GPS dual-frequency phase tracks on the
frozen grid without target/reference or PRN-conditioned selection.  A
negative result would close this fixed-six measurement path before any
primary is selected.

## Exact qualification artifact

| Field | Frozen value |
|---|---|
| role | structural qualification only |
| station | ALGO00CAN / DOMES 40104M002 |
| GPS day | DOY229 / 2026-08-17 |
| product | `ALGO00CAN_R_20262290000_01D_30S_MO.crx.gz` |
| format | daily 30 s mixed-observation compact RINEX, gzip transport |
| authority | BKG GNSS Data Center, IGS observation archive |
| URL | `https://igs.bkg.bund.de/root_ftp/IGS/obs/2026/229/ALGO00CAN_R_20262290000_01D_30S_MO.crx.gz` |
| HEAD result | HTTP 200, 4,317,738-byte content-length hint |
| server last-modified | 2026-08-20 01:45:45 UTC |
| server ETag | `"41e22a-65970adb01b5e"` |

Content-Length, Last-Modified and ETag are descriptive server metadata, not
artifact identity.  A later authorized materialization must verify the exact
filename, compute the complete-file byte count and SHA-256 before any
decompression, and refuse if the byte count differs from the frozen hint.

## Observer and geometry binding

- observer coordinates: latitude 45.955800 deg, longitude -78.071368 deg,
  ellipsoidal height 200.8294485278988 m;
- receiver: SEPT POLARX5, firmware 5.3.2;
- antenna/radome: AOAD/M_T / NONE;
- clock: INTERNAL;
- equipment epoch: 2026-03-25;
- frozen raw window: 2026-08-17 12:49:30--13:58:30 GPS;
- frozen held-out boundary for any later experiment: 13:29:00 GPS;
- orbit-derived codebook, unavailable to the structural selector:
  G05/G15/G18/G20/G21/G29.

The qualification artifact is chosen because it is the earliest member of
the repeated ALGO geometry and is distinct from the highest-ranked DOY230
cell.  This plan does not assign DOY230 or DOY231 a primary, reserve or any
other measurement role.

## Value-blind structural input rule

The later scanner must traverse the complete intended window and consider
every GPS record.  System-level GPS filtering is frozen; PRN filtering is
forbidden.  Tracks are assigned deterministic opaque identifiers by
first-seen order before any retained structural result is emitted.

For every opaque track and epoch retain only:

- epoch time and event flag;
- record presence and continuation state;
- L1C and L2W field presence/blank state;
- LLI for L1C and L2W;
- C1C and C2W presence/blank state;
- deterministic segment-break reason;
- header-declared interval and first/last-observation coverage;
- station, receiver, antenna and observable-schema descriptions.

The scanner must never represent or persist:

- carrier phase, pseudorange, Doppler or signal-strength magnitudes;
- `D*` observations;
- `S*` observations;
- residuals, SNR, orbit predictions or codebook identities;
- decoded observation arrays or signal-derived diagnostics.

The 2025 NRCan notice about incorrect RINEX 3.03 Doppler polarity is therefore
outside the admitted coordinate rather than silently assumed corrected.

## Frozen field roles

```text
CORE PHASE
  L1C
  L2W

CYCLE-SLIP / CONTINUITY
  LLI on L1C and L2W
  exact 30 s epoch continuity

SAME-PATH CODE WITNESS, DESCRIPTIVE IN QUALIFICATION
  C1C
  C2W

OPTIONAL / NOT READ
  all D* Doppler fields
  all S* signal-strength fields
```

C1C/C2W absence is reported but is not fatal at every qualification epoch.
It cannot become a primary witness later without a separate predeclared
quantitative rule.  S1C/S2W and all other signal-strength fields are neither
core nor qualification diagnostics.

## Segment and count policy

- no interpolation;
- no gap bridging;
- exact 30 s grid on all 139 epochs;
- missing/blank L1C or L2W breaks the affected track;
- nonzero LLI on either core field breaks the affected track;
- unsupported continuation or invalid record breaks the affected track;
- a track is complete only if one uninterrupted core segment covers all 139
  frozen epochs;
- every complete GPS track enters the count;
- exactly six complete tracks are required;
- fewer or more than six complete tracks fails qualification;
- no incomplete track may be promoted and no complete track may be removed.

The structural receipt is hashed before the scanner may reveal the receiver
PRN labels.  The reveal is a non-independent witness.  It may report
concordance or discordance with the orbit-derived six-code set, but it cannot
alter membership or rescue a failed count.

## Header admission

Before record traversal, require:

- exact station/marker identity;
- RINEX observation content and GPS system availability;
- 30 s declared interval;
- TIME OF FIRST OBS no later than the frozen start;
- TIME OF LAST OBS no earlier than the frozen stop;
- L1C, L2W, C1C and C2W present in the GPS observable schema;
- receiver and antenna descriptions compatible with the frozen station
  history;
- no unrecognized structural header state that changes field indexing or
  event-time semantics.

A descriptive mismatch is `QUALIFICATION_DESCRIPTION_ERROR`, not evidence
that the physical six-track topology failed.

## Outcome semantics

Exactly one later terminal is permitted:

```text
GNSS_ALL_TRACK_STRUCTURAL_QUALIFICATION_PASSED
GNSS_ALL_TRACK_STRUCTURAL_QUALIFICATION_FAILED
QUALIFICATION_ARTIFACT_MATERIALIZATION_FAILED
QUALIFICATION_DESCRIPTION_ERROR
```

`PASSED` requires all header clauses, complete traversal, exactly six opaque
complete tracks and a valid structural receipt.  It authorizes only a later
review of whether to freeze one distinct primary.  It does not authorize
measurement scoring.

`FAILED` means the artifact was readable and validly described but the
predeclared structural topology did not exist.  The path closes without
changing the six-track rule.

Materialization and description failures do not become physical failures and
cannot modify the geometry outcome.

## Stop boundary

Stop now with zero artifact bytes accessed.  No primary or reserve is selected,
no orbital prediction is compiled for measurement scoring and no detector is
built.  A later execution requires explicit authorization for this exact
qualification artifact.
