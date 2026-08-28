# AMC observer-replication metadata report

## Outcome

`AMC_REPLICATION_METADATA_PATH_AVAILABLE`

This is a bounded metadata-only result. No AMC observation product, RINEX
header, record or value was requested. It creates no new gate and authorizes
no qualification or primary access.

## Physical decision

```text
Physical question:
Does the frozen G22 orbital preference reproduce at a second observer and on
a pass distinct from the successful PIE held-out observation?

New information produced:
Whether the PIE result survives both a new physical receiver root and a new
pass, rather than remaining compatible with a PIE-specific or DOY223-specific
systematic.

Why existing experiment cannot answer it:
PIE establishes one held-out station/window. GOLD/NLIB supplied the earlier
two-station evidence and therefore cannot be counted as another unseen root.

Minimum experiment:
One AMC-only structural qualification on DOY222 followed, only if it passes,
by one prospective AMC DOY221 observation using the same no-fit observer
coordinate and frozen null discipline.

Stop condition:
Stop if DOY222 cannot establish the exact field, timing, continuity and
same-path witness family, if historical equipment continuity fails, or if the
DOY221 physical margin no longer remains positive before observation access.
```

## Route comparison

The choice uses only the already frozen observer-transfer screen.

| Route | New independence | Geometry | Main limitation |
| --- | --- | --- | --- |
| AMC400USA / DOY221 | new station and new pass | `159,899.492 m` remaining margin; `25.726 deg` minimum shifted elevation | receiver family is also POLARX5TR |
| DRAO00CAN / DOY221 | new station, pass and receiver model | `19,155.284 m` remaining margin; `15.088 deg` minimum shifted elevation | much smaller margin and near-threshold elevation |
| PIE100USA / another pass | new pass only | large modeled margin | cannot challenge PIE-specific systematics |
| broader wrong-orbit family only | stronger model comparison, no new observation | not yet computed | cannot replicate the physical measurement by itself |

AMC is selected because it changes both station and pass while retaining a
large conservative margin and a substantially cleaner elevation guard. The
shared receiver family is not silently treated as independent. It is retained
as a possible common implementation systematic, while the actual physical
roots are checked below.

## Independent hardware and clock lineage

The official IGS AMC site log was read from its predeclared URL. It is `13,049`
bytes with SHA-256
`c510f416437c2aa941b565b589159b3ca5447bcf51e21374246e49661c4f82c5`,
identical to the previously frozen station-screen receipt.

For both candidate dates it documents:

- station/DOMES: `AMC400USA` / `40472S005`;
- receiver: `SEPT POLARX5TR`, serial `3013929`, firmware `5.6.0`;
- receiver effective from `2025-08-28T14:53Z` with no removal date;
- antenna: `TPSCR.G5C NONE`, serial `1364-10065`;
- external frequency standard: `H-MASER`, `5.0 MHz`, USNO Alternate Master
  Clock #1 lineage;
- monument and organisation distinct from PIE100USA.

PIE used receiver serial `4100427`, firmware `5.7.0`, antenna serial
`CR520022114` and a different station clock chain. Thus AMC and PIE are
independent receiver, antenna, monument and clock roots even though both use
the POLARX5TR family. A firmware-family common mode remains a declared
limitation of the eventual claim.

## Predeclared roles

| Role | Date/window GPS | Logical product | Observation access |
| --- | --- | --- | ---: |
| structural qualification candidate | DOY222, `05:37:30--06:46:30` | `AMC400USA_R_20262220000_01D_30S_MO.crx.gz` | 0 |
| prospective replication primary candidate | DOY221, `05:41:30--06:50:30` | `AMC400USA_R_20262210000_01D_30S_MO.crx.gz` | 0 |

There is no reserve. Qualification failure authorizes no substitution. The
DOY221 held-out suffix would begin at `06:21:00 GPS` after the same fixed
79-epoch prefix and would contain 60 untouched epochs.

## Product descriptions

Only documented anonymous GSSC session directory descriptions were read.
Neither named file was downloaded.

| DOY | Directory response bytes | Directory SHA-256 | Unique file match | Declared product bytes | Modified |
| ---: | ---: | --- | ---: | ---: | --- |
| 221 | 491,472 | `1f30600686f3ae8e466bcc796e3538bcdf601d2d7e2d676f839357c320d600b5` | 1 | 3,415,979 | `2026-08-10 03:01:38` |
| 222 | 488,949 | `207aece33d1d72add0da59228104de955f8b241416f07e9ae55d93f3c41dd573` | 1 | 3,455,043 | `2026-08-11 03:01:26` |

The directory's `md5` field is the literal value `1` for both products and is
not treated as a checksum. Complete-file hashes remain unknown until a later
explicitly authorized materialization.

## Frozen geometry inherited, not re-scored

The DOY221 candidate remains exactly the third entry from the pre-observation
observer shortlist:

- controlling null: `FROZEN_AFFINE_NULL`;
- held-out separation: `162,247.192926 m` peak-to-peak;
- pairwise comparison envelope: `2,347.701235 m`;
- remaining margin: `159,899.491692 m`;
- minimum time-shifted model elevation: `25.725628 deg`.

No PIE observation value or outcome score was reused to select an AMC window,
and the consumed PIE result is not rescored.

## Unknown until structural qualification

Filename and site metadata do not prove:

- RINEX header identity and complete frozen-window coverage;
- actual L1C/L2W phase and LLI fields for G22/G30;
- C1C/C2W same-path witness availability;
- deterministic 139-epoch continuity without gaps or nonzero LLI;
- geometry-free phase health;
- the quantitative phase-minus-code witness on AMC.

The next maximum action is one value-blind DOY222 structural qualification,
with full hash before decode and zero persisted observation values. It requires
a separate explicit authorization. DOY221 must remain unopened until that
qualification passes and a new prospective plan and prediction are reviewed.
