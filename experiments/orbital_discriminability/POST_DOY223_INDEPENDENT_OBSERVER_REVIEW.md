# Post-DOY223 independent-observer review

## Scope

This is a bounded offline change-of-abstraction review. It creates no gate,
opens no observation product, discovers no locator and does not reopen or
rescore GOLD/NLIB, ALGO/MDO DOY219 or ALGO/MDO DOY223.

```text
Physical question:
Can the orbital structure already preferred on GOLD/NLIB predict a coordinate
on observer hardware and geography not used by that result?

New information produced:
Whether the repeated-pass preference transfers to a new observer rather than
remaining compatible with a systematic shared by GOLD/NLIB.

Why existing experiments cannot answer it:
DOY220 and DOY219 use the same station pair. ALGO/MDO qualified independently,
but neither frozen primary reached measurement admission or an orbital score.

Minimum experiment:
Derive and screen an observer-transfer phase coordinate offline. Only if its
complete physical envelope is positive may one new observer and one distinct
prospective artifact be selected.

Stop condition:
Stop without artifact discovery if a station-local unresolved term, a required
free rate, or the complete pairwise/null envelope can absorb the prediction.
```

## Authoritative evidence boundary

The current claim has two real components:

- GOLD/NLIB DOY220: `ORBITAL_MODEL_PREDICTIVELY_PREFERRED`, orbital held-out
  residual `2.312586 m` versus `8,858.964270 m` for runner-up G01;
- GOLD/NLIB DOY219: `ORBITAL_MODEL_REPEATED_PASS_PREFERRED`, orbital held-out
  residual `2.268796 m` versus `8,988.224632 m` for runner-up G01.

This establishes repeated-pass consistency for one station pair. It does not
separate orbital structure from all station-pair-specific systematics.

ALGO/MDO DOY217 independently demonstrated the required L1C/L2W, LLI,
C1C/C2W and geometry-free health path. Its DOY219 primary stopped at transport
materialization; its DOY223 primary stopped at ALGO Hatanaka decode. Those
outcomes say nothing about orbital preference on ALGO/MDO.

## Block attribution

```text
BLOCK:
Independent-observer confirmation has not produced a measurement-valid
coordinate. The latest failure occurred before physical admission.

INFORMATION VALUE:
We learned that a distinct pair can qualify on one date, but the selected
archive path did not reliably deliver a decodable later primary under the
frozen one-shot contract.

CURRENT ABSTRACTION:
Two entirely new stations are sufficient for independence, but not logically
necessary for the next claim-ladder step. Repairing CDDIS/Hatanaka is also not
part of the orbital hypothesis.

ACTION:
Abandon both consumed ALGO/MDO primaries. Compare observer-transfer mechanisms
offline before choosing another capability.
```

## Route A — wholly disjoint station pair

Retain the demonstrated two-station, two-satellite ionosphere-free continuous
phase double difference, but use two roots disjoint from GOLD/NLIB.

This is the cleanest replication topology: every measurement root changes
while the orbital coordinate and nulls remain recognizable. The existing
bounded six-station screen already shows multiple positive geometries, so raw
geometric separation is not the problem.

Its weakness is experimental cost. It needs two new structurally valid
products, four continuous phase links and another date-separated qualification
before a primary. Selecting another pair solely because its archive transport
looks convenient would reverse the satellite-first order. Reusing ALGO/MDO or
either consumed date is forbidden.

Maximum claim: independent-pair orbital-model preference. A negative is useful
only after all four links and the complete physical envelope pass admission.

## Route B — held-out observer transfer

Use two development/calibration observers A and B to discriminate or freeze a
candidate orbital family, then predict a target-minus-reference continuous
phase coordinate at a third observer C that was not used in that inference.

For ionosphere-free carrier phase in range units, define:

```text
Q_C(t) = IF_phase(C, G22, t) - IF_phase(C, G30, t)
Z_C(t) = Q_C(t) - Q_C(t_anchor)
```

The same fixed anchor operation is applied to the target orbit, every wrong
orbit and every non-orbital null. It removes one constant ambiguity; it is not
a fitted time phase. No suffix sample may choose the anchor, fit a rate, alter
the signal pair or select the model.

The receiver clock is common to the simultaneous same-station satellite
difference. First-order ionosphere is controlled by the frozen multi-frequency
combination. Satellite clocks, differential troposphere, higher-order
ionosphere, phase wind-up, antenna effects, multipath/hardware, event-time and
orbit/EOP terms remain explicit and must be projected through the same anchor
operator.

This route tests exactly the missing causal edge with one new observer product
instead of two. It also puts one inherited abstraction at risk: a universal
two-new-station requirement may be unnecessary once the discovery pair and the
confirmation observer have different roles.

The route is not yet admitted. An offline spike must prove that no free rate is
needed and that the complete held-out separation remains positive after every
station-C term. If a free rate or an unresolved non-affine term can absorb the
curve, the correct outcome is `OBSERVER_TRANSFER_ENVELOPE_INSUFFICIENT`.

Maximum claim: `HELD_OUT_STATION_CONFIRMED` for one frozen orbit/signal/window,
not independent identity or orbit recovery.

## Route C — one-new-root cross baseline

Construct the existing double difference on GOLD/C or NLIB/C. This changes one
observer while retaining one proven reference root. It is cheaper than Route A
and retains the strong common coordinate, but the old station remains in the
measurement equation.

It can expose whether the signal follows new geography and can localize some
pair-specific systematics, but it cannot authorize a wholly independent-root
replication. Agreement on both GOLD/C and NLIB/C would be stronger, yet the two
coordinates share C and correlated terms must not be counted twice.

Maximum claim: spatial transfer with one new root. This is a useful fallback if
Route B is not algebraically detectable, not a substitute for full root
independence.

## Route D — two-station SatNOGS forward validation

Compare known-orbit Doppler ridges at two independent SatNOGS stations using
frozen raster resolution, cadence, event-time and ridge uncertainty.

This changes the entire measurement family and provides direct RF dynamics.
It is model-conditioned by satellite/transmitter selection, and rasterized
absence is difficult to interpret without same-path detectability witnesses.
It therefore adds useful modality diversity but advances the current claim
ladder less directly than a held-out GNSS observer.

Maximum claim: model-conditioned multi-station forward consistency, not
independent identity evidence.

## Route E — fixed public SDR roots with raw time-resolved RF

Freeze two physically independent SDR roots before inspecting the target RF
window and compare their observer-specific Doppler trajectories with the same
held-out/null discipline.

This has high physical independence and avoids GNSS receiver observables, but
requires defensible server-side event time, frequency calibration, continuity
and same-path detectability. Earlier OpenWebRX/Kiwi work shows these properties
cannot be inferred from connectivity. The implementation and qualification
risk is currently much larger than the physical comparison.

Maximum claim: independent distributed RF orbital consistency if both raw
measurement paths are admitted.

## Comparison

| Rank | Route | New physical information | Negative interpretability | New roots required | Main risk |
|---:|---|---|---|---:|---|
| 1 | Held-out observer transfer | Directly tests prediction at unseen geography | Potentially high after full envelope | 1 | station-C nuisance may require forbidden flexibility |
| 2 | Wholly disjoint pair | Strong independent replication | High after four-link admission | 2 | repeats costly qualification/materialization chain |
| 3 | One-new-root cross baseline | Tests partial spatial transfer | Medium | 1 | one original root remains in the observable |
| 4 | Two-station SatNOGS | Adds direct-RF modality | Low-to-medium for absence | 2 | model-conditioned selection and raster transforms |
| 5 | Fixed public SDR pair | Strong direct-RF independence | Potentially high | 2 | event-time and calibration capability risk |

The ranking is by physical information gained per uncontrolled assumption,
not by software reuse or archive convenience.

## Recommended minimum vertical

The next work should be one offline observer-transfer mechanism spike. It must
not name a new station, date or observation product.

1. Define `Q_C` and the single predeclared anchor operator exactly in metres.
2. Give the target orbit, affine/non-orbital null and wrong-orbit families the
   identical operator and grid.
3. Determine whether receiver-clock cancellation is exact for the selected
   RINEX phase convention; leave satellite-clock and hardware terms explicit.
4. Propagate direct `t +/- delta_t` trajectories and all existing physical
   intervals into the C-only coordinate.
5. Add plausible synthetic station-C mismatch not generated from the nominal
   orbit and verify that the target is not preferred automatically.
6. Compute the minimum detectable held-out separation and refuse any model
   that requires a free rate, suffix refit or post-hoc anchor.
7. Only after a positive complete margin may a bounded observer set be declared
   and ranked by geometry before artifact discovery.

Allowed spike outcomes:

```text
OBSERVER_TRANSFER_MECHANISM_DISCRIMINATIVE
OBSERVER_TRANSFER_ENVELOPE_INSUFFICIENT
OBSERVER_TRANSFER_REQUIRES_FORBIDDEN_NUISANCE
```

## SHOCK

The failed ALGO/MDO primaries make the old topology look like a receiver
problem, but the stronger lesson is different: after a repeated-pass result,
the next independent datum may be an unseen observer, not another complete
two-station experiment. Separating discovery roots from confirmation roots can
increase physical independence while reducing the measurement surface.
