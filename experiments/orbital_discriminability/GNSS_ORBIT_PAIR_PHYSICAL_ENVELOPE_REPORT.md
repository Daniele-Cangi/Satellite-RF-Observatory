# G14/G17 candidate-specific physical-envelope result

## Physical question

> After applying the existing outcome-independent physical uncertainty
> families to the exact DOY-220 G14/G17 coordinate, would a future negative
> result distinguish the frozen orbital model from the affine and G22 nulls?

Only the exact-hash DOY-220 broadcast-navigation artifact and the frozen orbit-
pair screen receipt entered this calculation. No observation product was
discovered, selected or opened.

## Frozen coordinate

```text
stations:          GOLD00USA / NLIB00USA
target/reference:  G14 / G17
wrong-orbit null:  G22
raw GPS window:    2026-08-08 05:07:00--08:19:30
feature epochs:    384
calibration:       first 77 features
held-out:          last 307 features
```

Both nulls receive the same event-time treatment, frequency coordinate,
physical terms, affine prefix projection and held-out suffix. No suffix
nuisance fit is permitted.

## Result

```text
GNSS_ORBIT_PAIR_PHYSICAL_ENVELOPE_DOMINATES
```

| Quantity | Value |
|---|---:|
| Prefix-affine held-out separation | 556.645586 Hz p-p |
| G22 held-out separation | 403.375454 Hz p-p |
| Controlling separation | 403.375454 Hz p-p |
| One-model physical envelope | 366.877021 Hz p-p |
| Pairwise comparison envelope | 733.754042 Hz p-p |
| Remaining physical margin | **-330.378588 Hz** |

The negative margin is not a measurement outcome and is not evidence against
G14, G17 or the broadcast orbital model. It means that the existing
conservative nuisance family can absorb the entire modeled orbital-versus-G22
held-out distinction. A negative observation would therefore be
epistemically ambiguous under this contract.

## Contribution ledger

| Pairwise contribution | Epistemic treatment | Bound |
|---|---|---:|
| Broadcast-orbit SV accuracy | `MODELED_INTERVAL` | 324.268025 Hz |
| Antenna PCV and phase wind-up | `MODELED_INTERVAL` | 81.067006 Hz |
| Multipath and signal-specific hardware | `CALIBRATION_ADMISSION_LIMIT` | 81.067006 Hz |
| Satellite-clock retarded-time remainder | `MODELED_INTERVAL` | 81.067006 Hz |
| Station displacement, EOP and relativity | `MODELED_INTERVAL` | 81.067006 Hz |
| Station event time, direct trajectory envelope | `MODELED_DIRECT_TRAJECTORY_ENVELOPE` | 44.628890 Hz |
| Higher-order ionosphere | `MODELED_INTERVAL` | 40.533503 Hz |
| RINEX carrier-phase quantization | `KNOWN_FORMAT_BOUND` | 0.034937 Hz |
| Differential troposphere | `MODELED_INTERVAL` | 0.020661 Hz |

No unresolved term was silently set to zero. There is no calibrated
probability and no root-sum-square combination: the frozen policy sums the
per-model bounds linearly and doubles that sum for a two-model comparison.

The dominating fact is the conservative aggregate, not one uniquely proven
failure mechanism. Even setting the broadcast-orbit contribution to zero
would leave 409.486016 Hz pairwise, still 6.110562 Hz above the frozen G22
separation. Removing only the learnable multipath/hardware term would leave
652.687035 Hz. No single permitted term deletion admits the candidate.

For admission, the one-model envelope would have to be below
201.687727 Hz. That requires a defensible reduction of at least 165.189294 Hz
per model across more than one physical family; it cannot be obtained by
renaming an uncertainty or learning from the held-out observation.

## Change-of-abstraction review

### Block

The selected GOLD/NLIB G14/G17 geometry is not prospectively falsifiable under
the existing conservative physical-envelope semantics.

### Information value

The geometry screen found a real, repeatable orbital distinction, but this
audit shows that geometric separation alone is insufficient. The limiting
quantity is the structure assigned to orbit/path uncertainty after the affine
projection.

### Is the current abstraction necessary?

The double-difference coordinate remains physically useful. What is not yet
demonstrated is that treating every metre-scale path interval as an arbitrary
per-epoch adversarial perturbation is the right uncertainty family for this
coordinate. That question must be answered outcome-independently; the present
candidate cannot assume a smoother family merely because the conservative one
fails.

### Physically distinct alternatives

1. Bound broadcast-orbit and clock error as predeclared smooth trajectory
   families derived from outcome-independent ephemeris dynamics, rather than
   arbitrary sample-wise path signs.
2. Use a geometry whose orbital-versus-alternative separation exceeds the
   existing envelope without changing its uncertainty assumptions.
3. Add an independent station or quotient coordinate that cancels more of the
   common orbit, clock and hardware family before scoring.
4. Design a separately prospective phase-continuous or multi-frequency
   observable with explicit same-path witnesses; do not retrofit it to DOY 220.

The smallest next physical question is whether a structured, premeasurement
broadcast-orbit/clock family is defensible and materially narrower in this
double-difference coordinate. That work is not implemented here.

## Authorized conclusion

The DOY-220 G14/G17 candidate is closed before prospective-plan freeze and
before structural qualification. Lower-ranked dates are not retries. No
observation access is authorized.

The strict receipt is
`GNSS_ORBIT_PAIR_PHYSICAL_ENVELOPE_RECEIPT.json`; its SHA-256 is
`8e25a8f1a335fb12d883479e316a670ed27a838e26dbe12b465b5d6546f60bbe`.
