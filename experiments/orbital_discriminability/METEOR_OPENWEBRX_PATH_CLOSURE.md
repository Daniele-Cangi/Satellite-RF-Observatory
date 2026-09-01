# METEOR OpenWebRX measurement-path closure

## Terminal result

```text
MEASUREMENT_PATH_INSUFFICIENT
OPENWEBRX_PATH_CLOSED
```

This closes only the explicitly bounded Alkmaar–Bucharest OpenWebRX path for
the first METEOR-M N2-4 forward vertical. It does not classify either receiver
as broken and makes no global claim about OpenWebRX or public SDRs.

## Why the path is closed

The two authorized sessions ended before measurement admission:

1. attempt 1 exposed a mismatch between the bare `status.json` profile name
   and the SDR-prefixed WebSocket label;
2. attempt 2 exposed the non-atomic property-delta semantics of OpenWebRX
   profile transitions.

Both are descriptive software failures, not physical rejections. Their
attribution remains frozen in the two attempt receipts.

Repairing those failures would still not supply the properties required by
the already-frozen visibility experiment. The official client/server path and
the earlier Berlin–Utrecht receipts establish that the waterfall wire product
does not expose a frame-generation timestamp or sequence number. Client
arrival time has no documented finite bound to the FFT event, and ordinary
frame delivery is not a same-path physical witness for an interpreted
absence. A third profile-transport attempt could characterize cadence, but it
could not close these causal cuts.

The endpoint capability state therefore remains unresolved while the composed
measurement path is insufficient. No threshold, pass, carrier or physical
claim was changed to obtain this terminal result.

## Change of abstraction

The next route is a model-conditioned two-station SatNOGS forward validation,
not another public-SDR client repair. SatNOGS is useful here because each
observation record binds a station coordinate, scheduled UTC interval, exact
transmitter and the TLE used by that observation. Raster timing, frequency
resolution, Doppler correction and ridge uncertainty still require explicit
admission before any orbital score.

A bounded metadata-only reconnaissance was limited to:

```text
NORAD 59051
transmitter dP82t5VrQC6hQDC39wxPo8
137900000 Hz
two API cursor pages
```

No waterfall, audio or decoded-data URL was opened.

It found one distinct development fixture with two `good` independent roots:

| Role | Observation | Station | UTC interval | Coordinates |
|---|---:|---|---|---|
| development A | 14904366 | OE9BKJ | 2026-08-29 13:21:42–13:29:17 | 47.4675556 N, 9.6692303 E, 412 m |
| development B | 14907984 | SA1CKW | 2026-08-29 13:22:44–13:32:58 | 57.276 N, 18.471 E, 38 m |

It also found a later, unopened four-root set on 2026-09-01 around
04:05–04:25 UTC. Those observations are only a candidate primary set. No pair
has been selected, no plan has been frozen and no RF product has been opened.

## Maximum next action

After this closure is integrated, the minimum next work is offline:

1. rank only the four predeclared primary roots by joint interval and frozen
   orbital-versus-null differential margin;
2. audit SatNOGS raster and artifact time/frequency transforms from official
   source and metadata;
3. freeze a model-blind ridge extractor using only the development pair;
4. freeze one primary pair before opening either primary waterfall.

If raster event time, frequency coordinates or transform lineage cannot
preserve the predicted distinction, stop with the SatNOGS path unadmitted.
Do not return to OpenWebRX and do not create a receiver catalog.
