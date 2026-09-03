# GNSS all-track bounded parser-repair retry plan

## State

```text
HISTORICAL_OUTCOME_IMMUTABLE
ANTENNA_2A20_REPAIR_MERGED
BOUNDED_RETRY_FROZEN_OFFLINE
RETRY_NOT_AUTHORIZED
```

This is a normal implementation-repair continuation of the existing ALGO
all-track qualification. It creates no gate, changes no physical hypothesis
and does not authorize network access. The historical terminal remains:

```text
QUALIFICATION_DESCRIPTION_ERROR / ANTENNA_TYPE_CHANGED
```

That receipt remains true about the first execution. It is never overwritten,
renamed or reclassified.

## Information-gain test

```text
Physical question:
  Does the frozen ALGO product materialize exactly six complete, value-blind
  GPS L1C/L2W tracks on the frozen 139-epoch grid?

New information produced:
  The retry can reach record traversal and answer the still-unresolved
  structural question after correcting the RINEX antenna description parser.

Why the existing execution cannot answer it:
  It stopped at the descriptive header boundary before any observation record
  was traversed. Structure, measurement admission and orbital score are all
  NOT_EVALUATED.

Minimum experiment:
  Re-materialize the same exact artifact once, verify its already observed
  complete-file identity before decompression, apply the 2A20 parser and the
  otherwise unchanged structural contract, and write distinct retry receipts.

Stop condition:
  One retry terminal. No primary selection, measurement admission or orbital
  score follows automatically.
```

## Frozen scientific contract

The retry inherits without modification:

- station `ALGO00CAN` and DOY229 / 2026-08-17;
- product `ALGO00CAN_R_20262290000_01D_30S_MO.crx.gz` and the same BKG URL;
- compressed byte count `4,317,738`;
- compressed SHA-256
  `88aa876b787cac583345d512b2f705ec19062a5f71c38c3a4ae0da45f8095f24`;
- raw window 12:49:30--13:58:30 GPS, 139 epochs at 30 s;
- complete-track count exactly six;
- opaque first-seen membership before PRN reveal;
- core phase L1C/L2W and their LLI rules;
- descriptive, non-fatal C1C/C2W witnesses;
- no interpolation, gap bridging, PRN-conditioned selection or value reads;
- zero measurement admission, orbital scoring and primary selection.

The only semantic change is the confirmed implementation repair:

```text
ANT # / TYPE
  RINEX 3.04 Table A2: 2A20
  IGS second A20: A16 antenna model + A4 radome
```

No threshold, field role, geometry, window, track count, candidate, endpoint or
outcome meaning may change.

## Immutable predecessor and distinct receipts

The existing file `GNSS_ALL_TRACK_QUALIFICATION_OUTCOME.json` is the immutable
predecessor. The retry may write only:

- `GNSS_ALL_TRACK_QUALIFICATION_RETRY_COVERAGE.jsonl`;
- `GNSS_ALL_TRACK_QUALIFICATION_RETRY_STRUCTURE.json`;
- `GNSS_ALL_TRACK_QUALIFICATION_RETRY_REVEAL.json`;
- `GNSS_ALL_TRACK_QUALIFICATION_RETRY_OUTCOME.json`.

If any retry output already exists, execution is refused. The original outcome
must have its frozen canonical SHA-256 before and after execution.

## Lineage and artifact admission

Before network access, the executor must verify a separately frozen seal that
binds:

- the historical outcome and terminal;
- the original qualification plan and selection receipt;
- repair commit `e4bf316c3c15728ad6821dedb25d41e0a3f44866`;
- the repaired structural scanner and header-parser hashes;
- the original structural manifest hash;
- this retry plan and retry-executor hashes;
- the exact artifact filename, URL, byte count and SHA-256;
- every retry output filename.

Content-Length, ETag and Last-Modified remain descriptive. A complete artifact
whose bytes or SHA-256 differ is a materialization failure and is not decoded.

## Retry boundary

There is one parser-repair retry execution. Within its single materialization,
the existing bounded transport policy permits at most two attempts only for a
timeout or interrupted transport before a complete-file hash exists. It does
not permit an alternate product, URL, station, date or window.

After a complete-file hash exists there is zero retry. Decompression, header
description, record traversal, receipt serialization and structural outcome
are terminal for this execution.

## Outcome semantics

The retry preserves the existing four terminals:

```text
GNSS_ALL_TRACK_STRUCTURAL_QUALIFICATION_PASSED
GNSS_ALL_TRACK_STRUCTURAL_QUALIFICATION_FAILED
QUALIFICATION_ARTIFACT_MATERIALIZATION_FAILED
QUALIFICATION_DESCRIPTION_ERROR
```

Only `PASSED` or `FAILED` evaluates the structural question. Materialization or
description errors leave structure `NOT_EVALUATED`. Every terminal leaves
measurement admission, orbital score and primary selection `NOT_EVALUATED`.

Even `PASSED` authorizes only review of a later, distinct primary plan. It does
not select or access a primary.

## Current stop

Stop offline after freezing and testing the executor and its seal. A later
materialization requires separate explicit authority for this exact retry.
