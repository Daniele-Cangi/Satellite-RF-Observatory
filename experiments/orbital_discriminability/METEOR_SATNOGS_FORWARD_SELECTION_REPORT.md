# METEOR-M N2-4 SatNOGS forward selection

## Outcome

```text
SATNOGS_GEOMETRY_SHORTLISTED_MEASUREMENT_TRANSFORM_UNRESOLVED
SatNOGS RF artifacts opened: 0
audio/decoded-data requests: 0
new gate family: none
```

This is the bounded successor to the closed Alkmaar–Bucharest OpenWebRX path.
It does not resume receiver discovery. It evaluates only the two declared
development observations and four already declared primary candidates for
METEOR-M N2-4 / NORAD 59051 / 137.900 MHz.

```text
Physical question:
Can a frozen METEOR orbit predict station-coupled carrier structure in two
independent SatNOGS products better than frozen non-orbital tracks?

New information produced:
The exact geometric ranking of the bounded four-root set, and the location of
the SatNOGS Doppler-control transform relative to the waterfall.

Why the existing experiment cannot answer it:
OpenWebRX did not expose bounded FFT event time, sequence continuity or a
same-path absence witness. SatNOGS supplies scheduled UTC and observer
metadata, but its waterfall uses a different receiver transform.

Minimum experiment:
Two good development roots, one later two-root primary selected from the four
sealed candidates, a model-blind detector and one frozen post-compensation
baseband prediction shared by the orbit and all nulls.

Stop condition:
No artifact access while native raster coordinates or the applied
Doppler-control ledger remain unresolved.
```

## Frozen records

The development payloads remain sealed. Their only current role is to support
a later detector-development authorization.

| Role | Observation | Station/root | Interval UTC | Client / radio | Declared sample rate | API status |
|---|---:|---|---|---|---:|---|
| development A | 14904366 | 4545 / OE9BKJ | 2026-08-29 13:21:42–13:29:17 | 1.9.3+5 / gr-satnogs 2.3.5.0-compatible | 3.000 MHz | good |
| development B | 14907984 | 5066 / SA1CKW | 2026-08-29 13:22:44–13:32:58 | 2.1.2 / unknown | 2.048 MHz | good |

The primary candidates remain unopened and are not yet a frozen primary pair.
`unknown` is retained literally; it is not treated as `good` or `bad`.

| Observation | Station/root | Interval UTC | Client / radio | Declared sample rate | Metadata qualification issue |
|---:|---|---|---|---:|---|
| 14919555 | 1768 / EA3AGB | 04:10:35–04:24:41 | 1.6 / gr-satnogs 2.3.1.1 | 2.048 MHz | status unknown |
| 14919561 | 5140 / hyperlink | 04:09:45–04:19:52 | 2.1.2 / unknown | 2.048 MHz | status and exact radio/flowgraph versions unknown |
| 14919551 | 147 / F6KKR | 04:08:12–04:22:51 | 0.8 / unknown | unknown | API altitude 100 m, client metadata 200 m |
| 14919554 | 949 / SM0KOT-VHF | 04:05:58–04:17:23 | 1.9.3 / gr-satnogs 2.3.5.0-compatible | 2.048 MHz | status unknown; 100 kHz LO offset declared |

All four primary records carry the same observation TLE. It is independent of
the unopened RF values but remains model-conditioned SatNOGS control metadata;
it cannot provide independent identity evidence.

## Geometry and null ranking

The calculation uses the exact pairwise intersection of the scheduled
intervals and first selects the single contiguous interval in which both
stations exceed 10 degrees elevation. The calibration-prefix/held-out split
is then frozen at 20/80 on that interval at 1 s cadence. This selection uses
orbit, coordinates and timestamps only; no RF value can move the boundary.

The four hardened G0 nulls are retained: station constant, station affine,
station quadratic and observer permutation. Ranking uses the smaller of:

1. the affine-residual differential span divided by the G1 three-bin rule;
2. the held-out RMSE of the best frozen null against the orbital trajectory.

| Rank | Pair (observation IDs) | Baseline | Joint visible interval UTC | Differential affine-residual span | Controlling null / held-out RMSE | Geometry-only resolution ceiling |
|---:|---|---:|---|---:|---|---:|
| 1 | EA3AGB–hyperlink (14919555/14919561) | 1,244.964 km | 04:13:15–04:19:52 | 4,506.364 Hz | station constant / 1,017.905 Hz | 1,017.905 Hz |
| 2 | hyperlink–SM0KOT (14919561/14919554) | 1,340.301 km | 04:09:46–04:16:10 | 4,103.047 Hz | station constant / 903.706 Hz | 903.706 Hz |
| 3 | F6KKR–EA3AGB (14919551/14919555) | 889.198 km | 04:13:15–04:20:22 | 2,933.458 Hz | station constant / 805.831 Hz | 805.831 Hz |
| 4 | F6KKR–SM0KOT (14919551/14919554) | 1,569.754 km | 04:10:44–04:16:10 | 3,751.189 Hz | station constant / 752.816 Hz | 752.816 Hz |
| 5 | F6KKR–hyperlink (14919551/14919561) | 368.303 km | 04:10:44–04:19:52 | 996.037 Hz | station affine / 315.920 Hz | 315.920 Hz |
| 6 | EA3AGB–SM0KOT (14919555/14919554) | 2,389.347 km | 04:13:15–04:16:10 | 1,163.823 Hz | station quadratic / 13.807 Hz | 13.807 Hz |

The result again demonstrates that baseline length is not the ranking rule.
The longest baseline is last because its short common interval lets a frozen
quadratic approximate the held-out orbital shape. The geometric values above
are not detector requirements and not admission margins: event-time,
frequency-axis, orbit and receiver-transform envelopes have not been
subtracted.

## Native SatNOGS waterfall semantics

The versioned client source defines a native `waterfall.dat` header containing
`timestamp`, `nchan`, `samp_rate`, `nfft_per_row`, `center_freq` and
endianness. Each row contains a microsecond relative-time field and one
float32 spectrum. Thus the native, pre-plot coordinate is:

```text
frequency-bin spacing = samp_rate / nchan
nominal row spacing    = nfft_per_row * nchan / samp_rate
actual row event time  = header timestamp + tabs / 1e6
```

The HDF5 artifact retains relative time, absolute time and frequency datasets,
plus the header start time. The client source explicitly warns that this start
time need not equal the scheduled observation start. It also stores the
per-frequency offset and scale used to map power into clipped uint8 values.
Sample rate therefore does not equal spectral resolution.

PNG is a further display transform. Clients 1.6 and 1.9 render a Matplotlib
image with plot extents but their versioned source does not demonstrate the
embedded native-header metadata later added to the 2.1 family. A PNG pixel is
not automatically one native FFT bin, and the sealed products have not been
opened to see which metadata they actually contain.

## Causal cut discovered: Doppler is an applied control

Official `satnogs-flowgraphs` source for the checked 1.3, 1.5 and 2.5.2 FSK
families connects:

```text
Soapy source
→ SatNOGS Doppler compensation
→ doppler_corrected virtual stream
→ waterfall sink
```

The waterfall is therefore not an absolute-RF Doppler coordinate. It is a
model-controlled baseband coordinate. This does not make the experiment
meaningless: a carrier matching the frozen orbit should remain near a stable
baseband location, while constant, affine, quadratic or wrong-observer sky
tracks should evolve after receiving the same control. But the applied
control must be part of every prediction and null.

The current record metadata does not expose the applied correction samples or
polynomial. It identifies `gr-satnogs` for some stations, not the exact
deployed `satnogs-flowgraphs` commit. Regenerating the nominal Doppler from the
same TLE without bounding update timing, quantization, retuning and residual
receiver behavior would simply reinsert the model and overstate the evidence.

## Admission decision

```text
geometry:              POSITIVE
independent roots:     PRESENT IN DECLARED SET
native raster bounds:  UNRESOLVED UNTIL DEVELOPMENT ARTIFACT METADATA
applied control trace: UNRESOLVED
measurement path:      NOT YET ADMITTED
primary pair:          NOT FROZEN
```

The top geometric pair is EA3AGB–hyperlink, but it is not selected as primary
yet. Geometry is necessary, not sufficient. The exact remaining blocker is a
bounded, reversible post-Doppler transform for the development products:
native row times and bins, actual waterfall dimensions, deployed transform
lineage and an error envelope for the applied Doppler control.

## Maximum next action

After review and explicit authorization, the smallest next action is a
development-only metadata/header characterization of observations 14904366
and 14907984. It must not expose spectrum values, waterfall pixels, audio,
decoded frames or any primary artifact. If the required coordinates cannot be
read without accessing signal-derived payload, or the applied control cannot
be bounded from outcome-independent metadata, close this SatNOGS route without
building a detector.

Only if that characterization passes may a model-blind detector be developed
on the two development products. The four primary payloads remain sealed
through both steps.

## Sources

- [SatNOGS Client 2.1 waterfall source](https://docs.satnogs.org/projects/satnogs-client/en/stable/_modules/satnogsclient/waterfall.html)
- [SatNOGS Client artifact source](https://docs.satnogs.org/projects/satnogs-client/en/stable/_modules/satnogsclient/artifacts.html)
- [SatNOGS Client 1.9 waterfall source](https://docs.satnogs.org/projects/satnogs-client/en/1.9/_modules/satnogsclient/waterfall.html)
- [SatNOGS Client 1.6 waterfall source](https://docs.satnogs.org/projects/satnogs-client/en/1.6/_modules/satnogsclient/waterfall.html)
- [SatNOGS Client 1.6 artifact source](https://docs.satnogs.org/projects/satnogs-client/en/1.6/_modules/satnogsclient/artifacts.html)
- [SatNOGS generic IQ flowgraph](https://gitlab.com/librespacefoundation/satnogs/satnogs-flowgraphs/-/blob/master/generic/iq_receiver.grc)
