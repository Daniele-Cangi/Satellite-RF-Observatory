# GNSS short-window held-out primary outcome

Terminal outcome:

    ORBITAL_MODEL_PREDICTIVELY_PREFERRED

This is the single authorized DOY 220 execution of the previously sealed
GOLD00USA/NLIB00USA G22/G30 experiment. There was one attempt per predeclared
product, no retry, no substitute date, no window movement and no post-outcome
change to coordinate, null, nuisance or threshold.

## Physical result

The measurement path was valid. Both stations supplied the complete
139-epoch raw window on the exact 30-second GPS grid. L1C and L2W were present
with zero or blank LLI on all four station-satellite links. Every C1C/C2W
same-path witness had 100% presence and all required partition indices.

The worst geometry-free phase second difference was
0.008667878806591034 m, below the frozen 0.09514683639918244 m limit.

The orbital model also passed calibration admission:

| Clause | Result | Frozen boundary |
| --- | ---: | ---: |
| orbital calibration residual | 0.3672753512726934 m p-p | at most 1192.1168692918313 m |
| orbital held-out residual | 2.312586041483124 m p-p | scored, not fitted |
| runner-up G01 residual | 8858.964270285564 m p-p | scored identically |
| observed preference margin | 8856.65168424408 m | greater than 2384.2337385836627 m |

The held-out suffix therefore prefers the frozen broadcast G22-relative-G30
geometry over every predeclared alternative. G01 is the runner-up;
prefix-affine, G14 and G17 are farther away.

Only a constant and rate were fitted separately for each hypothesis on the
fixed 77-epoch prefix. The 60-epoch suffix did not fit a nuisance, select a
model, change a threshold or receive a free time phase.

## Artifact lineage

| Station | Complete bytes | SHA-256 | Attempts |
| --- | ---: | --- | ---: |
| GOLD00USA | 2,182,238 | b1763eb485311c0fd3a073f7b9b0beda3c9af8f8f9f7be4c868a56fdeb5b7e3d | 1 |
| NLIB00USA | 2,523,817 | 48d80ce59776fa6b10024a8cf5456153f1c1fd9906d1a4acfc84053799d40b3f | 1 |

Both complete compressed artifacts were hashed before decoding. They existed
only in RAM and were erased after the outcome. Decoded RINEX and phase values
also had zero persistence.

The strict aggregate outcome receipt is
GNSS_PHASE_SHORT_WINDOW_PRIMARY_OUTCOME.json:

- bytes: 9,799;
- SHA-256:
  66adf39fa1b10cbf43bdb712ebf4d1f3d8f598203caaa8fa2a41601fea511f9d;
- seal SHA-256:
  58802ab8f4dfcc0a2050bcf6c37b4d3b751b97d02a8efc28127340f0b45df62b;
- scorer source commit:
  548b7a28f3bc36904142ed2ceef259b121657429.

The receipt contains no raw coordinate, phase cycles, model-curve arrays,
code values, SNR values, NaN or Infinity.

## Claim boundary

Authorized:

> For this frozen GOLD00USA/NLIB00USA, G22/G30, DOY 220 experiment, the real
> held-out ionosphere-free carrier-phase coordinate predictively prefers the
> broadcast G22-relative-G30 orbital geometry over the frozen prefix-affine
> and G01/G14/G17 alternatives by more than the predeclared guard.

Not authorized:

- catalog-wide uniqueness;
- general GPS satellite identity from RF alone;
- a claim about arbitrary station pairs or dates;
- repeated-pass consistency;
- held-out confirmation by a third station;
- unconstrained orbit reconstruction.

This reaches MEASUREMENT_VALID, ORBITAL_SIGNATURE_DETECTABLE and
ORBITAL_MODEL_PREDICTIVELY_PREFERRED on the project claim ladder. It remains
explicitly below satellite identity.

## Stop

The primary is consumed. No second execution, retry or reserve exists. Any
future scientific work must begin from this frozen result and ask a genuinely
new physical question; it may not rescore this observation.
