# Integer phase information in the retained G12 raw observations

Exposed-data feasibility, distinct from the failed RF correction in #240.
No target orbit/clock, prior state, target OSB, new acquisition or state fit.
Reuse the complete 10:00-11:00 GPST September 5 raw extract, same signals
C1C/C2W/L1C/L2W, all seven listed receivers and 22 allowed references.
Six receivers have parsed observations; YELL remains unsupported. This is a
raw-signal algebra/continuity diagnostic, not an orbital observation admission:
no target-state-dependent elevation mask is constructed or borrowed.

## Fixed calculation before the first execution

From the existing four-channel transform, form the uncorrected MW observable
in cycles of lambda_W=c/(f1-f2). Double difference four endpoints of every
receiver pair and satellite pair with signs (+,-,-,+). The all-reference
pairs are controls; every G12/reference pair is retained separately. Do not
apply code OSB translations, rescale extracted fields again or round IF phase.
Separable receiver/satellite fractional biases cancel in this law; arbitrary
remaining link code/phase bias or multipath does not.

Fit only time < 10:30 GPST. Reuse the existing causal GF continuity primitive
on those training observations only, with base breaks at missing/flagged raw
samples. For each DD use its latest joint segment ending at 10:29:30, with at
least two samples. Freeze the float mean, exact best/second 1-D integer choices,
training likelihood gaps and all integers within delta-Q <= 4 of the float
optimum. This last interval is a descriptive conditional likelihood set,
not a physical confidence interval or an admission threshold.

Use the existing equal-band raw covariance preserving IF sigmas 20 m code and
20 mm phase. Carry its exact MW transform and the four endpoint contributions.
Temporal/endpoint independence and those weights are assumptions, not measured
RF precision. Do not fit a new noise scale or claim repeated DD configurations
are independent: they share raw endpoints and their likelihoods are not pooled.

All predictions precede held scoring. From 10:30 onward, stop at the first
missing/flagged endpoint, without restart, phase repair, held GF-based selection
or refitting. Score frozen float/integer means on every supported held sequence.
An unflagged slip remains a possible held failure; a blank LLI is not proof of
continuity. Retain unsupported configurations and all worsening cases.

## What this can and cannot establish

A unique training integer under the weighting scenario is only a hypothesis.
The model y=N_W+b_DD+noise has the exact invariance N_W+k, b_DD-k if the link
bias is unconstrained. Retain that identifiability failure explicitly. A real
integer fix needs justified bias structure and noise/continuity, not closeness
to a rounded value. No integer is admitted by this feasibility report.

MW observes N1-N2 only. The equal integer shift (N1+k,N2+k) leaves MW unchanged
but shifts IF phase by k*c/(f1+f2). This remaining narrow-lane ambiguity must be
resolved through another valid constraint before an orbital fit can use a phase
level. No bias-position ambiguity, position accuracy or S2 completion is claimed.

References: [ESA ambiguity fixing](https://gssc.esa.int/navipedia/index.php?title=Carrier_Phase_Ambiguity_Fixing),
[ESA GNSS book, section 6.3.1.1](https://gssc.esa.int/navipedia/GNSS_Book/ESA_GNSS-Book_TM-23_Vol_I.pdf)
and [RINEX 3.05, section 6.7](https://files.igs.org/pub/data/format/rinex305.pdf).
The synthetic tests exercise the integer law, separable and nonseparable biases,
remaining narrow-lane shift, held-value poisoning and GF-null slips.

## Reproduction

Use the existing phase-report CLI with a fresh output directory:

```console
python -m research.exploratory.real_phase --integer-ambiguity --inputs research/exploratory/inputs/real_phase/observations_gps_only_v2.json --target-input research/exploratory/inputs/real_phase/g12_target_phase_v2.json --output data/integer-phase-2026-10-26
```

Source revision/hashes, both input hashes, all frozen predictions and native
scores are retained. Historical experiments and sources remain reproducible
through their original artifacts/Git versions. No new authority or fixing API.
