# Independent GNSS structural qualification

Date: 2026-08-23

Branch: `experiment/gnss-independent-qualification`

Frozen pre-access commit: `86a37a0c94f9f9c29df4d50e41a05d37c6a5bbe6`

## Terminal result

```text
GNSS_INDEPENDENT_QUALIFICATION_FAILED
```

This is a structural qualification result. It is not an orbital measurement,
does not select a primary, and does not alter or rescore the historical
GOLD/NLIB result:

```text
MEASUREMENT_INVALID
TRUNCATED_REQUIRED_OBSERVATION_RECORD
```

## Frozen qualification artifacts

The independent date was 2026-08-02 (DOY 214), one day before the closed
historical experiment, with the same GOLD/NLIB hardware roots and unchanged
site-log receiver/antenna configurations.

| Station | Exact product | Bytes | SHA-256 |
|---|---|---:|---|
| GOLD00USA | `GOLD00USA_R_20262140000_01D_30S_MO.crx.gz` | 2,175,246 | `0da86ed0b7fd2b4436d8e8fa5a4b2abeeadd8590af83544be9e98d1911517fe6` |
| NLIB00USA | `NLIB00USA_R_20262140000_01D_30S_MO.crx.gz` | 2,485,603 | `3a0313973e040adf619a0fb6e1e12415aa8c790d65606bffc1fe84e1545c10fc` |

Both headers declared a 30 s interval, `TIME OF FIRST OBS`, `TIME OF LAST
OBS`, and full-day coverage enclosing the frozen window. The qualification
window was fixed at 2026-08-02 10:05:30--13:18:00 GPS: 386 raw epochs, 384
feature epochs, a 77-epoch calibration prefix and a 307-epoch held-out suffix.

## Structural coverage

The scanner emitted exactly 9,264 atomic rows: two stations, 386 epochs, two
satellites and six relevant observables. It did not persist observation
values.

| State | Count |
|---|---:|
| `PRESENT` | 9,102 |
| `BLANK` | 162 |
| `TRAILING_FIELD_OMITTED` | 0 |
| `CONTINUATION_SUPPORTED` | 0 |
| `CONTINUATION_UNSUPPORTED` | 0 |
| `RECORD_INVALID` | 0 |

All 162 blanks are the same structural cut: NLIB has no G21 record for the
first 27 epochs, from 10:05:30 through 10:18:30 GPS, across all six fields.
At the first G21 record, 10:19:00 GPS, both core phase fields are present but
carry nonzero LLI. The first admissible joint epoch is therefore 10:19:30.

The maximal joint segment is fixed and was not substituted or extended:

```text
2026-08-02T10:19:30 GPS -> 2026-08-02T13:18:00 GPS
358 epochs; 10,710 s elapsed duration
```

## Clause result

- Core `L1C`/`L2W`: incomplete for NLIB-G21; full-window admission fails.
- LLI and geometry-free continuity: NLIB-G21 cannot be evaluated over the
  complete frozen window, so the continuity clause is unsatisfied.
- Same-path `C1C`/`C2W`: NLIB-G21 has 359/386 present epochs (93.005%), below
  the frozen 95% rule, and the frozen partition-boundary witness is absent.
- Optional `S1C`/`S2W`: descriptive only and never used to cause failure.
- Parser topology: no unsupported continuation, truncated trailing field or
  invalid record was found.

No interpolation, gap bridging, alternative segment selection, new window or
post-outcome threshold change was applied.

## Authorized conclusion

This independent pair does not prove the full four-link `L1C`/`L2W` signal
family required by the frozen qualification contract. The failure is caused
by actual G21 visibility/continuity at NLIB in the predeclared window, not by
the old truncation error and not by a descriptive field. Consequently no new
primary may be selected or accessed from this result.

The generated coverage, summary and outcome receipts retain hashes and
structural metadata only. Compressed RINEX, decoded RINEX, phase/code values
and orbital scores persisted: zero.
