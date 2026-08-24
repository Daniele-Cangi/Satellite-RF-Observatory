# Continuous-phase GNSS quotient mechanism spike

## Outcome

~~~text
PHASE_QUOTIENT_MECHANISM_DISCRIMINATIVE
~~~

This is a mechanism result on the already-closed G14/G17 geometry. It is not a
measurement outcome, does not reopen that candidate and does not select a new
primary.

## Physical question

Does preserving the continuous ionosphere-free carrier-phase double
difference retain more orbital-versus-null structure than deriving an
instantaneous frequency coordinate before applying the physical envelope?

New physical information: yes. With the same four links, same 77/307
calibration/held-out partition, same prefix-only affine nuisance, same G22
wrong-orbit null and same conservative per-link path intervals, the continuous
phase coordinate has a positive historical mechanism margin.

## Access boundary

- broadcast navigation: exact-hash DOY 220 artifact only;
- frozen geometry receipt: exact-hash input;
- observation products discovered or selected: zero;
- observation headers opened: zero;
- observation values or payload bytes accessed: zero;
- new candidate selected: false;
- prospective plan frozen: false;
- measurement authorized: false;
- new gate created: false.

G14/G17 remains HISTORICAL_DEVELOPMENT_ONLY_NEVER_PRIMARY. Its earlier
frequency-coordinate closure remains authoritative.

## Coordinate

The coordinate is the ionosphere-free carrier-derived range:

~~~text
2.54572778016316 * L1C_METERS
- 1.5457277801631601 * L2W_METERS
~~~

for the signed quotient:

~~~text
(GOLD_target - GOLD_reference) - (NLIB_target - NLIB_reference)
~~~

The weights sum to one and their first-order dispersive coefficient sums to
zero. No time derivative is applied.

Only a constant ambiguity and constant range rate are fitted on the first 77
epochs. The 307-epoch suffix receives no refit. The affine and G22 alternatives
receive the same coordinate, prefix, timing treatment and physical envelope.

## Historical-fixture discriminability

| Quantity | Value |
|---|---:|
| Prefix-affine held-out separation | 2,295,676.524764 m p-p |
| G22 held-out separation | 742,458.297490 m p-p |
| Controlling null | G22 |
| Controlling separation | 742,458.297490 m p-p |
| One-model physical envelope | 11,518.512516 m p-p |
| Pairwise comparison envelope | 23,037.025031 m p-p |
| Remaining historical mechanism margin | **719,421.272458 m** |

The controlling separation is 32.229 times the pairwise envelope and 96.897%
of it remains after the conservative subtraction.

This large value is not an RF result. It demonstrates that integrated orbital
curvature survives the fixed wrong-orbit comparison far more strongly than
the same geometry after numerical differentiation.

As a numerical regression, applying -L1/c times the central derivative to the
new range coordinate reconstructs the frozen frequency result at
403.375454029965 Hz. Its absolute difference from the old
403.375454029966 Hz value is 7.96e-13 Hz. Geometry, signs and target/null
identity are therefore unchanged; only the retained observable differs.

## Physical-envelope ledger

| Pairwise contribution | Treatment | Bound |
|---|---|---:|
| Station event time | direct trajectory at t +/- 15 s | 21,065.733903 m |
| Broadcast-orbit SV accuracy | four-link interval | 925.592302 m |
| Antenna PCV and phase wind-up | four-link interval | 231.398076 m |
| Multipath and signal-specific hardware | prefix admission interval | 231.398076 m |
| Satellite-clock retarded-time remainder | four-link interval | 231.398076 m |
| Station displacement, EOP and relativity | four-link interval | 231.398076 m |
| Higher-order ionosphere | four-link interval | 115.699038 m |
| Differential troposphere | direct mapped path family | 4.307762 m |
| RINEX phase quantization | format bound | 0.099723 m |

The event-time family contributes 91.443% of the one-model envelope even with
the deliberately coarse half-cadence bound. It still occupies only a small
fraction of the G22 separation. No term was removed, smoothed after the result
or combined probabilistically.

For an arbitrary per-link interval b, the phase coordinate first forms the
four-link amplitude bound 4b, then propagates it through the same
prefix-affine peak-to-peak operator. This avoids the finite-difference
amplification but does not silently assume temporal smoothness.

## Synthetic model-mismatch stress

A constant unmodeled line-of-sight acceleration of 0.00005 m/s^2, not generated
from the nominal orbit, was passed through the same prefix-only affine
projection. It leaves 2,643.84 m peak-to-peak in the held-out suffix. The
coordinate therefore does not collapse a plausible smooth trajectory mismatch
into its allowed constant/rate nuisance.

The test does not establish that this is the best alternative-orbit family.
The actual historical controlling physical alternative remains G22.

## Measurement bridge that is still missing

The positive result is conditional on a future measurement preserving one
continuous segment. Before a real plan can be frozen:

- L1C and L2W carrier phase must exist for all four links;
- any nonzero LLI on either phase breaks the segment;
- geometry-free phase continuity must independently witness cycle continuity;
- no interpolation or gap bridging is allowed;
- C1C and C2W are same-path admission/refusal witnesses, not phase
  corrections;
- code fields need not be present at every epoch unless a quantitative cadence
  rule is declared before the primary;
- S1C/S2W remain optional without coherent units and a quantitative rule;
- suffix witnesses may refuse health but may not tune the orbital score.

Thus MECHANISM_DISCRIMINATIVE is not yet
ORBITAL_SIGNATURE_DETECTABLE. Actual structural coverage and the measurement
envelope remain future admission questions.

## What changed conceptually

The double-difference topology survived. The assumption that its primary
observable must be instantaneous frequency did not.

The old path performed:

~~~text
continuous carrier phase -> central derivative -> frequency score
~~~

The surviving path is:

~~~text
continuous carrier phase
-> ionosphere-free four-link quotient
-> prefix ambiguity/rate removal
-> held-out phase evolution versus frozen nulls
~~~

This is the principal result of the spike: the project had enough modeled
orbital structure, but discarded much of its falsification power by
differentiating before using phase continuity.

## Verification

- 10 focused spike tests cover the phase-to-Doppler identity, prefix-only fit,
  ionosphere-free invariants, four-link interval propagation, witness
  semantics, synthetic mismatch, strict positive margin and JSON finiteness;
- 31 focused GNSS regressions pass across the spike and frozen pair/envelope
  mechanisms;
- the complete generic offline suite passes: 930 tests;
- sealed Cassini CI remains separately excluded because it requires its
  exact-hash external kernel environment.

## Next boundary

Do not inspect another observation artifact yet. The next minimum work is a
new, bounded, metadata-only orbit/station/signal/date declaration followed by
a phase-coordinate screen that ranks candidates by:

~~~text
min(prefix-affine separation, frozen wrong-orbit separation)
- pairwise phase physical envelope
- declared measurement envelope
~~~

G14/G17 may not enter that candidate set. Unknown terms make a candidate
unrankable, not zero. Only a positive newly selected geometry may proceed to
one independent qualification artifact and one later distinct primary.

The strict spike receipt has repository SHA-256
12a93c7f52799042d062747e322568d78d2197721ce05cb84c6214ed36a431e1
and contains 8,811 bytes.
