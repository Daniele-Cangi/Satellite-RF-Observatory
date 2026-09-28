# TEXBAT ds7: does the NOAA network improve a modeled clock check?

## Answer for this exposed episode

**No incremental detection benefit is demonstrated.** With the same broadcast
GPS orbit/clock hypothesis, fixed coordinate, 14 epochs and 11 common satellites
per epoch, ds7's time push is already large in the single-receiver clock
estimate. Subtracting the mean clock estimate of two real NOAA receivers adds
contemporaneous context, but does not improve the clean control in this sample.

| Channel, centered on two source-defined preattack epochs | Largest absolute deviation over 14 cleanStatic epochs | Largest absolute deviation in 10 ds7 time-push epochs |
|---|---:|---:|
| Local code + broadcast model, no remote observations | 1.17 m | 312.31 m |
| Same local estimate − TXAU/SAM2 mean receiver clock | 1.23 m | 312.18 m |

The [complete result](results/pnt_texbat_network_clock_v1.json) reports every
epoch, source hash, excluded record, clock fit and satellite residual summary.
The largest difference between the separately fitted TXAU and SAM2 clocks is
0.59 m in these 14 epochs. It is *agreement under one shared GNSS broadcast
model*, not an independent absolute-time certificate. A 1.17 m maximum on 14
correlated clean epochs is not a false-alarm rate or a deployable threshold.
The attack is also visible in the local model without the network. No time to
alarm, equal-false-alarm network gain, origin attribution or live verdict is
inferred.

## Model and inputs

The five exact input hashes are in the JSON. Four inputs and the monotonic
RRT-to-GPST preattack anchor are inherited from the [earlier pairing report]
(PNT_TEXBAT_NOAA.md): UT processed `cleanStatic/channel.mat` and
`ds7/channel.mat`, plus NOAA TXAU and SAM2 C1 observations for 2012-09-14.
The fifth input is NOAA's [daily composite broadcast GPS NAV]
(https://noaa-cors-pds.s3.amazonaws.com/rinex/2012/258/brdc2580.12n.gz),
a RINEX 2.10 file. The new adapter converts its fixed-width GPS records into
the repository's existing RINEX 3 navigation-record primitive and reuses the
existing broadcast satellite/clock/propagation model. It excludes the two
unhealthy records; at each comparison epoch the nearest healthy navigation
`toc` within two hours is selected for each of the common satellites.

TXAU and SAM2 antenna coordinates come from their own RINEX headers. For the
local fixed site, the declared ECEF coordinate is
`(-741992.74, -5462240.48, 3198027.11) m`, the [published mean cleanStatic
position](https://radionavlab.ae.utexas.edu/images/stories/files/papers/LemmenesGNSSpaper.pdf)
reported by a different software receiver. It is derived from the same clean
RF recording and **is not an independent ground survey**. No coordinate from
attacked ds7 is fitted. NOAA's station coordinates are header-declared, not
independently audited in this study.

For each GPST epoch, only satellites with valid local clean/ds7 code **and**
C1 code at both external stations enter all four fits. There are 154 such
satellite rows in 14 epochs, the same selection as the previous report. For
each receiver, the median of `observed code − modeled range` estimates its
common receiver-clock term in metres. The model includes broadcast satellite
motion/clock, Earth rotation and its existing simple troposphere term. It does
not qualify L1 group-delay or cross-receiver hardware biases, ionosphere, the
published local coordinate's error, or absolute clock accuracy. Local
satellite residual median absolute magnitudes range from about 11 to 14 m,
versus about 1 to 3 m at the external receivers; centering on the preattack
epochs removes a constant receiver-specific code level, not those systematics.

`local-only` here means local per-satellite observations plus the **same
externally archived broadcast NAV** used in both channels, with no CORS
observations. `local-minus-network` subtracts the mean of the two separately
fitted CORS receiver clocks before applying its own preattack centering. The
network-only clock and the CORS disagreement are retained. The two channels
are compared on identical satellites and epochs; the ds7 receiver's attacked
ORT is not used as a time axis. CleanStatic and ds7 share their underlying RF
recording, so this is an exposed counterfactual, not an independent trial.

Download the [four paired sources](PNT_TEXBAT_NOAA.md) and the NAV file, then:

```console
python -m research.exploratory.pnt_texbat_clock_context cleanStatic-channel.mat ds7-channel.mat txau2580.12d.gz sam22580.12d.gz brdc2580.12n.gz report.json
python -m pytest research/exploratory/tests/test_pnt_texbat_clock_context.py research/exploratory/tests/test_pnt_texbat_noaa.py -q
```

No UT raw RF or processed MATLAB file is redistributed in the repository.
The original pairing result is unchanged and can still be reproduced byte for
byte after the shared pairing helper refactor.

## Direction

This is a useful negative selection result: more modeling of ds7 cannot turn
an obvious single-receiver time push into proof of network detection gain.
Keep the network path for corroboration and incident context. A stronger
product claim needs an episode where the local-only control is genuinely
ambiguous, a defensible fixed coordinate/clock baseline, and enough benign
variation to compare false alarms. Public software-only data can be searched
for that episode; hardware acquisition is not assumed. An independently timed
reference remains necessary for an absolute-time authenticity claim.
