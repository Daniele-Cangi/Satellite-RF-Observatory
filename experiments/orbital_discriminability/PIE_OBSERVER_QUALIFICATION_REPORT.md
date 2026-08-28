# PIE observer structural qualification outcome

Terminal outcome:

```text
PIE_OBSERVER_QUALIFICATION_PASSED
```

This is a value-blind measurement-path result for the frozen PIE100USA DOY221
qualification product. It is not measurement admission, an orbital score, a
prospective-plan freeze, or authority to open the DOY223 primary candidate.

## Frozen execution identity

The one-shot executor and its scientific parameters were committed before the
qualification product body was requested:

```text
source commit
a7d154e458a8d3cdd50b45421a318cb2e153ad09

executor source SHA-256
5cd0e7ba77c0f7f19b174ad6ffa94819cba366f4448293177b09ac9c51237548

executor manifest SHA-256
e1664c49e5bb3589152b7a821898382d24860ff19f26e1d41f825037bfd156f4
```

The sole admitted product was:

| Property | Value |
|---|---|
| station | `PIE100USA` |
| date | 2026-08-09 / DOY221 |
| product | `PIE100USA_R_20262210000_01D_30S_MO.crx.gz` |
| complete bytes | 3,111,600 |
| complete MD5 | `2ef135588a873b4204a9fa9a35272106` |
| complete SHA-256 | `6a39f3ee411bd43d32befb856fc54ea8bd6d4db41a1669ca7823bc5e1931e0d3` |

The complete-file byte count and hashes were computed before decompression or
record scanning. CDDIS remained the descriptive authority; its HEAD metadata
had declared the same byte count. The body was materialized through the
documented GSSC anonymous web session. GSSC returned `1` in the directory field
where an MD5 may appear, so that field was not treated as a published checksum.
The full MD5 above is a locally computed identity only; SHA-256 is the retained
cryptographic artifact identity.

## Header and transform boundary

The decoded header confirms the pre-access station-log configuration:

| Property | Frozen observation |
|---|---|
| RINEX | 3.04 |
| receiver | SEPT POLARX5TR, serial `4100427`, firmware `5.7.0` |
| antenna | ASH701945E_M NONE, serial `CR520022114` |
| cadence | 30 s |
| declared span | 2026-08-09 00:00:00--23:59:30 GPS |
| required fields | L1C, L2W, C1C, C2W |
| receiver clock offsets applied | no, by the RINEX 3.04 default |

The declared phase-shift records were retained descriptively. No phase, code,
signal-strength, clock-offset, or other numerical observation scalar was
parsed or persisted. The GPS time tags were not silently relabeled UTC.

## Structural clause results

The frozen window is 2026-08-09 05:50:30--06:59:30 GPS, inclusive, with the
future held-out boundary at 06:30:00 GPS. It contains exactly 139 epochs.

| Clause | State | Evidence |
|---|---|---|
| artifact materialization and pre-decode hash | SATISFIED | exact product, 3,111,600 bytes, complete SHA-256 |
| header configuration and full window | SATISFIED | exact receiver/antenna, 30 s cadence, TIME OF FIRST/LAST OBS enclosing the window |
| G22/G30 core L1C/L2W plus LLI structure | SATISFIED | one complete 139-epoch segment on each link; no structural break |
| same-path C1C/C2W witness | SATISFIED | 139/139 epochs on all four satellite/observable paths, including indices 0, 78, 79 and 138 |
| geometry-free numerical phase health | NOT_EVALUATED | prohibited by the value-blind qualification authority |
| measurement admission | NOT_EVALUATED | requires a separately frozen prospective contract |
| orbital-versus-null comparison | NOT_EVALUATED | no orbit, prediction, null or score entered the qualifier |

All 1,668 structural rows are `PRESENT`. Each of G22 and G30 has one maximal
4,140-second segment spanning the full frozen window. C1C and C2W coverage is
1.0 for both satellites. S1C/S2W remain optional descriptive diagnostics and
were not used for admission.

## Causal failure attribution during materialization

Four earlier attempts were retained as atomic descriptive receipts rather than
being converted into capability rejection:

| Receipt | Attribution | SHA-256 |
|---|---|---|
| `PIE_OBSERVER_QUALIFICATION_MATERIALIZATION_FAILURE.json` | CDDIS body redirected to an Earthdata login document | `19c3ca2961f3d048981c92ec7c1dfef04ef730325552de972c932d28edfbda1d` |
| `PIE_OBSERVER_QUALIFICATION_GSSC_LOGIN_DESCRIPTION_FAILURE.json` | the initial GSSC client expected a nonexistent JavaScript login token | `924fe9161e8a4a12ee39efc605adbb6490e3475b73eca738f779966085c39f67` |
| `PIE_OBSERVER_QUALIFICATION_GSSC_SESSION_FAILURE.json` | the first client did not preserve the authenticated web-session state | `c57ef56e8e48ac06df10e2b114c708ae263cc849b00f6ca68d17988e4d0f63c3` |
| `PIE_OBSERVER_QUALIFICATION_GSSC_DOWNLOAD_URL_FAILURE.json` | the client encoded WingFTP's bare `download` flag incorrectly | `78f978190aec947816717cb1695897083df83ef452d21ec91603d33b733a9f38` |

Each repair changed only transport/description mechanics before complete-file
hashing. No failed attempt reached decompression, header parsing, structural
classification, or a physical decision.

## Receipt boundary

| Receipt | Rows/bytes | SHA-256 |
|---|---:|---|
| `PIE_OBSERVER_QUALIFICATION_OUTCOME.json` | 3,011 bytes | `006554154cd014f25414d9507149f08580fc247460d335419eec66bc3c61f37e` |
| `PIE_OBSERVER_QUALIFICATION_SUMMARY.json` | 4,932 bytes | `8813d699753af9729bf122c893641598bb837b57c9f7c090e5dd67073143a4ba` |
| `PIE_OBSERVER_QUALIFICATION_COVERAGE.jsonl` | 1,668 rows | `773e84d7f2c5d9698a7a90745386c60fdfbc015ea9ad9c4041c7e0380881961e` |

The JSON Lines receipt contains structural states and lineage only. The
compressed and decoded observation artifacts existed only in RAM and were
destroyed after the receipt was formed. Persisted compressed bytes, decoded
bytes, observation values and orbital scores are all zero.

## Authorized and unauthorized claims

Authorized:

- the exact DOY221 artifact was complete and hashable;
- the documented PIE receiver/antenna configuration is present in the real
  header;
- the frozen G22/G30 window exposes uninterrupted L1C/L2W field structure,
  blank-or-zero LLI structure, and complete C1C/C2W same-path witnesses;
- this signal family may enter a separate prospective-plan review for PIE.

Unauthorized:

- numerical phase continuity, measurement validity, orbital preference or
  satellite-identity claims;
- inference that DOY223 has the same fields or continuity;
- any statement about the unopened DOY223 artifact identity or hash;
- fallback to another observer, date, duration, satellite pair or threshold.

## Stop

DOY223 remains completely unopened: zero locator requests, headers, payload
bytes and values. The next maximum authority is
`PROSPECTIVE_PLAN_REVIEW_ONLY`. That review must decide whether the already
frozen PIE/DOY223 geometry, this independently qualified signal family and a
predeclared numerical phase-health/admission rule are sufficient to freeze one
primary experiment. It grants no observation access by itself.
