# DRAO labelled-forward rank-1 physical-envelope scope

This is a bounded hardening step inside the existing DRAO labelled-forward
vertical. It is not a new gate and authorizes no observation-product query,
selection, header access, payload access, decoding or score.

## Physical question

Does the fixed DOY237 DRAO geometry retain positive held-out separation from
the already frozen affine and time-reversed nulls after a date-specific
model-side envelope and a predeclared complete-measurement reserve are applied
to the same six labelled tracks?

## New information

The audit can determine whether the first-ranked geometry is physically worth
qualifying. A negative result closes this DRAO window before any observation
lookup. A positive result authorizes only review of one structural
qualification contract; it does not select or freeze an observation product.

## Frozen parent and geometry

- parent receipt:
  `GNSS_DRAO_LABELLED_FORWARD_GEOMETRY_SCREEN.json`;
- parent raw/canonical SHA-256:
  `06161af57ada12e081faef7cf470e540ea5fff5dd7cf2f6614077b738852ed62`;
- observer: `DRAO00CAN`, DOMES `40105M002`;
- GPS day: DOY237 / 2026-08-25;
- raw grid: `04:55:00--06:04:00 GPS`, 139 epochs at 30 s;
- calibration prefix: indices 0--78;
- held-out suffix: indices 79--138, beginning `05:34:30 GPS`;
- fixed codebook: `G14/G15/G17/G20/G24/G30`;
- controlling null: `TIME_REVERSED_GEOMETRY`;
- screened controlling separation: `36546.47062947322 m`;
- screen event-time envelope: `1396.8700135458348 m`;
- minimum shifted elevation: `15.103639282444858 deg`.

The codebook, date, station, interval, partition and null family cannot change
after this scope. G14 and G17 appeared in historical development; a later
experiment would be temporally independent, not satellite-family independent.

## Model input

The sole transient input is the already shortlisted NOAA NGS broadcast file:

```text
brdc2370.26n.gz
compressed bytes: 71512
compressed SHA-256: 7676ce71221f4a0313f5ba2981886826c87ff346782b0993b9505b0dc0722ca8
uncompressed SHA-256: 09ebad2417413c30f507c4f7a784b8f67c61a129b4246d45e1d58803d1cddb22
```

It may be reacquired solely to regenerate the model-side envelope. It must be
hashed before parsing, held transiently and destroyed after compilation.

## Exact model-side transformations

The audit must:

1. iterate one-way transmit time from each receive epoch;
2. rotate transmit-frame ECEF through Earth rotation during light time;
3. ensemble-centre all six tracks at each epoch;
4. fit only a constant and rate per centred track on prefix indices 0--78;
5. apply the frozen affine and time-reversed nulls without suffix refit;
6. evaluate event time directly at `t-15 s` and `t+15 s`;
7. retain broadcast-clock non-affinity as an omitted-path envelope rather than
   letting it establish the orbital result;
8. apply every term to the same grid and prefix projection.

No free time phase, interpolation, time warp, satellite substitution or
held-out nuisance fit is allowed.

## Envelope terms

The model-side envelope contains:

- direct event-time trajectory displacement at `+/-15 s`;
- broadcast-orbit user-range-accuracy family from the selected ephemerides;
- omitted broadcast satellite-clock non-affinity using AF0/AF1/AF2 and the
  eccentricity relativistic term at iterated transmit time;
- differential troposphere under an intentionally conservative per-epoch
  slant-delay box derived from `0--3.5 m` zenith delay and actual elevation;
- a `4 m` common-mode held-out reserve for station displacement, EOP and
  remaining relativistic implementation.

The troposphere box is propagated through the complete ensemble-centering and
prefix-projection linear operator. It does not assume that a constant zenith
delay is exact.

The capability-conditional reserve remains:

- higher-order ionosphere: `2 m`;
- antenna PCV and phase wind-up: `4 m`;
- multipath, signal-specific hardware and receiver implementation under a
  complete phase-minus-code witness: `2500 m`;
- RINEX F14.3 carrier-phase quantization: `0.0017238368006440115 m`.

An epoch-common receiver clock cancels under ensemble centering. Track- or
signal-dependent implementation does not cancel and stays inside the
phase-minus-code witness reserve. No unresolved term becomes zero.

## Conditional measurement clauses

The numerical reserve is usable only if a later distinct qualification proves:

- L1C, L2W, C1C and C2W for every fixed PRN at every one of the 139 epochs;
- blank or zero LLI on both carrier-phase fields;
- no gap, interpolation, epoch substitution or unsupported scale transform;
- geometry-free phase continuity with maximum absolute second difference no
  greater than `0.09514683639918244 m`;
- per-satellite anchored ionosphere-free phase-minus-code peak-to-peak no
  greater than `1250 m` over the complete window;
- header identity, time system, interval and `TIME OF LAST OBS` coverage;
- exact RINEX carrier-phase field precision compatible with the frozen
  quantization term.

Additional receiver tracks remain descriptive. Missing or invalid required
tracks fail admission. S1C/S2W remain optional diagnostics.

## Decision rule

Let `B` be the sum of the date-specific one-model terms and the conditional
measurement reserve. Recompute the exact null separation using the retarded
geometry. Admission requires:

```text
exact controlling separation > 3 B
```

The three copies allow the orbital model to worsen by `B`, the null to improve
by `B`, and still require a preference exceeding `B`. The terminal outcomes
are:

```text
DRAO_LABELLED_FORWARD_PHYSICAL_MARGIN_ADMITTED
DRAO_LABELLED_FORWARD_PHYSICAL_ENVELOPE_DOMINATES
DRAO_LABELLED_FORWARD_PHYSICAL_BOUND_UNAVAILABLE
```

## Stop

Stop after one receipt and report. Do not query whether a DOY237 DRAO
observation exists. Do not freeze a primary or build an executor. If the
margin is admitted, the next maximum action is review of one structural-only
qualification contract for the fixed date, window and codebook.
