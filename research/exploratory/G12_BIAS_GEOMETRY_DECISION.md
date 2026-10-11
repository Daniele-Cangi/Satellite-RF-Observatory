# G12: changing geometry and the remaining absolute-bias requirement

Exploratory decision of 12 October 2026, on already exposed observations.
The interval solver, historical fits, masks, floors, thresholds and closed
outcomes are unchanged. No target orbit/clock or oracle-error report is read.
This answers whether the present observations supply the missing bias information,
before implementing another inverse estimator.

**Decision:** time-varying geometry does add local information if station biases
are tied across arcs. It does not yet supply a defensible physical constraint:
the information remains very weak, the bias-stability assumption is unqualified,
and the historical covariance omits shared temporal/systematic dependencies.
S2 remains open. There is a concrete extension using the existing exposed hour;
there is no reason to start S3 or change an acceptance threshold now.

## Coverage comes before a longer trajectory

The retained G12 extract has 30 s samples on 2026-09-05, GPST 10:00â€“11:00.

| Station | Available code/phase rows | Exposed time coverage | Interpretation |
|---|---:|---|---|
| ALGO, DRAO, AREQ, BOGT | 121 each | 10:00â€“11:00 | Four common receiver paths |
| STJO | 72 | 10:00â€“10:35:30 | Its later tested RF elevations fail the original 10 degree mask |
| BRAZ | 61 | 10:30â€“11:00 | Completes the current five-station cohort |
| YELL | 0 | Unsupported | Existing event/header limitation retained |

Five receiver records are structurally available at every one of the 121 tags,
using STJO early and BRAZ late. This is **not geometric or model admission**.
The current five-station selection has just 61 common tags, 10:30â€“11:00.
Its twenty original non-overlapping arcs fit three endpoints over 60 s and
withhold the next endpoint. All twenty code fits remain accepted; fifteen phase
fits remain rejected and five accepted. Accepted phase endpoints span 1,350 s;
all code endpoints span 1,710 s.

The reference-phase clock report supplies only the second-half-hour increments.
A first-half-hour extension must derive its own reference-only drift inputs from
the already retained observations/products, and check phase continuity and
RF-derived elevations. Neither structural presence nor nominal daily RINEX file
coverage supplies that qualification. Longer times outside the exposed hour need
additional extraction/calibration; this result makes no availability claim about
their target measurements.

## Information measured without another bias fit

At each accepted historical fit, replay the unchanged interval solver and check
state, status and covariance hash against its RF report. Let `A` be its complete
state/receiver-clock/ground Jacobian, and `B` the four orthonormal, zero-mean
station code-bias contrasts. `B` is zero for carrier increments and calibration
rows. A common station offset is retained as a satellite-clock gauge, not an
absolute time observation.

Whiten with the original covariance. Complete QR of `A` gives an orthogonal
complement `Q_perp`; the bias-only profile is `R = Q_perp.T @ B_whitened`.
Thus all arc-local nuisance parameters are eliminated without subtracting nearly
equal normal matrices. Stack these profiles for a shared bias across arcs;
**do not** force a 60 s quadratic trajectory to describe half an hour.

| Admitted historical subset | Shared constant bias contrasts | Weakest profile singular value, per m | Formal weakest-contrast scale, m |
|---|---:|---:|---:|
| Code only, 20 arcs | 4/4 | 2.8503e-6 | 350,846 |
| Code + phase, 5 arcs | 4/4 | 6.2037e-5 | 16,119 |

The scale is `1 / smallest_singular_value`, under the old **conditional** weights
and block-independent arcs. It is not a measured station bias, a position-error
radius or physical confidence coverage; such large perturbations are outside a
validated local linear neighborhood. Sharing reference products/clocks can change
the information and must not be counted as independent repeated measurements.

This profile rank concerns four bias columns after nuisance elimination. It is
not the historical 38/40 or 39/40 scaled full-model rank. We retain those original
ranks and the 1e-10 relative rule separately. A formally nonzero profile direction
does not mean useful practical identifiability or contradict the short-arc result.

Halving/doubling the derivative step at the same fitted points gives a code-only
constant-bias scale of 350,865â€“350,888 m and phase scale of 16,148â€“16,248 m.
The weak-information conclusion is numerically stable; no step is chosen to
obtain a preferred outcome. Allowing a shared linear bias drift, including its
variation **inside** each short arc, gives 8/8 profile dimensions but scales of
14,565,427 m for code only and 16,822 m for phase. These remain conditional
comparison scenarios, not calibrated drift bounds.

## Which physical information is missing

For the shared constant-bias phase design, the weak direction has approximately
this station pattern, normalized to maximum absolute amplitude one:

```text
ALGO        DRAO        BRAZ       AREQ       BOGT
+0.01       -1.00       +0.48      +0.15      +0.36
```

The complete directions are in the JSON. This is a differential station pattern,
not an observation that DRAO is faulty. The earlier single-arc study gives
approximately 10 m position motion per hypothetical 1 m maximum station contrast
along this near-null mode. Its ~70 m omitted-one-station response describes a
different question: fitting with bias fixed to zero. Neither assigns a physical
bias amplitude.

A useful independent constraint must observe a scalar `h.T @ b` with nonzero
projection on this weak direction, in the **same effective ionosphere-free code
and clock convention**. A common clock datum has zero projection and cannot
help. One scalar suffices algebraically to remove the single short-arc near-null
dimension; other ill-conditioned directions and all error sources still need
coverage before an uncertainty claim.

Existing information does not yet provide such an absolute constraint:

- Carrier increments remove the constant ambiguity and constant code level.
  They add motion information but cannot anchor that level by themselves.
- Over the common half-hour, target code-minus-carrier variation spans
  5.745 m (ALGO), 5.499 m (DRAO), 2.691 m (BRAZ), 1.561 m (AREQ), and
  2.337 m (BOGT). These observed combinations cancel the common range/clock
  terms, but mix code/phase errors and retain an unknown phase ambiguity.
  They neither measure the absolute code offset nor establish its constancy;
  unflagged phase discontinuities remain possible.
- The retained CODE bias extract has 66 **reference-satellite** OSBs and no
  receiver/target bias constraint. It translates reference signal conventions;
  it does not calibrate the effective target-minus-reference station error.
  The [Bias-SINEX specification](https://files.igs.org/pub/data/format/sinex_bias_100.pdf)
  supports several bias types, including differential biases; a product's label
  alone does not establish an absolute range anchor or compatible clock datum.
- Small reference residuals or a receiver DCB alone do not bound a bias common
  to the relevant code combination, target-dependent propagation/multipath,
  or error imported through the reference clock calibration. Previously exposed
  [reference-only transfer](PSEUDOTARGET_REFERENCE.md) was mixed, not a qualified
  target-direction bound. A target orbit/clock-derived correction would defeat
  the independence claim.

## Next attempt and the fallback measurement

**Next use existing data:** evaluate the full exposed hour with the four common
stations and the changing STJO/BRAZ paths. Keep missing paths and RF elevation
failures explicit. Derive reference-only first-half clock increments with the
existing primitives; do not import the target orbit. Use a trajectory/phase
continuity design that is physically valid over its declared interval, or
piecewise short arcs with justified connections. Compare constant and changing
bias modes, test observability/stability, and retain excluded RF predictions.
Sharing biases is a physical assumption to test, not a free numerical prior.
The current inventory supports trying this design; it does not certify its result.

**If geometry remains weak:** obtain an independent measurement or bound of the
weak differential **effective** code-bias projection. This requires reference-only
calibration with compatible signals and demonstrated transfer to the target's
viewing conditions, or an independently calibrated absolute range/clock-and-delay
observation with that same convention. A hardware receiver-bias value without
its clock datum, direction-dependent error and calibration dependencies is
insufficient. Required precision follows from the allowed position-error budget
and the measured response to this projection; it cannot be picked from residual
RMS or from the already revealed target orbit error.

This identifies what additional measurement must contain and why it is useful.
It does not assume such calibration is presently obtainable without instruments.
A reference-only calibration built from open data is worth testing before buying
hardware, but its failure must remain an admissible scientific conclusion.

## Reproduction and retained evidence

Use Python 3.13 and `requirements-positioning.txt`, from repository root:

```console
python -m research.exploratory.g12_bias_geometry NEW_REPORT.json
python -m pytest research/exploratory/tests/test_g12_bias_geometry.py -q
```

[Machine-readable result](results/g12_bias_geometry_v1.json) retains coverage,
all forty model outcomes, twenty code/five phase profiles, constant/drift designs,
derivative-step variants, actual code-minus-phase changes and input/source hashes.
The original [interval report](REAL_TARGET_INTERVAL.md) and
[bias report](REAL_TARGET_BIAS_IDENTIFIABILITY.md) remain unchanged. The new
analysis uses existing parsing, fitting, covariance and linear algebra; no new
seal, checked wrapper or authority mechanism is introduced.

A Windows checkout converted the access JSON's original LF bytes to CRLF.
The original Git blob matches the historical input hash. Restore those exact
bytes and pin `-text` for this file; neither its contents nor the expected hash
changes. The regression checks the original access-to-input binding on both CI
platforms.
