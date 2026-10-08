# Yunnan: native-epoch local/network comparison

Exploratory development, completed 9 October 2026. All local source values were
already exposed in the [recording intake](PNT_YUNNAN_RECORDING_INTAKE.md).
This extends that result separately; it changes no historical outcome, Android
grid tolerance, detector threshold or prospective boundary.

## Physical result

**Two contemporary references are now available, and the native-epoch model
evaluates 204/240 requested epochs. This does not demonstrate network detection
gain.** The combined residual is smaller in 91 evaluated epochs and larger in
113. The global median changes from 31.63 m locally to 30.33 m combined, while
the post-disturbance median worsens from 18.69 m to 26.85 m. These are model
residuals on identical common satellites, not position errors or detection rates.

The references are JFNG (China) and CUSV (Thailand), approximately 1,307 km and
1,272 km in ECEF chord distance from the published local coordinate. Both have
GPS C1C at all 2,880 daily 30-second epochs. CUSV lacks 180 individual requested
codes; these gaps remain in source admission. KUNM was absent from the inspected
ESA/BKG daily directory. Neither distant station qualifies transfer of local
ionospheric or multipath errors. Distinct markers do not establish independent
clock systems, distribution paths or GNSS products.

The exact native NAV join resolves 3,593 PVT/CLOCK pairs in hour 12, with seven
missing CLOCK messages. Hour 18 has 3,530 pairs, 55 CLOCK epochs without PVT and
15 PVT epochs without CLOCK. For example, PVT collected under `18:00:02` pairs
with CLOCK collected under `18:00:03`, both declaring `iTOW=381619000`.
The first PVT epoch, `381617000`, has no CLOCK counterpart; it stays missing.
Collection labels and array indices are never used to establish a NAV epoch.

## Time and comparison rules

The [u-blox interface description][interface] identifies RAWX `rcvTow` as
receiver-local time approximately aligned with GPS, and NAV `iTOW` as the
navigation epoch. The [integration manual][integration] explains that equal
NAV `iTOW` values identify one navigation solution; their validity is separate.
Our exact join is scoped to each continuous one-hour acquisition segment,
shorter than a GPS week. Ambiguous duplicates and unmatched messages are kept.
**RAWX-to-NAV clock conversion remains unqualified:** neither `clkB` nor PVT
calendar fields silently replaces RAWX time. Matching NAV messages does not
make their receiver-derived time independent or authentic.

For each requested reference epoch, choose the unique nearest original RAWX
tag within half the local one-second sampling interval (0.5 s). Selection uses
timestamps, not code magnitude, residuals, fix status or attack success. Reject
ties, duplicated native epochs and missing coverage. No interpolation, clock
correction, host-time substitution or widened existing 1 ms grid is used.
Actual selected tag offsets range from -11 ms to +39 ms. The association
interval is an engineering selection rule, **not a physical timing error bound**.

The shared `pnt.fixed_site.evaluate_epoch` now accepts optional per-receiver
measurement times. Orbit selection and clock fitting use each original time,
with separate navigation records per receiver. Default simultaneous-epoch
calls retain their former output. The model already treats receiver clock as
a nuisance in emission/reception geometry. Its fit is not independent UTC.
Native timestamp serialization is retained; datetime evaluation has microsecond
precision. The public coordinate is converted from WGS84 latitude/longitude
and ellipsoidal height, never estimated from victim PVT. Its survey error is
unspecified. Reference coordinates come from their RINEX XYZ and antenna offset.

Compare GPS C1C only, using the existing healthy broadcast NAV selection,
two-hour age cap, 10-degree elevation mask, minimum four common satellites,
median clock fit, Earth rotation and troposphere model. Ionosphere, signal group
delay and hardware code biases remain uncorrected. The shared common set depends
on all receivers' coverage; standalone fits with different sets remain separate.
No target local values enter either remote clock fit.

The scalar reported below is the maximum absolute satellite difference relative
to the minimum common GPS PRN. Local uses the local residual vector, network
uses CUSV-minus-JFNG, and combined uses local-minus-mean-reference. All three
use exactly the same evaluated epochs and satellites. No threshold is fitted.

Requested reference GPST windows are `[04:00:30,05:00:30)` and
`[10:00:30,11:00:30)`, 120 epochs each, covering the retained native hours.
Of 7,124 RAWX messages, 248 declare time outside 21 December and are retained
as unavailable for this day's geometry, without repairing them. Of 240 grid
requests, 227 have a local timestamp association; 13 do not. Twenty-three more
lack four common admitted satellites, giving 36 unavailable comparisons in all.
Every request and every native GPS L1 code disposition is in the retained replay.

## All descriptive windows

Window names follow paper Table 13 and original collection labels. They record
transmitter activity, not receiver capture or successful attack. Before,
between and after intervals are not certified benign. The 13 requests without
a RAWX association have no independently established host-window assignment;
they remain explicitly unassigned, rather than being dropped or invented.

| Collection interval | Associated / evaluated | Median local m | Median combined m | Smaller / larger combined |
|---|---:|---:|---:|---:|
| Before first Table 13 attack | 65 / 65 | 40.54 | 37.33 | 61 / 4 |
| Attack 1 | 4 / 0 | unavailable | unavailable | 0 / 0 |
| Between 1 and 2 | 3 / 3 | 35.75 | 34.58 | 3 / 0 |
| Attack 2 | 5 / 0 | unavailable | unavailable | 0 / 0 |
| Between 2 and 3 | 5 / 5 | 56.13 | 55.11 | 2 / 3 |
| Attack 3 | 22 / 13 | 31.72 | 31.71 | 9 / 4 |
| Between 3 and 4 | 2 / 2 | 31.45 | 31.82 | 0 / 2 |
| Attack 4, retained part | 6 / 1 | 31.20 | 31.58 | 0 / 1 |
| Hour after logged disturbances | 115 / 115 | 18.69 | 26.85 | 16 / 99 |

The largest local difference is **1,517,252 m**, and combined is **1,517,259 m**,
at collection label `18:50:43`, driven by G17. Its original L1 code declares
`prValid=1`, C/N0 21 dB-Hz and lock time zero. It is finite and positive, so
the declared code-admission rule retains it. Smaller large G14/G03 cases also
remain. This is already a local inconsistency, not proof of a new network-only
detector, attack attribution, or a benign false alarm. No post-reveal C/N0,
lock-time or residual filter was added to improve the result.

## Reproduce and what this resolves

Original contemporary files, source paths and hashes are documented in the
[input directory](inputs/yunnan20231221/README.md). The 329 KB compressed
[result](results/pnt_yunnan_native_network.json.gz) retains all NAV associations,
7,124 RAWX dispositions and 240 detailed comparisons, without a new replay layer.

```console
python -m research.exploratory.pnt_yunnan_network yunnan-network.json.gz
python -m pytest pnt/tests/test_ublox.py pnt/tests/test_fixed_site.py research/exploratory/tests/test_pnt_yunnan_network.py -q
```

This resolves archive access and software support for distinct native measurement
epochs. It provides an actual exposed RF-recording/network comparison and a
reusable NAV association primitive. Synthetic regressions exercise timestamp
offsets, receiver-specific ephemeris selection, gaps and duplicate rejection;
real replay checks preserve physical residuals within 0.1 mm across platforms.
The original intake replay remains unchanged.

P2 is still open: there is no independent event-clock bound, surveyed local
uncertainty, certified benign population, qualified detector or demonstrated
network benefit at equal false-alarm rate. Residual reduction alone cannot
supply those claims. The useful next physical question is whether external
witnesses expose a local geometric inconsistency that the same local-only
control misses. This recording comparison has not established that advantage;
extra administrative gates or tuning its filters cannot establish it.

[interface]: https://content.u-blox.com/sites/default/files/documents/u-blox-F9-HPS-1.30_InterfaceDescription_UBX-22010984.pdf
[integration]: https://content.u-blox.com/sites/default/files/ZED-F9P_IntegrationManual_UBX-18010802.pdf
