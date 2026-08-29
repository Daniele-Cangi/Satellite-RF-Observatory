# Blind-orbit opaque prediction and scorer seal

## Outcome

```text
BLIND_ORBIT_PREDICTION_AND_SCORER_SEALED
PRIMARY_DOY226_UNQUERIED_AND_UNOPENED
```

This is the reviewed offline boundary immediately downstream of the frozen
prospective plan. It is not a primary execution, observation decoder, identity
claim or new gate.

## Physical information protected

The future experiment can now test whether one of six predeclared dynamics is
preferred by the held-out AMC coordinate without allowing hypothesis identity
to change the scoring path. The bundle contains five orbital trajectories and
one non-orbital trajectory, but exposes them only as six opaque identifiers.

The scorer has no named orbit, target, reference, mapping-seal, navigation
compiler or observation-product input. Every hypothesis receives exactly the
same two prefix parameters: one constant and one linear rate. The 60-epoch
held-out suffix cannot refit, shift, warp or interpolate the model.

This is interface blindness, not adversarial secrecy. A repository reader can
inspect the separately committed mapping. The scientific protection is that
the scorer source and runtime interface have no identity-dependent branch.

## Exact artifacts

| Artifact | Canonical bytes | SHA-256 |
| --- | ---: | --- |
| opaque prediction bundle | 20,849 | `a36aed59f32ee9b409778e44a0b661aebbf83c0675c58473c6655ad562c82ee2` |
| curve set | n/a | `0e5eb9207a15574cf66d25f5f1eccdedb4e9ec4129a32abf5d23a066fdd9b2df` |
| prediction/scorer seal | 2,962 | `2403358fed46293a1c44a9a7576a52c4cac547507abec1da1be5db1c7ff711f4` |
| scorer source | n/a | `ef064788296caaf0d1d48e2b25621ae99fb935c1a964ac5b9ffc17138a266dda` |

The prediction compiler is bound to commit
`9b17c7b39fe672cc3bcce01be8816f8b2ff92c6c` and source SHA-256
`3160bc4ab9c9fbbabca20457d7cfd4aa14d3d84f8a388ca850a6162504600544`.
The scorer and seal compiler are bound to commit
`28740c0af2964ba644f1c7e58307ab94057e5393`.

## Prediction materialization

Only the already frozen NOAA broadcast-navigation product
`brdc2260.26n.gz` entered the compiler. It matched the predeclared 71,489-byte
size and SHA-256
`d2b2006769aac07d40497c547edef37c1cf1a32780981dffab971c610ae5b0b9`.
It is orbit metadata, not receiver observation data. The temporary copy was
destroyed after bundle compilation.

The compiler reproduced the screen's exact held-out separations, direct
`t +/- 15 s` trajectory handling and minimum joint visibility. It then removed
all PRN, observer, product, mapping and provenance fields from the scorer
bundle. The output contains only grid, opaque IDs, arrays and frozen scoring
constants.

## Scorer semantics

For every opaque array, in one identical loop:

1. subtract the array from the future finite 139-point coordinate;
2. fit a constant and rate on indices 0--78 only;
3. project the frozen fit through indices 79--138;
4. compute held-out peak-to-peak and RMS;
5. order by peak-to-peak, RMS and opaque ID;
6. prefer the best only if runner-up minus best peak-to-peak is strictly above
   `7339.701234647398 m`.

Otherwise the opaque outcome is `AMBIGUOUS`. The score receipt persists no
observation array. Its canonical SHA-256 must be persisted before the mapping
may be used to interpret the winning identifier.

Synthetic seam tests recover an exact opaque trajectory after an added
constant and linear rate with a controlling `18763.716565 m` preference
margin. A midpoint between the controlling pair returns `AMBIGUOUS` with zero
margin. The scorer makes an owning working copy before its RAM cleanup, so the
caller-owned coordinate remains unchanged. These are software-path tests, not
measurements or orbital outcomes.

## Access boundary and next maximum

```text
primary locators queried: 0
primary headers opened: 0
primary payload bytes: 0
primary observation values: 0
orbital scores from measurement: 0
executor present: false
```

After review, the next maximum action is one explicitly authorized
materialization of the exact AMC DOY226 product followed by structural and
physical admission, packaging of one unlabeled coordinate, one opaque score,
receipt hashing, and only then mapping reveal. No alternate product, window,
station, cadence, candidate family, threshold or post-hash retry is allowed.
