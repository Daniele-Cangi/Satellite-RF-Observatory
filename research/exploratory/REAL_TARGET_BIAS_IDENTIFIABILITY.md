# Absolute code-bias information on the real G12 geometry

The [real-target interval study](REAL_TARGET_INTERVAL.md) found a phase benefit
for some withheld RF paths but no defensible total position envelope. This
follow-up tests the **dominant state-error mode**, using exactly the exposed
G12 RF inputs, stations, windows and frozen fits. It does not access the G12
orbit or its already revealed oracle errors. No new observation or confirmation
is opened.

At each of the three fit endpoints, add one hypothetical constant code offset
per station. Its column is +1 for that station's code and zero for carrier
increments: differencing removes any constant phase/code level. A common
offset over all five stations is a gauge with the fitted satellite clock, so
the analysis uses four orthonormal **zero-mean station contrasts**. These are
free nuisance parameters, without a prior or assigned physical amplitude.
The active interval solver is rerun and its state, status and covariance hash
must reproduce the frozen RF report before its data gain and Jacobian are
used. The existing relative singular-value rank rule, `1e-10`, is retained.

| Exposed real-RF fit | Arcs analyzed | Rank after four free bias contrasts | Nearly unconstrained contrasts |
|---|---:|---:|---:|
| Code only | 20 | 38/40 on every arc | 2 |
| Code + phase, conditionally accepted | 5 | 39/40 on every arc | 1 |

The fifteen phase fits rejected by their original residual test remain
rejected and are not used to claim recovered information. Phase contributes
one local dimension, but leaves another weak direction mixing station bias
and position. Its smallest singular value is only 5.9–6.6×10⁻¹¹ of the
largest across those five fits, below the solver's 10⁻¹⁰ rank cutoff.
Normalizing each near-null vector to a maximum 1 m station
bias contrast, the code-only directions move the fitted position about
17.4–24.9 m and 9.1–10.8 m respectively. The surviving phase direction moves
it about 10.0–10.5 m. These figures describe the **local Jacobian**, not an
observed bias or a physical error bound.

If the original fit omits a +1 m constant code error at one station, the
linearized position response is 70.27–76.75 m over the twenty code fits.
Across the five accepted phase fits it remains 69.58–74.88 m. These are unit
sensitivities, not claims that a real station has 1 m of bias. A formal
position variance with completely free bias contrasts is intentionally not
reported when the augmented design fails the existing rank criterion.

This resolves the decision from the prior report: **phase increments add
motion information but do not make the present short-arc, five-station
absolute-range solution self-calibrating.** Tightening a phase residual or
retuning weights cannot assign a credible amplitude to the surviving bias
mode. S2's next physical route must either obtain an independent station/code
bias constraint or use a longer, physically justified trajectory and changing
geometry that makes the contrasts identifiable and tests that model's own
error. A prospective S3 campaign should wait for a positive total-error
margin. The website may expose an explicit unqualified result, not a position
accuracy guarantee from these local numbers.

The numerical result is in
`results/real_target_bias_identifiability_v1.json`, including all twenty
arcs, the five accepted phase cases, rank ratios, near-null bias patterns and
unit responses. Replay from repository root:

```powershell
python -m research.exploratory.real_target_bias_identifiability research/exploratory/results/real_target_bias_identifiability_v1.json
```
