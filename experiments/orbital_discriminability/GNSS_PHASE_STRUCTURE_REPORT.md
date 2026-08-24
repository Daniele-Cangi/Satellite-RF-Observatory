# G22/G30 DOY 216 value-blind structural outcome

## Terminal result

```text
GNSS_PHASE_STRUCTURE_REJECTED
```

This is a measurement-topology refusal, not a transport, serialization or
parser error. It does not evaluate geometry-free phase health, measurement
admission, the orbital model or any null. The DOY 220 primary remains sealed.

## Exact qualification artifacts

Both predeclared artifacts were materialized in RAM on the first attempt and
SHA-256 hashed before Hatanaka decompression.

| Station | Product | Bytes | SHA-256 |
|---|---|---:|---|
| GOLD00USA | `GOLD00USA_R_20262160000_01D_30S_MO.crx.gz` | 2,197,783 | `286babf58a11d8a87c8b72a07f7fd1de03c8cd0fa844afa8d571a25ddf2eeb21` |
| NLIB00USA | `NLIB00USA_R_20262160000_01D_30S_MO.crx.gz` | 2,551,870 | `a0ae412ed32b31e31aa879cebab43a8c1c9329cc106eac5a44631a88bdf347c8` |

Both headers match the frozen receiver/antenna configurations, declare GPS
time at 30-second cadence, contain `TIME OF LAST OBS`, cover the complete
window, and declare L1C/L2W plus C1C/C2W. There were no parser issues,
unsupported continuations, off-grid epochs or nonzero epoch flags.

## Exact structural failure

GOLD is complete for G22 and G30 over all 386 raw epochs: both phase fields,
both code witnesses and both optional S fields are present, with zero/blank
LLI throughout.

NLIB does not preserve the four-link phase coordinate over the frozen window:

| Link | Structural breaks |
|---|---|
| NLIB–G22 L1C | 32 blank fields, 4 absent satellite records, 3 nonzero LLI |
| NLIB–G22 L2W | 40 omitted trailing fields, 4 absent satellite records, 2 nonzero LLI |
| NLIB–G30 L1C | 14 blank fields |
| NLIB–G30 L2W | 14 blank fields and 1 nonzero LLI |

The longest joint four-link segment is
`2026-08-04 05:29:30--07:50:00 GPS`, 282 epochs and 8,430 seconds elapsed.
It cannot replace or move the predeclared 386-epoch window. Other joint
segments contain only 5, 34 and 4 epochs.

The same-path code clause also fails independently:

- NLIB–G22 C2W: 342/386 present (88.601%), with raw indices 1, 77 and 78
  omitted;
- NLIB–G30 C1C: 381/386 present (98.705%), but raw index 384 is blank;
- NLIB–G30 C2W: 372/386 present (96.373%), but raw index 384 is blank.

NLIB–G22 C1C passes at 382/386 (98.964%) with every frozen boundary present.
Optional S1C/S2W states were descriptive and did not cause the refusal.

Across 9,264 atomic rows the state counts are:

```text
PRESENT                 9,022
BLANK                     122
TRAILING_FIELD_OMITTED    120
```

## Authorized and unauthorized claims

Authorized:

- both exact DOY 216 artifacts and headers were materially available;
- the frozen GOLD/NLIB G22/G30 qualification topology is not continuous over
  the complete selected window;
- the refusal is caused by actual NLIB field/LLI/code topology, not software;
- the geometry-only visibility envelope did not guarantee receiver phase lock
  at the low-elevation edges.

Not authorized:

- that G22/G30 lacks an orbital signature;
- that phase values disagree with the orbital model;
- that geometry-free phase is unhealthy;
- measurement admission or any orbital-versus-null score;
- shortening or shifting the window after observing this topology;
- discovery or access of the DOY 220 primary.

The result exposes the remaining abstraction error: geometric visibility and
RINEX product availability are not the same as continuous carrier-phase
capability. Any later experiment must predeclare a capability envelope that
includes actual lock/field continuity, or choose a geometry/window with enough
guard to make that property independently qualifiable. This is a future
change-of-abstraction question, not authority to search or retry now.

## Receipt integrity and persistence

| Receipt | Bytes | SHA-256 |
|---|---:|---|
| `GNSS_PHASE_STRUCTURE_COVERAGE.jsonl` | 3,517,896 | `193a1999b290341145883d425ec2114ebfd6895910a10ce6053ca5174354fb4b` |
| `GNSS_PHASE_STRUCTURE_SUMMARY.json` | 8,157 | `4e233e41c17bbddf6c8b57b492bae1cde23a9f5a1c362e18746e4ba0d3f3c874` |
| `GNSS_PHASE_STRUCTURE_OUTCOME.json` | 2,149 | `7b7efb4fc3fb81e029f85bebde1e9f53520a49ffb9f5909a200ea4da4ec571d8` |

The run is bound to pre-access source commit
`a5033c9ce84c483fea9ebd43c75918a3dec9cf32`, contract manifest
`76c42055467c9b63e05911dc21611b6e26b0d9206f808b0c74b2f9c1696bcc86`
and scanner manifest
`dd4ee054988541696ae8c7f14b82640262ab4531750e0e64ce03ba342e1d071c`.

Compressed artifacts persisted: zero bytes. Decoded RINEX persisted: zero
bytes. Observation scalars parsed or persisted: zero. DOY 220 header, payload
and value access: zero.
