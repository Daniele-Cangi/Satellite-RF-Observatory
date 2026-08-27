# PIE observer capability metadata characterization

## Status

```text
PIE_METADATA_PATH_AVAILABLE
PIE_SIGNAL_FIELDS_NOT_YET_QUALIFIED
PRIMARY_CANDIDATE_UNOPENED
```

This is a bounded descriptive check of the single observer selected by the
real-geometry screen. It is not a capability admission, qualification result,
prospective plan or orbital measurement.

## Physical purpose

The observer-transfer geometry selected PIE100USA on DOY223 with a
`187,324.520 m` conservative margin. The only question here is whether that
geometry has a plausible measurement path worth qualifying. No alternate
station, date or product family was searched.

## Frozen candidate roles

| Role | Date | Geometry window GPS | Exact product name |
|---|---|---|---|
| qualification candidate | DOY221 / 2026-08-09 | 05:50:30--06:59:30 | `PIE100USA_R_20262210000_01D_30S_MO.crx.gz` |
| unopened primary candidate | DOY223 / 2026-08-11 | 05:42:00--06:51:00 | `PIE100USA_R_20262230000_01D_30S_MO.crx.gz` |

DOY221 is a distinct earlier product under the same documented hardware
interval and itself retains `186,900.574 m` geometric margin. The role labels
do not freeze a prospective primary and authorize no body access.

## Product-level metadata

Two HEAD requests were issued to the exact CDDIS locators. No response body or
byte range was requested.

| Role | HTTP | Content-Length | Last-Modified | ETag | Accept-Ranges |
|---|---:|---:|---|---|---|
| DOY221 qualification candidate | 200 | 3,111,600 | 2026-08-10 00:30:16 GMT | `2f7ab0-658a6754cdfed` | bytes |
| DOY223 primary candidate | 200 | 3,112,422 | 2026-08-12 00:25:15 GMT | `2f7de6-658ce9f13e195` | bytes |

Both responses declare `application/x-gzip`. Their IGS long names declare a
RINEX 3 mixed-observation product, one day duration, nominal 30 s cadence,
compact/Hatanaka encoding and gzip transport. Those filename declarations do
not prove actual header fields, epoch coverage or record continuity.

The predeclared BKG endpoint timed out at the transport boundary. That is a
descriptive transport result, not `CAPABILITY_REJECTED`; the exact CDDIS
products resolved the existence question. ETags are retained as HTTP metadata
only and are not treated as artifact hashes.

## Hardware continuity

The already frozen official station log was temporarily materialized and
matched its prior authority exactly:

- bytes: `29,326`;
- SHA-256: `de79c3d3f677bb6a8d61ab11fc0eee0215a39ef93d79668826cd2537248fe626`;
- prepared: 2026-03-25.

Its active intervals cover both candidate dates:

| Component | Identity | Installed | Removed |
|---|---|---|---|
| receiver | SEPT POLARX5TR, serial `4100427`, firmware `5.7.0` | 2026-03-10 21:27 UTC | open |
| antenna | ASH701945E_M NONE, serial `CR520022114` | 2007-01-23 18:00 UTC | open |

The station log also documents an H-maser timing source at the site and the
current receiver entry states that frequency input was moved to the 10 MHz
port with PPS input. This supports unchanged declared hardware and timing
architecture between DOY221 and DOY223; it does not establish the actual event
times or continuity of either observation file.

The temporary station log copy was destroyed after extraction. No observation
artifact was materialized.

## Clause status

| Clause | State | Evidence or blocker |
|---|---|---|
| exact RINEX 3 product path | SATISFIED_DESCRIPTIVELY | exact CDDIS HEAD 200 for both roles |
| declared 01D/30S mixed compact product | SATISFIED_DESCRIPTIVELY | IGS long-name semantics and content type |
| unchanged receiver/antenna interval | SATISFIED_DESCRIPTIVELY | exact-hash official station log |
| disciplined timing architecture | SUPPORTED_NOT_ADC_BOUND | H-maser, 10 MHz and PPS station-log entries |
| `L1C + L2W` and LLI | UNKNOWN | qualification header unopened |
| `C1C + C2W` witnesses | UNKNOWN | qualification header unopened |
| TIME OF FIRST/LAST OBS | UNKNOWN | qualification header unopened |
| actual 30 s epoch grid | UNKNOWN | filename declaration is insufficient |
| G22/G30 presence and continuity | NOT_EVALUATED | requires qualification records, not metadata |
| DOY223 primary integrity/hash | NOT_EVALUATED | primary candidate remains unopened |

## Interpretation and next boundary

PIE has a materially plausible measurement path: the exact historical files
exist, use the required product generation and share documented hardware. The
remaining uncertainty is narrow and empirical, not architectural.

The next maximum action requires explicit authorization for the DOY221
qualification candidate only. It should materialize and hash that complete
artifact before decoding, inspect its RINEX header and scan the predeclared
PIE/G22/G30 window structurally without persisting phase/code values. DOY223
must remain unopened throughout qualification.

Allowed qualification result:

```text
PIE_OBSERVER_QUALIFICATION_PASSED
PIE_OBSERVER_QUALIFICATION_FAILED
```

Do not create a new gate, generic parser framework or fallback station. Do not
open DOY223 until a passed DOY221 qualification and a separately reviewed
prospective plan exist.
