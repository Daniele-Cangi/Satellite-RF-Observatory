# Bounded blind-orbit assignment geometry screen

## Outcome

```text
BLIND_ASSIGNMENT_GEOMETRY_SHORTLISTED
```

The screen found one difficult, robustly discriminable orbit family before any
new observation product was discovered or opened. This is an orbit-only result.
It selects no qualification artifact or primary product, freezes no prospective
plan and authorizes no measurement claim.

## Physical question and information gain

The forward PIE and AMC experiments showed that a frozen G22-relative-to-G30
trajectory predicts held-out phase structure better than one affine null and
three large-separation wrong-orbit alternatives. They did not ask whether a
scorer deprived of the PRN mapping could distinguish G22 inside a deliberately
close, predeclared orbital family.

This screen asks only whether such a bounded assignment problem exists. The
answer is positive for the exact five-day, one-observer scope frozen in
`GNSS_BLIND_ORBIT_ASSIGNMENT_SCOPE.md`.

The future maximum claim remains limited to:

```text
BOUNDED_ORBIT_ASSIGNMENT_PREFERRED_WITHIN_FROZEN_CANDIDATE_SET
```

The receiver has already correlated GNSS spreading codes upstream. Hiding the
PRN-to-hypothesis mapping from a future scorer does not make the measurement
targetless and cannot establish free orbit recovery or RF identity.

## Frozen model-only inputs

- observer: AMC400USA, `38.803125 deg`, `-104.524597 deg`, `1911.3941 m`;
- target/reference mechanism: `G22 - G30`;
- model population: every healthy GPS broadcast orbit except target and
  reference;
- exact grid: 139 epochs at 30 s, 79 prefix and 60 held-out;
- event-time geometry: nominal and direct common `t +/- 15 s` trajectories;
- complete elevation requirement: `15 deg` for target, reference and every
  retained alternative;
- unchanged AMC pairwise decision guard: `7339.701234647398 m`;
- robust admission: every controlling separation must be at least two guards,
  `14679.402469294797 m`.

Every hypothesis receives the same two-parameter constant-plus-rate nuisance,
fit only on the 79-epoch prefix. There is no held-out refit, free time phase,
time warp, spline or candidate-dependent complexity.

## Navigation authority

The five predeclared NOAA RINEX 2.11 broadcast-navigation products were
materialized after scope and compiler commits, hashed, parsed in RAM and then
deleted.

| DOY | Compressed bytes | Compressed SHA-256 | Raw bytes | Raw SHA-256 |
| ---: | ---: | --- | ---: | --- |
| 224 | 71,290 | `51b07e0b...33787160` | 296,253 | `382a4269...58638f0` |
| 225 | 71,213 | `4d041840...9e5a122e` | 296,234 | `cfe3d00c...ec4c314f` |
| 226 | 71,489 | `d2b20067...0ae5b0b9` | 297,923 | `4042f7a4...1f05d665` |
| 227 | 69,478 | `14db10ee...8eab2015` | 290,097 | `0bcacf56...9643a4cf` |
| 228 | 70,468 | `5d3e15a6...f7dc16bd` | 295,515 | `9a9aaa59...931c1981` |

The receipt retains the complete hashes. These are orbit-model artifacts, not
receiver observations.

## Selection result

All five days contained robust windows. The deterministic difficult-first rule
ranked only each day's best robust window:

| Rank | DOY | Raw start GPS | Candidate family | Fourth-nearest separation m p-p |
| ---: | ---: | --- | --- | ---: |
| 1 | 226 | 2026-08-14 06:14:30 | G22 / G06 / G14 / G17 / G19 | 94,418.837 |
| 2 | 225 | 2026-08-13 06:18:30 | G22 / G06 / G14 / G17 / G19 | 94,614.476 |
| 3 | 224 | 2026-08-12 06:22:30 | G22 / G06 / G14 / G17 / G19 | 94,811.212 |

The selected orbit-only window is:

| Property | Frozen value |
| --- | --- |
| date | GPS DOY226 / 2026-08-14 |
| raw window | 06:14:30--07:23:30 GPS |
| calibration prefix | indices 0--78 |
| held-out start | 06:54:00 GPS |
| held-out suffix | indices 79--138 |
| family | G22, G06, G14, G17, G19 |
| minimum direct-time-shifted elevation | 15.010433 deg |

The minimum elevation is only `0.010433 deg` above the frozen threshold. That
is a real geometric fragility, not a reason to move the window after selection.
Any later measurement must retain the complete window or fail admission.

## Controlling separations

| Hypothesis relative to G22 truth | Held-out separation m p-p | Remaining after one guard m | Double-guard pass |
| --- | ---: | ---: | --- |
| prefix-frozen affine null | 18,763.717 | 11,424.015 | yes |
| G06 | 26,484.407 | 19,144.706 | yes |
| G14 | 49,342.719 | 42,003.018 | yes |
| G17 | 54,723.200 | 47,383.498 | yes |
| G19 | 94,418.837 | 87,079.136 | yes |

The affine null, not an orbital alternative, is controlling. The combined
remaining margin is `11424.01533014155 m`. The nearest alternative orbit is
G06 with `19144.705988368158 m` remaining after the same guard.

This is substantially harder than the earlier AMC wrong-orbit family, but it
is not yet evidence that measured phase will preserve the distinction.

## Observation boundary

The committed receipt records:

- zero observation locators and products discovered;
- zero observation headers, payload bytes and values;
- zero consumed outcomes reopened or rescored;
- zero measurement-derived orbital scores;
- no primary, qualification artifact or prospective plan selected.

The five broadcast-navigation files were removed after compilation. No
ephemeris payload remains in the working tree.

## Exact remaining blocker

Before any observation access, a separate review must decide whether to freeze
one prospective measurement with all of the following:

1. opaque hypothesis identifiers and a PRN mapping sealed outside the scorer;
2. an evaluator that receives identical model coordinates and prefix-only
   nuisance authority for all five orbital hypotheses and the affine null;
3. the existing AMC measurement transform and guard unchanged;
4. product-independent receiver/antenna/configuration continuity through
   DOY226;
5. one exact logical primary product and zero replacement after freeze;
6. terminal outcomes that separate measurement invalidity, not detectability,
   ambiguity, affine preference and bounded orbit-assignment preference.

The existing AMC DOY222 qualification may be cited only for the measurement
transform and historical configuration it actually demonstrated. It cannot
prove DOY226 product existence, complete-window coverage or primary health.

The next maximum work is therefore:

```text
REVIEW_BEFORE_OPAQUE_HYPOTHESIS_PLAN_AND_ONE_NEW_PRIMARY_SELECTION
```

It is not another station search, raw-RF dataset search, detector or generic
blind-inference framework.

## Reproducibility

- scope commit: `00bb74da2ad2a494c2e6bf0b92d45a124c46680f`;
- compiler source commit: `0f08f0956fc24dcbe4eabb7fa08314b02a15b743`;
- compiler source SHA-256:
  `022760e60d5f72a9a1efe857e49ac1cb9b2578f49ce076b780370bc1adf5b132`;
- receipt bytes: `46,895`;
- receipt SHA-256:
  `cddc9fcf0db1be7f55fde04f1bf51256c3a88edf2608871b3bc7e438bd167485`.

