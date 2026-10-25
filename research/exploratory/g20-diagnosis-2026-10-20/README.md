# G20: distinguish a failed correction from missing physical information

This diagnoses one named failure on the already exposed RF archive: the fixed
observed-coordinate residual model increased G20's 300 s phase-increment RMS
from **14.692259 to 15.406601 mm**, on the same **261** original comparison pairs.
The original MissNet-inspired outcome remains negative and unchanged. No new
correction, fitted gain, rank, source search or paid model call is introduced.
Satellite is an unusually demanding stress case; this diagnostic does not measure
Missing Link's general usefulness or establish a practical blocked-agent rescue.

RepoTraction #132 and Satellite #238 were merged only after clean current-head
reviews, resolved threads and successful Windows/Linux CI. Their merge commits
are `c11732df6ed12bd299352ec5fb80c418a563f9e6` and
`49d2a8fcae0da6b65b3f62b22565211e3be6a9fa`. The new diagnosis starts from the latter.

## 1. The correction is not just too large

Let `e` be the original error (observation minus baseline prediction) and `c` the
added prediction correction. The corrected error is `e-c`. Reusing all 261
conserved G20 pairs gives:

| Quantity | Value |
| --- | ---: |
| Correction RMS | 3.049310 mm |
| Mean `e*c` | -6.101298 mm² |
| Mean `c*c` | 9.298294 mm² |
| Increase in mean squared error | 21.500889 mm² |
| Pairs with worse absolute error | 139/261 |

The identity `MSE(e-a*c)-MSE(e) = a² E[c²] - 2a E[e*c]` shows that **every positive
scale of this same correction worsens pooled MSE on these exposed pairs**. This
is a signed projection result, not a centered-correlation claim, statistical
significance, or an instruction to fit another gain from held scores. No gain was
selected. Shrinking a positive correction alone does not resolve this failure.
The cause of its wrong projected direction still requires separate diagnosis.

## 2. The learned training residual is not the missing-link prediction error

The prototype fits its latent model to residuals at observations that also helped
fit the native calibration. In a fixed linearization these are `r=(I-H)y`.
A missing-link error instead has the form `e_hidden=y_hidden-K_mask*y_admitted`.
Masking changes the fitted network, not just which latent coordinates are read.
These objects are not interchangeable supervision without additional justification.

A bounded diagnostic uses the **last prefix epoch (38310 s)** and exactly
**300 s earlier (38010 s)**, all original hash-selected links, with no time/link
replacement. The true future held rows remain excluded from every new fit.
Three native wet fits are used: original admitted data, a fixed numerical input
intervention, and removal of the selected prefix rows. All still use admitted
other-link RF at later epochs: prefix describes the contrasted rows, not a
causal prefix-only calibration or whole-network future forecast. This is a diagnostic on
training-prefix data, not a replacement forecast model or independent validation.

All **14** selected link identities remain visible: ten have a comparable pair,
three lack a comparable/continuous prefix pair, and one loses an observable clock.
There are 22 removed prefix observations. On the ten comparable links:

| Prefix quantity | RMS |
| --- | ---: |
| Residual increments when the observations helped fit calibration | 7.346326 mm |
| Prediction errors after excluding those observations | 11.427947 mm |

This single prefix contrast does not estimate a generalization distribution or
prove the cause of every future error. It demonstrates that the implementation
has not trained on the same error object it later attempts to correct.

A fixed intervention adds +10 mm to IF code and phase at the later endpoint and
-10 mm at the earlier endpoint on the selected rows; GF/MW stay unchanged. It is
a numerical nondispersive input probe, not a measured physical disturbance.
The injected increment is 20 mm. After refitting, the observed training-residual
increment changes by only **6.863–15.661 mm**, median **9.696 mm**, on these ten links.
The calibration absorbs the rest. If those rows are excluded, the admitted inputs
are unchanged by that intervention: the missing-link prediction stays unchanged
and its error changes by 20 mm. The latter is an **analytic consequence of removal**,
not a second measured masked refit. The observed attenuation is measured by refit.

This establishes a software/methodological mismatch worth correcting or rejecting:
learn corrections from genuinely excluded prediction errors (or a properly derived
leverage/covariance transformation), rather than assuming post-fit residuals have
the same distribution. It does **not** demonstrate that correcting the mismatch
will improve future RF predictions; temporal stability and the rank-one residual
hypothesis remain unproven. It is a method-design gap, not a claim that the code
failed to execute its declared algorithm.

## 3. Where information really disappears

For the counterfactual DRAO00CAN/G31 pair, masking leaves DRAO observed but removes
every G31 reference link at both selected epochs. Under the native free-epoch
reference-clock model its clock is not observed. The existing code correctly
returns `UNOBSERVED_NETWORK_CLOCK`; the case remains unknown. Recovery needs an
additional admitted observation or a justified temporal/physical clock assumption.
A new implementation alone cannot identify an unrestricted missing clock.
This is a separate prefix-mask case, not the explanation for all 261 evaluated
future increments, which retained prediction support.

Conversely, source-coefficient aliases must not be confused with an unobservable
predicted increment. Reusing the full source model on admitted G20 data gives
197 source coordinates, numerical rank 129 and 68 unresolved directions. The
**complete** 300 s phase-increment map includes the direct source path, clock refit
and prefix ambiguity refit. On all original 261 keys its maximum unresolved-source
response is **5.1694e-9 metres per metre of total source-coordinate norm**, at the
existing declared rank tolerance. Native prediction replay agrees to 2.8784e-12 m.
Thus resolving every source alias is not algebraically necessary for these outputs
at that numerical resolution. This is conditional linearized information, not
proof of unlimited-amplitude physical uniqueness or accurate prediction.

The retained source-component gain from a unit whitened/profiled training error
to the phase increment ranges from **0.00505 to 0.94757 m**, median **0.01169 m**.
This identifies weak, amplification-prone directions; it is not the complete
forecast covariance, a measured noise amplitude or a qualified uncertainty bound.
The original weighting scenario assumes IF phase endpoint sigma 20 mm and independent
unobserved-endpoint difference sigma 28.284 mm. Those are weighting assumptions,
not an experimentally established irreducible floor. The observed 14.692 mm RMS
cannot establish the physical covariance or prove that further improvement is
impossible; overlapping increments also prevent naive independent-sample inference.

## Operational conclusion and the next Missing Link question

For this evaluated G20 correction, the evidence supports a concrete software-side
learning-target mismatch and rejects mere positive-gain tuning. It does **not**
establish that new physical measurements are required to improve its conditional
forecast. Separately, the erased-G31 example is structurally unsupported under the
current model, and physical uncertainty/source qualification still lacks justified
noise/source information. This is not a single binary diagnosis of all Satellite.

The narrow operation to consider next is:

> Given a weighted inverse calibration, changing observation masks and continuity
> constraints, construct training errors for genuinely unobserved predictions;
> preserve estimability checks, represent unavailable outputs explicitly, and
> evaluate a correction against the unchanged direct baseline.

Before external retrieval, note that Satellite already has the direct building
blocks: `network_clocks.fit`, `phase_continuity.withheld_segment` and
`source_geometry.source_link_prediction`. The counterfactual diagnostic uses those
existing operations. The minimum direct alternative is to construct mask-consistent
prefix errors with them; whether a useful correction can be learned remains open.
Missing Link should compare against that alternative before selecting an external
source. Another generic missing-data filter does not address the diagnosed gap.
If external search is later warranted, its contract should concern prediction-error
learning under a changing inverse observation operator, not RF vocabulary alone.
No retrieval or new correction experiment was started in this diagnosis.

## Reproduction and limits

Run `python -m research.exploratory.g20_prediction_diagnosis` from the repository
with a new `data/g20-prediction-diagnosis.json` output path available. It reads the
preserved stable RF and #238 score artifacts. `diagnosis.json` includes exact input,
score and executed-source hashes, all prefix terminals, correction decomposition,
source-map information and timing (12.467 s). Executed diagnostic revision is
`da70f92e38312044e18656440af57c54063e1e84`. No historical bytes or production paths
were changed, and no candidate orbital state/CODE fit or new G12 analysis occurred.

The initial driver revision `b893664` failed at startup because a loop variable
shadowed the timer module, before reading the archive or producing numerical
outcomes. Its traceback is retained in `initial-startup-failure.txt`; the name was
corrected and an entrypoint/input-guard regression added before successful execution.
This was an engineering correction, not a changed model or scientific retry.

Eleven focused tests pass: new signed-MSE, missing-key and entrypoint/input-guard
checks plus existing native source-separation and network-closure regressions
(see `focused-tests.xml`). Full Windows/Linux CI and review apply before
integration. This remains exposed-case diagnosis, not prospective confirmation,
proof of a new useful software connection or a reason to abandon Missing Link.
