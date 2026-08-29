# Bounded blind-orbit assignment prospective plan

## Frozen status

```text
BLIND_ORBIT_ASSIGNMENT_PLAN_MARKDOWN_FROZEN
AMC_DOY226_PRIMARY_UNOPENED
```

This is one prospective proof design, not a new gate, prediction seal,
executor or measurement authority. It binds the orbit-only shortlist and one
logical AMC product without querying its existence, directory metadata, header
or body.

## Physical question

Can a scorer that receives no PRN-to-hypothesis mapping prefer the frozen
G22-relative-to-G30 orbital trajectory over four deliberately close orbital
alternatives and one equally calibrated affine null on a held-out suffix?

## New information produced

A future admitted outcome can distinguish:

- forward orbitality: whether any candidate orbit beats an affine-only model;
- bounded orbit specificity: whether G22 beats G06, G14, G17 and G19 under
  identical prefix-only nuisance authority;
- ambiguity: whether the real measurement fails to preserve the orbit-only
  separation predicted by the screen.

PIE and AMC cannot answer this question because their scorers knew named G22
and compared it with three large-separation alternatives. The later screen
proved only model discriminability and contained no measurement.

## Frozen geometry and product role

| Property | Value |
| --- | --- |
| observer | AMC400USA |
| target/reference measurement package | G22 minus G30 |
| GPS date | 2026-08-14 / DOY226 |
| raw window | 06:14:30--07:23:30 GPS |
| prefix | indices 0--78, 79 epochs |
| held-out | indices 79--138, 60 epochs; starts 06:54:00 GPS |
| cadence | 30 s |
| logical product | `AMC400USA_R_20262260000_01D_30S_MO.crx.gz` |
| sole body transport | GSSC `/gnss/data/daily/2026/226` |
| product existence | `UNKNOWN_UNQUERIED` |

The filename is fixed by the already selected station/date/cadence role. No
directory or product search was used to choose it. Failure to materialize this
exact product is terminal and authorizes no alternate station, day, cadence,
file or archive.

Before a complete-file hash exists, at most two attempts of this same logical
product may occur, and only for timeout or interrupted transport. After a
complete hash or any decode begins there is zero retry. A description or
serialization error remains distinct from measurement invalidity.

## Measurement coordinate and admission

The model-blind packager may extract only the already demonstrated AMC
coordinate:

```text
P_s(t) = alpha * lambda_L1 * L1C_s(t)
       + beta  * lambda_L2 * L2W_s(t)

Q(t) = P_G22(t) - P_G30(t)
Z(t) = Q(t) - Q(t_0)
```

The future primary may be scored only if all clauses pass:

- exact 139-epoch GPS grid or event-time deviation no greater than 15 s;
- normal epoch flags throughout;
- L1C, L2W, C1C and C2W present for G22 and G30 at every epoch;
- blank or zero LLI on both phase fields;
- header station, receiver, antenna, interval and `TIME OF LAST OBS` cover the
  complete window;
- no unsupported scale, phase-shift, time or frequency transform;
- finite values for every declared transform;
- per-satellite geometry-free second differences no greater than
  `0.09514683639918244 m`;
- complete same-path ionosphere-free phase-minus-code witness no greater than
  `1250 m` peak-to-peak per satellite.

Missing structure, nonzero LLI, abnormal epoch, unsupported transform or
geometry-free failure is `MEASUREMENT_INVALID`. A complete finite same-path
witness over its frozen limit or event-time error over 15 s is
`NOT_DETECTABLE`. Neither state may be changed by the receipt layer.

The value-blind AMC DOY222 qualification remains evidence only for the parser,
field family and configuration it actually observed. It does not prove DOY226
existence, coverage or numerical health.

## Opaque hypothesis topology

`GNSS_BLIND_ORBIT_ASSIGNMENT_MAPPING_SEAL.json` freezes six opaque identifiers
before primary access:

- five candidate orbital curves: G22, G06, G14, G17 and G19, each relative to
  fixed G30;
- one affine-only non-orbital null.

The scorer interface receives:

- one finite observed coordinate;
- six opaque identifiers;
- six same-grid model arrays;
- prefix/held-out indices;
- the frozen guard and ordering rule.

It must not receive or import satellite names, target role, mapping-seal path,
navigation parser, observation decoder, product metadata or primary/reserve
information. Every orbital array and the affine null are handled by one
identical scoring loop. The opaque score receipt must be serialized and hashed
before the mapping is used to interpret the winning identifier.

The mapping seal is committed and reviewable; it does not claim cryptographic
secrecy against a person reading the repository. The protected property is a
testable data-flow boundary: no identity-dependent branch exists in the scorer.

## Nuisance and scoring

For each opaque hypothesis independently:

1. form `observed - model` on the identical 139-epoch grid;
2. fit exactly one constant and one linear rate using prefix indices 0--78;
3. propagate those two frozen coefficients into indices 79--138;
4. compute held-out residual peak-to-peak and RMS.

For the affine-only null, the supplied model array is identically zero, so the
same operation is exactly a prefix-frozen affine extrapolation of the observed
coordinate. There is no suffix fit, free time phase, time warp, interpolation,
gap bridging, spline, per-sample correction or candidate-dependent complexity.

Ordering is peak-to-peak, then RMS, then opaque identifier. A hypothesis is
preferred only when the runner-up minus best held-out peak-to-peak residual is
strictly greater than the unchanged pairwise guard:

```text
7339.701234647398 m
```

Otherwise the result is `AMBIGUOUS`. No threshold may be changed after primary
access.

## Detectability frozen by the orbit-only screen

| Contender | Model-only separation m p-p | Remaining after guard m |
| --- | ---: | ---: |
| affine-only null | 18,763.717 | 11,424.015 |
| G06 | 26,484.407 | 19,144.706 |
| G14 | 49,342.719 | 42,003.018 |
| G17 | 54,723.200 | 47,383.498 |
| G19 | 94,418.837 | 87,079.136 |

The affine-only null is controlling. Minimum direct `t +/- 15 s` elevation is
`15.01043286179639 deg`; complete-window coverage is therefore immutable and
cannot be repaired by shortening or shifting the window.

## Terminal outcomes

Before scoring:

```text
PRIMARY_ARTIFACT_MATERIALIZATION_FAILED
PRIMARY_DESCRIPTION_ERROR
BLINDING_INVALID
MEASUREMENT_INVALID
NOT_DETECTABLE
```

After one opaque score and mapping reveal:

```text
BOUNDED_TRUE_ORBIT_PREFERRED
BOUNDED_ALTERNATIVE_ORBIT_PREFERRED
FROZEN_AFFINE_NULL_PREFERRED
AMBIGUOUS
```

`BOUNDED_ALTERNATIVE_ORBIT_PREFERRED` must retain the exact alternative from
the precommitted mapping. It is a physical negative for G22 inside this family,
not a software failure. `AMBIGUOUS` is also a valid terminal physical outcome.

## Claim scope

The maximum positive claim is:

```text
BOUNDED_ORBIT_ASSIGNMENT_PREFERRED_WITHIN_FROZEN_CANDIDATE_SET
```

It does not establish targetless identity, free orbit recovery, catalog-wide
uniqueness or independence from the receiver's upstream PRN correlation.

## Stop boundary

This Markdown and mapping seal perform zero network requests and contain zero
observation locators queried, headers, payload bytes, decoded values or scores.
They grant no primary access.

The next maximum work after review is an offline exact-hash prediction bundle
and scorer implementation whose source surface cannot read the mapping seal.
Do not build an executor or access the DOY226 product in that step.

