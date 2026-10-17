# Shared code/phase error structure from admitted references

## Executable intervention

The temporal covariance study transported a declared receiver fraction of .5,
but its disjoint-reference cross moments were negative or indefinite. This
increment fits and evaluates a **differential shared-component model** before
any such fraction can be interpreted as measured noise. It reuses the existing
reference preparation, GF segmentation and spatial least-squares contrasts.
It also constructs exact raw-covariance nonuniqueness witnesses and verifies
the different orbital effects of receiver-common and link-dependent blind
disturbances through reference recalibration and trajectory refitting.

This is development on the exposed archive. There is no new orbital estimate,
candidate RF/CODE score, floor adjustment, independent confirmation or S3
campaign. The new executable capability is conditional prediction across
reference groups, with an explicit admissibility check on the shared moment.
An unsupported component is retained as unsupported rather than assigned a
positive sharing fraction.

## Information and fitted model

For each original candidate fold, admit only its other reference identities
and reference times up to the last prepared target training endpoint. Candidate
products are excluded as text before numeric parsing by the existing boundary.
Candidate RF supports its original snapshot preparation but does not enter its
own reference-error fit. G12 orbit remains unopened.

Use z=[IF_code-IF_phase, MW] within the original GF segments. The modeled
nondispersive range and clock cancel, so no fitted reference-clock means or
historical candidate state are needed for this diagnostic. Existing admitted
code-bias corrections and reference geometry/masks are retained. The
[ESA code/carrier equations](https://gssc.esa.int/navipedia/index.php/Code-Carrier_Divergence_Effect)
support these cancellations; they do not turn z into pure code noise.
[Multipath can affect both code and phase and depend on direction](https://gssc.esa.int/navipedia/index.php?title=Multipath).
No attribution to multipath, antenna response or another physical mechanism is
made from a negative cross moment alone.

Retain four fixed identity-only reference partitions: alternating sorted SVs,
and three SHA-256 orderings with seeds `spatial-0`, `spatial-1`, `spatial-2`.
All partitions are kept, not selected by their outcomes. At both 30 and 300 s,
fit free reference-common changes and zero-mean receiver Helmert contrasts in
each group. A missing/disconnected graph stays unsupported without an anchor.
The first two thirds of reference time train the model; the last third only
evaluates frozen predictors. Both endpoints of a difference must be on its
own side of the split and in the same GF segment.

For the two receiver-contrast series a and b, subtract each spatial mode's
training mean. Pool the five spatial modes and supported epochs to estimate
Caa, Cbb and the symmetric cross moment S. Under the declared independent-link
model, a=u+ea and b=u+eb imply S=Cov(u). It is admissible for this fit only if
S, Caa-S and Cbb-S are PSD. If it fails, retain the original matrix and its
eigenvalues, reject its admission as a positive common covariance, and use the
independent boundary for that model's prediction. Negative eigenvalues are
never clipped into a positive physical variance. This is distinct from proving
that the true common process is absent. Finite-record moments need not be
valid variance components; see the
[NIST discussion](https://itl.nist.gov/div898/handbook/prc/section4/prc44.htm).

Three predictions for excluded b are compared on exactly common support:

1. Independent: its frozen training mean.
2. Positive common: mean_b+(a-mean_a) Caa^-1 S, if the common moment is admissible;
   otherwise the independent boundary, explicitly marked inadmissible.
3. Signed cross-group: mean_b+(a-mean_a) G, with an unrestricted 2x2 least-squares
   gain G learned only from training. This can represent anti-dependence and
   is not a raw physical covariance model.

Repeat in the reverse direction. Loss is mean squared prediction error divided
channelwise by the corresponding **training** split variance; no validation
scale refit occurs. Raw channel MSE and worsening-epoch counts are retained.
All folds' predictors precede these prediction-loss calculations. Candidate
RF/CODE scoring functions are never invoked.

Validation supplies the source group's RF at the same later epoch. This tests
conditional transfer to the other group; it is **not a forecast made without
future RF**. Support is conditional on the existing reference masks and GF
segmentation, not a nonlinear mask-blind holdout. Modes, folds, lags and
partitions overlap and are not independent trials.

As a stability diagnostic, delete each fixed 300 s training time block and
retain the resulting cross eigenvalues. These are sensitivity ranges, not
confidence intervals. The descriptive support label requires positive training
and validation cross eigenvalues, positive eigenvalues after every supported
block deletion, an admissible common moment, and better positive-model loss
in both directions. It is not a calibrated significance test or permission to
replace the raw covariance. Every physical-budget qualification flag remains
false even if this conditional differential-transfer label is supported.

## Raw code/phase identifiability

Let T map the four raw metre channels [P1,P2,phase1,phase2] to IF code, IF phase,
GF phase and MW. The observed contrasts have H=[T_IFcode-T_IFphase; T_MW], rank 2.
For a symmetric 4x4 raw increment covariance C, H C H^T supplies only three
moments for ten unknowns: **seven covariance directions remain unidentified**.
Even when code/phase cross blocks are assumed zero, six unknowns retain a
three-dimensional null space. This is an algebraic statement, not a sample
size problem that more precise measurements of the same z can solve.

Both 2x2 submatrices H_code and H_phase are invertible. For any PSD contrast
covariance V, code-only and phase-only laws obtained as H_block^-1 V H_block^-T
are PSD and produce exactly V, while their IF code/phase covariances differ.
The artifact retains a unit-V illustrative witness. It is not an estimate of
shared variance, an equal-noise assumption, or a plausible physical phase
amplitude inferred from this archive. External amplitude/spectral information
could distinguish these laws; z alone cannot.

The mean null vectors include the all-four-channel nondispersive direction
and the first-order ionospheric direction [1,k,-1,-k], k=(f1/f2)^2. Arbitrary
PSD covariance along either can be added without changing H C H^T. Adding
independent information on the IF-phase nondispersive residual and the GF
ionospheric residual would augment H to rank 4. The existing free epoch clocks
and free link-epoch ionosphere do not supply that information. Two additional
independent mean directions, or seven additional independent covariance
moments (three under the separated-block assumption), are the structural
requirements for the unrestricted raw problem. A second correlated GNSS product
is not automatically an independent constraint. No finite absolute uncertainty
or required metre precision can be deduced for the unobserved modes from z.

Identifying all ten raw terms is sufficient, not necessary, for an orbital
covariance. A null direction annihilated by the complete calibration/nuisance
response need not be bounded separately. The relevant missing budget concerns
the directions that survive that response; raw nonuniqueness alone does not
establish their orbital effect.

The synthetic end-to-end control distinguishes their effects. An equal raw
metre disturbance shared by each receiver's references and target is absorbed
by the recalibrated receiver clocks, recovering the original trajectory.
Conversely a link-dependent nondispersive perturbation equal to the RF change
of another central+J2 trajectory leaves D/MW/GF unchanged and produces that
other fitted trajectory: the example shifts initial position by 137.48 m and
velocity by 26.93 mm/s. This is a constructive degeneracy, not a measured error
or a second orbit found in the exposed data. It shows why a receiver-common
clock-like term must not automatically be given the same orbital effect as
an unshared direction-dependent range term.

## Execution and results

Numerical producer: `5614bb7638aebb8aa8c513f2a307c0d5c2ed205e`, based on merge
`845c7969f2d714c7a07112707a3cbe8bb984a6c5` (#230). Command:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python -m research.exploratory.reference_network_clocks --structure NEW_OUTPUT.json.gz
```

One complete execution retains all 22 candidates, 440 preparation windows and
63 prepared arcs. Five folds have reference contrasts (G05/G11/G19/G20/G21);
17 retain insufficient original orbital preparation and are not analyzed here.
That inherited pipeline terminal does not establish that their reference-error
structure is unidentifiable under another preparation.

Output: `results/shared_error_structure_v1.json.gz`, 1,737,609 bytes,
SHA-256 `73f1a463e51fb3abe7c53153d2204b95319334728c521dca316f37a28650585b`.
It retains the 25,117 admitted reference rows, all partitions, raw moments,
block deletions, gains, excluded predictions, losses and unavailable terminals.
Those rows overlap across folds and are not independent observations.

There are 40 planned comparisons: 38 evaluated and two unsupported, both
G19/hash_2. That partition's reference/station graph is disconnected at every
eligible epoch: 29 training/14 validation at 30 s, 20/5 at 300 s. No anchor or
replacement split repairs it. All 38 evaluated comparisons remain
`POSITIVE_SHARED_STRUCTURE_UNQUALIFIED`; none receives the descriptive positive
transfer label.

| Fold | Lag, s | Alternating train/validation epochs | Admissible training common moment / evaluated partitions | Positive transfer supported | Signed transfer improves both directions |
|---|---:|---:|---:|---:|---:|
| G05 | 30 | 77 / 38 | 0 / 4 | 0 / 4 | 2 / 4 |
| G05 | 300 | 68 / 29 | 0 / 4 | 0 / 4 | 0 / 4 |
| G11 | 30 | 77 / 38 | 0 / 4 | 0 / 4 | 1 / 4 |
| G11 | 300 | 68 / 29 | 1 / 4 | 0 / 4 | 0 / 4 |
| G19 | 30 | 29 / 14 | 0 / 3 | 0 / 3 | 0 / 3 |
| G19 | 300 | 20 / 5 | 1 / 3 | 0 / 3 | 1 / 3 |
| G20 | 30 | 77 / 38 | 0 / 4 | 0 / 4 | 1 / 4 |
| G20 | 300 | 68 / 29 | 0 / 4 | 0 / 4 | 0 / 4 |
| G21 | 30 | 61 / 30 | 0 / 4 | 0 / 4 | 1 / 4 |
| G21 | 300 | 52 / 21 | 3 / 4 | 0 / 4 | 0 / 4 |

At 30 s no evaluated partition supplies an admissible positive common moment.
The original alternating moments reproduce #230's negative eigenvalues.
Their smallest eigenvalue stays negative under **every** 300 s training-block
deletion in every fold. This establishes stability of that finite-record sign
under these deletions, not statistical proof that shared errors are absent.
The identity S=Cov((a+b)/2)-Cov((a-b)/2) shows that cross-group disagreement
power exceeds consensus power in a negative direction; it does not determine
whether the cause is link structure, cross-group dependence or sampling.

At 300 s five training moments are admissible: G11/hash_1, G19/hash_1, and
G21/alternating, hash_1, hash_2. Every corresponding validation cross moment is
non-PSD. Four also lose positive eigenvalues under training block deletions.
The important contrary cases are retained:

- **G21/alternating** has training eigenvalues .001286/.025263 m2, with its
  smallest eigenvalue remaining .000176 to .001704 m2 after block deletions.
  Validation eigenvalues are -.069510/-.002541 m2. Positive-model loss rises
  3.82% and 1.68% in the two directions despite that stable positive training
  moment. G21/hash_2 worsens 17.41% and 5.74%.
- **G19/hash_1** improves positive-model loss by .51% and 1.50% on its five
  validation epochs, but has a slightly negative validation eigenvalue
  (-.0000376 m2) and unstable training block deletions. This small, correlated
  record does not establish absence of a common process, but does not qualify
  this fitted covariance either. The lower loss is not used to select it.

Across the 76 evaluated directional predictions, the signed model improves
18 and worsens **58** versus independence. It improves both directions in only
6/38 comparisons. The positive model improves two and worsens eight directions;
the other 66 are the explicitly rejected moment's independent boundary, not
successful learned shared predictions. These correlated counts do not measure
population false-positive rates. Directional scores, raw channel MSE and
worsening-epoch denominators remain in the artifact.

## Orbital effect, verification and next step

No fitted shared raw law is admitted from these results. Accordingly there is
no new candidate trajectory, position/velocity accuracy claim, orbital
covariance or genuinely future candidate-RF forecast. #230's four conditional
covariance scenarios and its 126 state comparisons/five future epochs remain
unchanged. In particular its roughly 29% formal-axis reduction under f=.5 is
still an unqualified sensitivity, and no future joint state was included in
its nominal 95% ellipsoid. An unsuccessful reference prediction is not used to
inflate or retune historical floors. The new excluded predictions above are
reference-group conditional predictions with later source RF supplied.

The 20 producer-focused tests pass, including raw PSD nonuniqueness, positive
and anti-correlated generators, excluded-value poisoning, disconnected spatial
support, calibration-plus-orbit blind disturbances, scoring order and historical
temporal/covariance receipts. The added result test binds artifact/input/source
bytes to the producer, replays every predictor and score, and preserves all
candidate/window terminals. Final-head CI and Codex review are recorded in the
focused PR. Historical source bytes and receipts are not rewritten.

This increment supplies an executable shared-component fit, rejects unsupported
variance admission, and tests its transfer beyond training; it does not close
S2. The next useful source of information is the **nondispersive link component
that survives reference calibration**, rather than another choice of f. With
the existing admitted reference geometry, time-differenced receiver/reference
network closure contrasts can cancel free clocks and constant phase biases.
Their response to reference orbit/propagation errors and link-specific
disturbances must be separated, with excluded-link/time validation and full
calibration-to-state response, before assigning a finite orbital budget.
Absolute common modes still require independent range/clock/ionosphere support
where they survive that response. Additional precision in D/MW alone cannot
observe their exact null directions. G12 remains unopened and S3 is not started.
