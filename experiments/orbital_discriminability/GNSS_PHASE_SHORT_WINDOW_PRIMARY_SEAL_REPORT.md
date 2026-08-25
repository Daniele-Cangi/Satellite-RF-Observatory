# GNSS short-window primary scorer seal

Status: PRIMARY_SCORER_FROZEN_PRIMARY_UNOPENED.

This is the offline seal for the already frozen GOLD00USA/NLIB00USA,
G22/G30, DOY 220 primary. It creates no new gate, changes no hypothesis and
does not authorize access to either primary observation product.

## Physical boundary

    Physical question:
    Does the real four-link ionosphere-free continuous-phase coordinate prefer
    the frozen broadcast G22 geometry on the 60-epoch held-out suffix?

    New information produced by the future one-shot execution:
    Measurement validity, calibration detectability, and one prospective
    orbital-versus-null outcome below satellite identity.

    Why the existing qualification cannot answer it:
    DOY 217 contained no orbital model or score and was destroyed after
    model-blind capability qualification.

    Minimum experiment:
    Hash both complete DOY 220 products before decode, admit the exact
    139-epoch measurement, fit only constant plus rate on the fixed 77-epoch
    prefix, and score the untouched 60-epoch suffix against all frozen
    hypotheses once.

    Stop condition:
    One physical outcome, or one typed materialization/description halt. No
    retry, date substitution, window movement, threshold change or suffix
    refit.

## Frozen artifacts

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| GNSS_PHASE_SHORT_WINDOW_PRIMARY_PREDICTIONS.json | 22,303 | 1500fa3d6ddc5b3e1681631fca10df2f24a80bdfa5933f725e006cd07d7a81b3 |
| GNSS_PHASE_SHORT_WINDOW_PRIMARY_SEAL.json | 1,976 | 58802ab8f4dfcc0a2050bcf6c37b4d3b751b97d02a8efc28127340f0b45df62b |

The seal binds scorer source commit
548b7a28f3bc36904142ed2ceef259b121657429, source SHA-256
bbacf8653a74198941a6380640d43b5e7ffc7d46767039e84604db0de61793fc,
plan manifest 0068385e...b5f3c, the exact three DOY 217 qualification hashes,
dependency versions and the exact-hash DOY 220 broadcast NAV.

The prediction artifact contains model coordinates only. Its curve-set hash is
816e259786a70f47b1b6d8063e79a3a14bda3a0b630d3c161982e46c6957ddb6.
At creation it had zero observation discovery, headers, payload bytes and
values. Primary product byte counts and SHA-256 remain deliberately unknown.

## Numerical regression and decision rule

The exact frozen grid reproduces:

| Alternative | Held-out non-affine separation |
| --- | ---: |
| prefix-affine | 11,401.473007275607 m p-p |
| wrong orbit G01 | 8,857.431880665245 m p-p |
| wrong orbit G14 | 60,003.29156747623 m p-p |
| wrong orbit G17 | 122,006.60516244936 m p-p |

The orbital calibration-prefix residual must be no greater than
1192.1168692918313 m peak-to-peak. Otherwise the outcome is NOT_DETECTABLE
and the suffix comparison is NOT_EVALUATED.

If admitted, all five hypotheses receive the same coordinate, 77/60
partition and per-hypothesis prefix-only constant-plus-rate nuisance. A model
is preferred only if its held-out peak-to-peak residual beats the runner-up by
more than 2384.2337385836627 m. Free time phase, suffix refit,
interpolation and gap bridging are absent.

## Runtime boundary

The live surface requires all of:

- explicit --execute-live;
- authority token AUTHORIZE_DOY220_SHORT_WINDOW_PRIMARY_ONCE;
- the exact seal file;
- expected seal SHA-256 58802ab8...df62b;
- the exact prediction artifact.

The seal itself grants no authority. Transport is exactly one attempt per
predeclared locator. Complete compressed artifacts are hashed before any
decode. Compressed bytes, decoded RINEX and phase/code/SNR values have zero
persistence; only aggregate measurement-admission and score fields may enter
the outcome receipt.

## Remaining blocker

Only a separate, explicit authorization for the single DOY 220 primary
execution remains. Until then:

    primary products discovered = 0
    primary headers opened       = 0
    primary payload bytes        = 0
    primary values accessed      = 0
