# Reference MW stability: temporal model not qualified, a concrete phase witness

**The fixed block model is not yet a qualified error model for integer fixing.**
It covers 765/841 held block means (90.96%) with its nominal 95% intervals,
under unqualified stationary IID assumptions. Those correlated observations
are not independent trials, so no binomial significance claim is made.

The useful new diagnosis is that 19 of the 31 original integer-mean disagreements
share BRAZ/G05. That link contains a large, unflagged raw MW/GF change at
10:59:30 GPST. The existing GF primitive detects the change when applied
post-score; no new detector or repaired integer is needed to expose this witness.
The finding does not uniquely attribute its physical cause or explain every
other disagreement. No failing sample/configuration is removed or rescored.

## Execution and input boundary

One execution at `e803092f71cbc34a18c67add0e92e87c0403bf5f`, using only the pinned
reference observation JSON. No target input file is opened. G12 rows, if inserted
in the reference map, are excluded before RF/time arithmetic. All prediction
means, prefix block scales and Student intervals were saved before held scoring.
The graph change projection was written only afterward and never feeds the fit.
No orbit/clock product, target state, target OSB, new acquisition or orbital fit.
This remains exposed-data development, not prospective confirmation.

The original 4,851 reference DD configurations and 251 scored controls reproduce
exactly their statuses/support and scientific outcomes: 220 held means agree
with the training integer, 31 disagree, and integer RMS improves over the scalar
float model in 135/251. The original input bytes and #242 numerical artifacts
remain unchanged. Cross-platform continuous reductions are checked at numerical
tolerance; all identities, segments/support and integer decisions remain exact.

## Complete temporal-model support

| Quantity | Count |
|---|---:|
| All reference DD configurations | 4851 |
| No original contiguous held baseline | 4600 |
| Original scored scalar controls | 251 |
| Controls with sufficient/nonzero complete prefix block scatter | 179 |
| Controls without two complete prefix blocks | 72 |
| Temporal models with at least one complete held block | 171 |
| Temporal models with only partial held support | 8 |
| Complete held block means scored | 841 |
| Inside nominal 95% interval | 765 |
| Outside nominal interval | 76 |

Partial prefix/held blocks and original unsupported cases stay in the artifacts.
A complete block has ten 30 s samples; its prediction includes future-block
scatter, not only the standard error of the prefix mean. Low prefix degrees
of freedom and block independence remain unqualified. No noise floor, block
length or interval factor was tuned after the result. The original IF weights
were not substituted for an unsupported empirical block model.

Of the 31 original integer-mean disagreements, 16 have a temporal model; 13 of
those have at least one nominal interval violation. Fifteen have insufficient
complete prefix blocks. These are descriptive overlapping comparisons, not a
validated wrong-integer detector or proof the other three integers are correct.
A constant effective DD bias remains confounded with the ambiguity, even where
temporal forecasts appear stable.

## Nonseparable changes versus path breaks

The held link changes are referenced to the last full prefix block,
10:25-10:29:30. Six full held blocks have 58, 57, 57, 56, 55 and 54 complete
links, with receiver/satellite additive design rank 25 and 33 to 29 independent
cycle contrasts. Only fitted rows/residuals are meaningful; parameter gauges
are not clock measurements or a hardware-delay decomposition.

This post-score description can compare full blocks on either side of a gap;
it does NOT claim a continuous ambiguity across that gap. In particular:

- **AREQ/G14:** the 10:35 block mean is 18.860 wide-lane cycles above its last
  prefix block. The raw path has missing fields at GPST 38010 and rejected
  LLI `1,1` at 38040, then resumes at 38070. This is a known path break, not
  evidence of an unflagged stable-bias drift. The original forecast stops.
- **STJO/G25:** the 10:40 block mean changes 6.243 cycles; the retained stream
  has missing epochs before it. A fresh ambiguity across reacquisition can
  contribute; it is not silently connected to the old forecast.
- **BRAZ/G05:** its 10:55 block mean changes -6.517 cycles despite flag-valid
  raw support. The post-score receiver/satellite projection leaves -4.644
  cycles on that link; the raw witness below identifies a sharp late change.

A large projected residual alone cannot uniquely identify the faulty endpoint:
the AREQ/G14 change also projects onto BRAZ/G14. The graph results show which
changes survive separable receiver/satellite terms, not which hardware is guilty.
All complete link changes and leave-one-link-out witnesses remain available.

## BRAZ/G05 raw witness, inspected after scoring

| GPST tag | MW, wide-lane cycles | GF phase, m | LLI |
|---|---:|---:|---|
| 39540 (10:59:00) | 5.877903713 | 4.588649653 | 0,0 |
| 39570 (10:59:30) | -58.858376218 | -11.288483907 | 0,0 |
| 39600 (11:00:00) | -58.927196858 | -11.275718376 | 0,0 |

The 30 s change is **-64.736279931 wide-lane cycles** and **-15.877133559 m GF**.
The existing `phase_continuity.segment` first-difference witness detects a
break from these samples, despite zero LLI. A phase discontinuity is a concrete
candidate explanation; its precise integer pair and physical cause are not
certified. No phase correction, branch replacement or removal follows this
post-score observation. Tests reconstruct it from the pinned raw reference file.

Nineteen of the 31 disagreeing DD configurations include this same link. They
therefore reuse an anomalous input rather than representing nineteen independent
failures. This is an overlap fact, not a causal proof that fixing that one link
would produce nineteen correct integers. The remaining disagreements stay open.

## Consequence

The immediate software need is continuous tracking/quality handling of the raw
phase arc, using existing GF and complementary MW witnesses, with explicit
reset/unavailable status and retention of failures. A current-epoch measurement
may diagnose an online break, but must not be used to erase a withheld forecast
error after reveal. That distinction keeps evaluation honest.

A larger or smaller inherited IF weight would not resolve these discontinuities.
Nor does temporal stability establish the absolute DD bias or the remaining
narrow-lane integer. The fixed error model is not admitted to an orbital fit.
No physical covariance, correct integer assignment or S2 completion is claimed.
Further evaluation needs independent tests of causal break handling and the
reference-only error model, without selecting thresholds from G12.

See [method/reproduction](README.md), [frozen predictions](predictions-before-scoring.json.gz),
[scalar and temporal scores](scores.json.gz) and [post-score graph changes](post-score-changes.json.gz).


The exact dependency-list bytes read on Windows are retained in
`requirements-as-read.txt`: its CRLF bytes match the original recorded hash;
its text matches the producer's Git blob after line-ending normalization.
All seven Python producer hashes match their original Git bytes literally.
No input, original manifest or numerical result was rewritten for this checkout
format difference.
