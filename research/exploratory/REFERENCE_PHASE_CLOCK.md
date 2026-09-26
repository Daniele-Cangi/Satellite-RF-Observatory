# Reference-only phase clock, exposed September 5 cohort

This exploratory check asks whether carrier increments from the already exposed
reference satellites can supply a target-independent receiver-clock drift for
the later real-target inverse. G12 observation and state values are absent from
the input and rejected again at the model boundary. The original day cohort,
products, receipts and closed outcomes remain unchanged.

For each station and 30 s evaluation interval, `reference_phase_clock.py`
subtracts the existing precise reference/VMF3 path model from ionosphere-free
carrier phase. An independently modeled elevation mask admits each endpoint;
continuous differences cancel each link's constant phase ambiguity. The mean
and median of at least four remaining references estimate clock increment.
Each reference is then held out of its own estimate. This is a relative
diagnostic using shared products, **not** an absolute clock or uncertainty bound.

Five of seven stations have parsed phase; YELL's event and BOGT's phase header
remain unsupported. All 300 evaluation blocks have at least four admitted
references. Across 2,817 leave-one-reference-out paths, the 30 s error RMS is
0.000707 m/s for the mean and 0.000678 m/s for the median. These aggregates hide
a material tail: the maximum absolute errors are 0.02823 and 0.02829 m/s.
At BRAZ/G13, GPST 38040, the held-out median error is +0.02829 m/s, or about
0.85 m over 30 s. Its RINEX phase loss-of-lock indicators are zero. We call
this an **unflagged phase discontinuity**, not a diagnosed cycle slip.
The previous phase report required an uninterrupted training ambiguity for
each link and had no BRAZ/G13 training entry; this interval was absent there.
Both outcomes remain visible. Median reduces this link's effect on the full
station-clock estimate, but cannot qualify the anomalous held-out path.

This result supports a robust reference-only *drift input* to a conditional
real-target test. It does not constrain the constant station-specific code
bias that dominated the earlier position sensitivity, prove independent
reference products, or justify reducing the 20 m code uncertainty floor.
For real-target positioning the remaining work is a target-only observation
adapter, RF-derived propagation geometry, fit and held-out prediction, and a
defensible joint error budget. Any target phase opening after this study is
exploratory: the historical G12 code/outcome has already been exposed.

Replay from repository root:

```powershell
python -m research.exploratory.reference_phase_clock research/exploratory/results/reference_phase_clock_v1.json
python -m pytest research/exploratory/tests/test_reference_phase_clock.py -q
```

The JSON stores source/input/baseline hashes, every full-block estimate,
held-out diagnostic, unsupported station and model/admission failure.
