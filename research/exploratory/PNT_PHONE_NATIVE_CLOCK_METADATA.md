# Native Android GNSS epoch metadata — 10 October 2026

The missing observable is now recorded: the Galaxy S21 FE reports native
GNSS/elapsed-realtime alignment uncertainty of **7.001176–7.001243 ms** in every
delivered callback. This is the receiver's estimate with **68% confidence**,
as defined by [Android's API](https://developer.android.com/reference/android/location/GnssClock#getElapsedRealtimeUncertaintyNanos()),
not an independent deterministic bound. It is wider than the unchanged **1 ms**
development association assumption. That assumption remains unqualified;
the new field does not license fitting a larger budget to this capture.

This exploratory instrumentation diagnosis follows the
[original clock decomposition](PNT_PHONE_CLOCK_DIAGNOSTICS.md), using the new
[PNT Clock Collector](../../pnt/android-collector/README.md) and existing NTS,
intake, UTC comparison, local continuity and replay. No new seal/executor or
scientific authority was added. P2 remains open.

## Acquisition and retained outcomes

Galaxy S21 FE SM-G990B, Android 16/API 36, stationary outdoors according to the
operator, Wi-Fi with USB disconnected. Native collector commit
`cce5b79246`, before the later API-29 collection-initializer fix; the full commit
and APK hash are in the [aggregate](results/pnt_phone_native_clock_metadata_v1.json).
That fix does not alter the Android-16 capture. Phone-local NTS uses the
retained source `8571827fb5d48866565cc81df4fda20c8da4c10e`, Python 3.13.13 and
the prior Android dependency pins. Same-phone/boot is a caller observation,
not an authenticated boot identity. No GNSS coordinates/fix are logged.

Before new values, retain the prior development assumptions: server UTC and
GNSS UTC error 1 ms each, association 1 ms only for the separate development
case, rate 100 ppm, counter resolution 1 ns and maximum NTS bracket span 15 s.
The unknown-association case remains separate. GPS-UTC stays 18 s, checked
against [IERS Bulletin 72's leap table](https://hpiers.obspm.fr/iers/bul/bulc/Leap_Second.dat).
Twenty NTS attempts were scheduled, ten rounds at 3 s with PTB1/PTB2 and 5 s
stage timeout; no failure replacement or hidden retry.

| Retained observation | Result |
|---|---:|
| Delivered callbacks / empty callbacks | 141 / 0 |
| Native epoch and its uncertainty present | 141/141 for both |
| Raw rows / normalized GPS / other constellations counted | 3,199 / 1,463 / 1,736 |
| Distinct GPS clock epochs | 140 |
| NTS authenticated / unavailable | 13 / 7 |
| NTS acquisition duration | 46.301065086 s |
| Native epoch to callback-entry gap | 519.580260–666.168385 ms |
| Callback snapshot duration (excludes CSV formatting/I/O) | 0.340521–2.949063 ms |

Callback entry is about half a second after the native epoch; it would be an
unsuitable replacement timestamp. This gap is not the uncertainty of the
native association and does not provide an independent bound. Both PTB
endpoints share one authority and are not an independent quorum. The initial
indoor engineering smoke has zero callbacks/Raw, an explicit terminal and a
retained file rejected by the existing intake; a stop-on-hide check also
retains an `ACTIVITY_STOPPED` terminal. No empty attempt is relabeled as success.

## Replay under unchanged assumptions

Under the development 1 ms association assumption, **496/1,463 GPS rows,
47/140 distinct clock epochs**, are inside the NTS acquisition window. Only
**316 rows / 30 epochs** have compatible external temporal support: 12 rows
inside individual exchanges and 304 through same-endpoint brackets. The other
**1,147 rows / 110 epochs** lack temporal support; 967 rows are outside the
admitted window and 180 are admitted without supported comparisons.

The unchanged local control retains **137 inconsistent rows / 13 epochs**;
349 rows are locally compatible and 977 insufficient, including anchors.
Among the externally supported rows, 74 rows / seven epochs are locally
inconsistent and 242 locally compatible. Hardware-minus-counter change on
the original admitted anchors spans **−10.285721 to +2.555376 ms**. These are
conditional diagnostics, not a physical-cause attribution or false-alarm rate.
Repeated satellite rows and distinct epochs are not independent trials.

With association unknown, **all 1,463 rows / 140 epochs remain insufficient**.
Reported uncertainty and callback counters do not change admission, budgets or
verdicts. No offsets beyond the original zero case were analyzed for this new
capture; no RF manipulation or confirmation claim was made.

The intake, both comparison reports and original-case diagnostic replay
**exactly** through existing APIs, excluding only CLI path/hash envelopes.
The public aggregate retains all counts, failures, assumptions and hashes;
raw inputs remain private on the PC/phone and full replay reports on the PC.
It is not a public benchmark corpus. Acquisition closed normally with `USER_STOPPED`; temporary
SSH authorization/listener, ADB mappings and loopback HTTP were removed, apps
stopped and wireless debugging disabled. Earlier scientific inputs/results
remain unchanged.

The useful next question is whether a defensible timing model can qualify the
association for the intended security claim. The reported 7 ms already makes
the 1 ms development assumption a poor basis for that claim. Repeating the
same benign capture or widening its budget until it passes would not answer
that question.
