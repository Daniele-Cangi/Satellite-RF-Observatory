# Post-G14/G17 SHOCK: choose the observable before another target

## Scope and information-gain test

This bounded change-of-abstraction review creates no gate, opens no
observation product, selects no primary and does not reopen GOLD/NLIB G14/G17.

~~~text
Physical question:
Which causal topology can preserve a held-out orbital-versus-null distinction
after the physical and measurement envelope, rather than only before it?

New information produced:
Whether the next experiment should change observer count, station geometry,
measurement coordinate or RF source family; and which mechanism can make a
negative result interpretable with the fewest uncontrolled assumptions.

Why the existing experiment cannot answer it:
The closed coordinate differentiates carrier phase into frequency and then
treats several path terms as arbitrary per-epoch intervals. Even perfect
orbit/clock knowledge leaves its pairwise envelope 6.110562 Hz above G22.

Minimum experiment:
An offline comparison of causal cancellations and envelope propagation. Test
the recommended mechanism first on synthetic and already-closed geometry.

Stop condition:
Do not discover or open an observation product until a newly declared
orbit/station/signal set has positive remaining physical margin under the
selected coordinate and every frozen null.
~~~

## Boundary inherited from the closed candidate

G14 versus G22 separates by 403.375454 Hz peak-to-peak. The pairwise envelope
is 733.754042 Hz. Substituting the official 0.006 m/s URRE sensitivity still
leaves -13.406593 Hz; the 0.02 m/s design sensitivity leaves -30.430664 Hz;
even zero orbit error leaves -6.110562 Hz.

These values are diagnostic boundaries, not parameters to reduce. G14/G17 DOY
220 is historical development material only. A successful new coordinate
cannot retroactively promote it to a primary.

## Route A — add a third GNSS station

**Physical question.** Does a vector of two independent station double
differences prefer the target orbit over a wrong-orbit family?

For stations A, B and C, retain [DD(A,B), DD(A,C)] and score the vector after
the same prefix-only nuisance projection. The third station provides a strong
held-out spatial consistency check.

It does not, however, cancel station-local multipath, antenna, troposphere or
signal-specific hardware. Under a non-probabilistic worst-case combination it
adds another local error family; sample count alone does not shrink an
interval. This is valuable for later held-out-station confirmation, but is not
the smallest repair of the present negative margin.

Maximum claim: spatial orbital consistency across three independent roots,
only if each component and the joint statistic have positive premeasurement
margins. Majority agreement is not an uncertainty bound.

## Route B — phase-continuous, multi-frequency witnessed quotient

**Physical question.** Does a frozen orbit predict the held-out evolution of
continuous, ionosphere-controlled carrier phase better than an affine
kinematic null and frozen wrong orbits?

Keep the dual-station, target-minus-reference quotient in continuous carrier
phase/range units. Form a predeclared multi-frequency combination whose
weights preserve nondispersive geometry and cancel the declared dispersive
order. Fit only the prefix offset and rate required for integer ambiguity and
oscillator drift; never refit the suffix.

For carrier-derived ranges P_k at frequencies f_k, first-order cancellation
requires:

~~~text
sum(w_k) = 1
sum(w_k / f_k^2) = 0
~~~

A third frequency may support another declared dispersive constraint, but it
is not required merely because it exists. Its noise and inter-frequency
hardware amplification must enter the envelope.

LLI on every core phase and geometry-free phase continuity break the segment
on a slip. Same-path code and independent geometry-free combinations can bound
or refuse non-affine ionosphere and path/hardware dynamics under rules frozen
before the primary. Signal strength remains optional without a quantitative
rule and coherent units. Missing witnesses produce NOT_DETECTABLE; they never
become zero-valued corrections.

This route avoids passing every path interval through a finite-difference
operator before scoring. Constant ambiguity is absorbed by the prefix offset,
bounded affine frequency error by the prefix rate, and slips are directly
witnessed. The integrated orbital signature survives. Every null receives the
same frequency combination, prefix fit, event-time treatment and missing-data
rules.

Orbit/clock, residual higher-order ionosphere, antenna/wind-up, troposphere,
event time and non-affine hardware remain explicit. Code noise cannot be used
as a precise phase correction. A suffix witness may only apply a predeclared
admission or refusal rule; it may not tune the orbital score.

Maximum claim: predictive preference of a known orbit over frozen nulls in one
continuous phase coordinate, not transmitter identity or unconstrained orbit
recovery.

This is the recommended mechanism.

## Route C — new geometry with the existing frequency-rate coordinate

**Physical question.** Does another bounded orbit/station geometry exceed the
unchanged frequency-rate envelope without changing its assumptions?

Better elevation, baseline orientation, lower direct time-shift gain and
larger wrong-orbit divergence may produce a positive margin. No current
nuisance cut changes, however. Ranking by raw orbital separation would repeat
the failure. The admissible statistic is:

~~~text
remaining margin = min(frozen null separations)
                   - pairwise physical envelope
                   - measurement envelope
~~~

Unknown terms make a candidate unrankable, not zero. A bounded predeclared
station set is sufficient; no global receiver inventory is needed. This is
the lowest-cost fallback, but it does not test whether the coordinate itself
causes the amplification.

## Route D — two-station SatNOGS forward raster validation

**Physical question.** Does a known pass predict a time-frequency ridge in two
independent station products better than frozen non-orbital tracks?

Independent geography couples the orbit to two real RF trajectories and could
reach a positive comparison quickly. Selection by satellite/transmitter is
model-conditioned, however. Waterfall binning, rasterization, cadence,
event-time semantics, clock and Doppler correction must be recovered per
product. A missing ridge is normally not interpretable without same-path
detectability witnesses.

Maximum claim: model-conditioned orbital forward consistency, not independent
identity evidence.

## Route E — Delta-DOR/VLBI angular observable

**Physical question.** Does spacecraft-versus-quasar differential delay follow
the predicted angular orbit on a held-out baseline?

The quasar is a strong same-path reference for clock, troposphere and much of
the propagation chain. The angular observable bypasses several terms that
closed the frequency routes. Public product access, pre-pass orbit lineage and
instrument covariance are uncertain, and an archival compiler is much more
expensive. The route has high scientific value but is not the shortest current
vertical.

## Comparison by falsification power

| Rank | Mechanism | Negative interpretability | New causal cuts | Roots | Cost/risk |
|---:|---|---|---|---:|---|
| 1 | Phase-continuous multi-frequency quotient | Potentially high | High | 2 | Low-medium |
| 2 | New geometry, unchanged frequency-rate coordinate | Medium if full margin is positive | None | 2 | Low, but may repeat failure |
| 3 | Delta-DOR/VLBI | Potentially very high | Very high | 2+ | High, archive-dependent |
| 4 | Two-station SatNOGS raster | Low for absence; useful for positive consistency | Medium | 2 | Medium, transform-dependent |
| 5 | Third GNSS station alone | Low under interval worst case | Low | 3 | Medium, adds local terms |

The ranking prioritizes the most interpretable negative with the fewest
uncontrolled assumptions, not implementation elegance, signal strength or
data volume.

## Recommended minimum vertical

The next bounded work is an offline phase-coordinate mechanism spike, not a
primary selection and not another qualification chain.

1. Define one continuous multi-frequency carrier-phase double difference and
   its exact units.
2. Freeze prefix-only ambiguity/rate nuisance and the same affine and
   wrong-orbit null families.
3. Propagate event-time, orbit/clock, media, antenna and quantization terms in
   phase units without silently replacing intervals by smooth processes.
4. Define LLI, geometry-free phase and same-path code as separate admission
   witnesses and state which physical cut each closes.
5. Use synthetic data and closed G14/G17 geometry only to test mechanism
   discriminability and algebraic boundedness. This is never candidate
   admission.
6. Only if it survives, predeclare a new bounded orbit/station/signal/date set
   and rank every candidate by full remaining physical margin before
   discovering observation products.
7. Select one qualification artifact and one later distinct primary only
   after that ranking is frozen.

Allowed mechanism outcomes are:

~~~text
PHASE_QUOTIENT_MECHANISM_DISCRIMINATIVE
PHASE_QUOTIENT_PHYSICAL_ENVELOPE_DOMINATES
PHASE_QUOTIENT_WITNESS_TOPOLOGY_INSUFFICIENT
~~~

Before a new candidate search, only the coordinate, fixed nuisance basis,
same-path witness rules and corresponding envelope may change. Do not alter
G0/G1, lower old bounds, reopen historical observations, add a catalog or
choose signals because an artifact is convenient.

If synthetic mismatch is not discriminative, or an UNRESOLVED family can
absorb every held-out separation, close this GNSS mechanism and move to the
physically distinct SatNOGS or Delta-DOR route. Do not repair it with more
infrastructure.

## Principal SHOCK

The likely bottleneck is not insufficient orbital Doppler. It is loss of
falsification power caused by deriving instantaneous frequency before using
the continuity and multi-frequency structure already present in carrier
phase. More receivers do not automatically create more information; a better
quotient can.
