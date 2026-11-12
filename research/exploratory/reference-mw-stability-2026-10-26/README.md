# Reference-only MW bias and temporal stability

Follow-up to the raw integer feasibility of #242, on exposed observations.
G12 RF/orbit/clock, target OSB and previous states are excluded. Open only the
retained GPS reference raw-phase extract (SHA-256 26152824138bb58c7af7f1db69019704e341eb87a7334a93fb33f9d345d44f92).
Reuse the original raw signals, flags, prefix GF segmentation, 10:30 GPST
cut, all 4,851 reference DD configurations and their original support/terminals.
No new input acquisition, detector, slip repair, integer fixing or orbital fit.

## Prefix-only temporal hypothesis

Use fixed absolute 300 s bins, each exactly ten 30 s samples. In each original
latest joint prefix arc, retain every complete block and list partial blocks.
For at least two complete blocks with nonzero scatter, predict a FUTURE block
mean by the prefix block mean with nominal 95% Student halfwidth
`t(.975,K-1)*s_block*sqrt(1+1/K)`. This includes future-block scatter as well
as uncertainty of the training mean. Insufficient/zero-scatter models remain
unsupported, without substituting the old IF weights. No model is selected or
rescaled using held results. All predictions are saved before held scoring.

This hypothesis assumes stationary IID Gaussian block means; 300 s separation
does not establish independence. Low degrees of freedom, temporal structure,
shared endpoints and a constant DD bias remain limitations. It is a nominal
conditional prediction interval, not physical uncertainty or an integer
admission rule. Partial endpoints remain visible and original scalar scores
are replayed on their unchanged 251 held controls, including all disagreements.
No pooled independent-trial inference uses the overlapping DD blocks.

## Post-score structural diagnosis

After scoring, compare full held link-block means against the last full prefix
block (10:25-10:29:30). Project changes onto additive receiver+satellite terms.
Report gauge-independent fitted rows and residuals only, with graph rank and
leave-one-link-out residuals where redundant tracking supports them. DD
annihilates the separable part, so surviving changes describe a link-dependent
component. They do not uniquely identify multipath, hardware, atmosphere or
an unflagged phase jump. No posterior projection changes a forecast or removes
a failing control. No absolute constant hardware bias is measured by this test.

The previous 31 disagreements motivate this exposed diagnostic; this is not
blind confirmation of a selected error law. The scalar integer ambiguities
and the remaining narrow-lane mode stay unassigned. Historical results,
weights/floors, masks and prospective boundaries remain unchanged.

References: [NIST Student prediction limits](https://www.itl.nist.gov/div898/software/dataplot/refman1/auxillar/predlimi.htm)
and [ESA MW observable and noise/bias limitations](https://gssc.esa.int/navipedia/index.php/Detector_based_in_code_and_carrier_phase_data%3A_The_Melbourne-W%C3%BCbbena_combination).

## Reproduction

Use the existing phase-report CLI and a fresh output directory:

```console
python -m research.exploratory.real_phase --reference-mw-stability --inputs research/exploratory/inputs/real_phase/observations_gps_only_v2.json --output data/reference-mw-stability-2026-10-26
```

The target-input/cache/integer-ambiguity options are rejected for this mode.
Retain the producer/source identities, one reference input hash, frozen block
predictions, original/native and block scores and post-score link changes.
