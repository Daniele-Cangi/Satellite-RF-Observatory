# G22/G30 distinct-pass replication seal

Terminal offline state:

    REPLICATION_PLAN_AND_PREDICTION_FROZEN

No observation product was discovered, opened or decoded. DOY 219 replication
and DOY 218 reserve remain sealed.

## Why this is the next experiment

The completed DOY 220 primary preferred the frozen orbital model, but one pass
cannot establish repeatability. Three routes were compared:

- the same independent hardware roots on a distinct pass;
- a new station pair;
- a new target/reference satellite pair.

The first route was selected because it directly tests the missing
repeated-pass property with the fewest new assumptions. It introduces
independent date, pass geometry and observation artifact. It deliberately
leaves station-pair, receiver-family and scorer systematics shared, so it
cannot authorize hardware-general claims.

## Prospective selection

The date rule existed before the DOY 220 outcome: rank by joint four-link
elevation guard, then remaining physical margin, then date. After removing
consumed DOY 220 and qualification DOY 217, DOY 219 is the first unopened
candidate. DOY 218 remains sealed as a reserve and cannot be used as a retry.

| Role | Raw GPS interval | Held-out start |
| --- | --- | --- |
| DOY 219 replication | 2026-08-07 05:46:00--06:55:00 | 06:25:00 |
| DOY 218 sealed reserve | 2026-08-06 05:50:00--06:59:00 | 06:29:00 |

No product availability, header or observation value influenced this
selection.

## Frozen prediction

The exact DOY 219 broadcast NAV authority was verified before use:

- compressed bytes: 1,391,036;
- compressed SHA-256:
  12246e0e614f0a16c9bd7329ddd637fb541d478160d944131023aa9faeffcc3d;
- decoded bytes: 8,383,950;
- decoded SHA-256:
  8d5126ae5a7a8ad1e718c11a1c575c0961de1c57845ca15da4081e65e5709b5d.

Because the host volume reported no free space, the compressed NAV was
downloaded, hash-checked, decompressed and parsed in RAM. This changes no
scientific parameter and created no observation capability in the compiler.

The frozen model-only regressions are:

| Comparison | Held-out peak-to-peak |
| --- | ---: |
| prefix-affine | 11,569.974689858733 m |
| wrong orbit G01 | 8,986.714337965008 m |
| wrong orbit G14 | 59,929.330243222300 m |
| wrong orbit G17 | 121,986.514415665000 m |

G01 remains controlling. Its separation exceeds the conservative
2,377.702990288828 m pairwise guard by 6,609.011347676180 m.

## Frozen scoring and admission

The later measurement, if separately authorized, must preserve:

- GOLD00USA and NLIB00USA;
- G22 target and G30 reference;
- L1C/L2W ionosphere-free continuous phase;
- 139 raw epochs at 30 seconds;
- 77 feature epochs for constant-plus-rate calibration;
- 60 untouched held-out feature epochs;
- the same prefix-affine and G01/G14/G17 nulls;
- no interpolation, gap bridging, free time phase or suffix refit;
- the existing LLI, code-witness and geometry-free health clauses.

The one-model calibration envelope is 1,188.851495144414 m. No threshold or
null can change after this seal.

## Hash ledger

- prospective plan manifest SHA-256:
  a9c7b00feb9b2fa277e5cd8d71ec22d6726cc4068bf932ef67560b07d68250ed;
- compiler source commit:
  bed2258e57d31910bacec3f3c17fe9917098042a;
- compiler source canonical SHA-256:
  8c40a868e97e668bf56e2f7184fb8ec42572c15cf2b9672402cbcde7235d8349;
- prediction canonical SHA-256:
  d408696d5c9d6e446216fdd7bad240a300e4d0d6d27af470756ff7d1413896b0;
- curve-set SHA-256:
  189ded42848dea792b0473726f2d24401452fa45d7a0843eac9e66c734b16fea;
- seal canonical SHA-256:
  8d4466be2037420fb251f7ed70de8d463d9489264948245606a1a65b5d79987d.

The seal grants no observation authority. The next permitted action requires a
separate review and may authorize at most one attempt for each predeclared
DOY 219 locator. It cannot authorize DOY 218.
