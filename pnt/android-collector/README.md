# PNT Clock Collector (Android 10+)

A foreground research app that records native GNSS measurements and
authenticated Internet time together. Version 0.2 removes the need for Termux,
a PC or USB during acquisition; version 0.3 adds live acquisition diagnostics,
and version 0.4 imports the existing engine's PC report.
It retains the existing Raw format and Python
intake/replay. It does not adjust the device clock, authenticate local RF or
compute a timing/security verdict on the phone.

## Record and export

1. Install the debug APK below on the recording phone. Enable Location and grant
   **precise** location to PNT Clock Collector.
2. With Internet access and sky view, press **Start GNSS + NTS**. Keep the app
   visible; it holds the screen on. GNSS callbacks and NTS use the same
   `SystemClock.elapsedRealtimeNanos()` / CLOCK_BOOTTIME counter and capture ID.
   No other app is required. Do not reboot during acquisition.
3. The app stops after ten rounds against `ptbtime1.ptb.de` and
   `ptbtime2.ptb.de`, or when you press **Stop recording**. Round starts are
   scheduled three seconds apart; slow network attempts can extend the session.
4. Press **Export last session**, then save the ZIP using Android's document
   picker. It contains the original `pnt-clock-<id>.txt` and
   `pnt-nts-<id>.json`. Transfer the ZIP to the PC without modifying either
   original, then follow the reporting steps below.

This is transport acquisition. Server error, counter drift and effective
counter resolution remain **unknown**, never inferred from nanosecond API units
or observed agreement. Consequently the JSON is not yet a qualified
`android-time-compare` input; that command fails closed without its required
budgets. The session report makes missing assumptions explicit and reuses the
existing engine/replay. The [Android guide](../../docs/ANDROID_GNSS_TIME.md)
retains the earlier GNSS Logger/Termux conditional workflow separately.

## ZIP to PC report to phone

On the PC, from the repository root:

```console
python -m pip install -r requirements-pnt-time.txt
python -m pnt android-session pnt-session-<id>.zip --output phone-report.json
```

The default command writes an **INSUFFICIENT_EVIDENCE** report and exits with
code **2**. This is an expected usable report: timing assumptions are unknown,
so no numerical comparison runs. It includes the existing Raw intake, original
NTS attempts, failures, unattempted slots, terminal/partial status and reasons.
Empty recordings remain reportable; the ordinary `android-raw` command still
rejects them. Invalid ZIP names, duplicate members and mixed capture IDs are
rejected; no archive member is extracted. Inputs/reports are limited to 32 MiB,
without truncation or overwriting an existing output.

Copy `phone-report.json` to the phone's Downloads and press **Open PC report**.
The system picker requires an explicit read grant. The app checks the report's
member names, byte counts and SHA-256 against originals retained in its private
storage before displaying it. A changed or different recording is rejected.
Valid report bytes are retained privately; reopening the app rechecks the latest
report against its originals. Import does not change the selected recording,
start acquisition or upload data.

Version 0.4.1 checks Raw terminal totals and per-event row counts, and reconciles
every NTS endpoint/round/scheduled slot and terminal count before comparison.
Its acquisition protocol records endpoints, planned attempts and the exact
integer interval. For the known 0.2.0/0.3.0/0.3.1/0.4.0 native apps, the intake
uses their documented fixed PTB endpoint pair and labels this format compatibility
in the report. Unknown legacy schedules remain insufficient. These are
consistency checks on trusted collector declarations, not tamper-proof attestation.
Cache writes publish a complete report only after a sibling pending file is
renamed; an interrupted pending write cannot hide an earlier valid report.

The `pnt-android-session-report-v1` JSON is a presentation envelope containing
the existing intake and, when requested, the unchanged
`pnt-gnss-time-comparison-v1` result. It is not a parallel scientific verdict
format. Hash matching binds inputs; **PC arithmetic is trusted, not independently
replayed or authenticated by the phone**. Exact replay uses the embedded existing
comparison's `witness_report`, `receiver_capture`, UTC budget/source and optional
`temporal_association.maximum_span_ns` with `compare_receiver_capture`.
The Raw/NTS files in the ZIP are the source originals; the analysis copy never
overwrites their unknown assumptions or counter resolution.

To request a conditional numerical comparison, supply `--analysis-options
options.json`. No budget has a default; all are labeled uncalibrated:

| Required key | Meaning |
|---|---|
| `server_error_ns`, `rate_error_ppm`, `budget_source` | Explicit server UTC and monotonic rate assumptions, with provenance |
| `monotonic_resolution_ns`, `counter_resolution_source` | Effective counter tick bound and its independent source; API units do not establish it |
| `association_source` | Same device/boot assertion and provenance; not hardware attestation |
| `gps_utc_offset_seconds`, `time_scale_source` | External conversion valid for the recording, without crossing a leap second |
| `utc_error_ns`, `utc_error_source` | Receiver UTC bound and source, distinct from reported uncertainty |

Optional `epoch_alignment_error_ns` and `epoch_alignment_source` must be
supplied together. If absent, comparison records remain insufficient using the
existing engine. Optional `bracket_span_ns` enables its adjacent same-endpoint
brackets, retaining failed attempts. Missing/unclosed originals prevent a
comparison; failures and all originals remain visible. Do not choose bounds
from observed agreement. The app displays supplied assumptions and comparison
counts; overlap is not RF authentication, an accurate position or an ALLOW
decision. Geometry, attack attribution, network benefit and independent budget
qualification remain unperformed.

The app stops with an `ACTIVITY_STOPPED` terminal when hidden.
There is no automatic restart, fallback to callback time or overwrite of an
earlier recording. Files use unique capture IDs in private app storage. Export
copies the last session through Android's document picker; originals stay
in app storage. Do not uninstall or clear app data before transferring files.
Export requires a `content://` document recognized by `DocumentsContract` and an
explicit Android write grant for that exact URI. Direct filesystem destinations,
provider roots and non-document URIs are rejected before opening the output;
provider document IDs stay opaque. Version 0.3.1 adds this export validation.
The debug build also permits `adb shell run-as org.satelliterf.observatory.clock
ls files` and copying retained files through `adb exec-out run-as ... cat ...`.
Copy binary output without PowerShell's text redirection/re-encoding.

## Live acquisition diagnostics

Below the recording controls, the app shows actual measurement callbacks, Raw
rows and distinct satellites in the latest callback, with GPS counted separately.
Multiple signals from the same satellite count as separate rows, not satellites.
Empty callbacks remain visible. Last callback age refreshes once per second while
recording; after stopping it shows age at stop. This is a reception indicator,
not RF arrival time, a stale-data admission threshold or a native epoch replacement.

The panel reports missing/invalid native epoch, alignment uncertainty and FullBias
fields, plus hardware clock discontinuity count changes. The receiver's reported
alignment uncertainty remains a **68% estimate, not a qualified bound**, even when
reported as zero. Clock changes are observations without a cause or attack attribution.
The legacy `onStatusChanged` readiness notification is retained in the log but
does not establish reception; actual Raw callbacks determine the displayed state.

NTS progress retains cumulative failures and pending/unattempted slots, with the
latest completed result per endpoint. Long failure messages are shortened on
screen; full reasons and every attempt stay in the original JSON. Diagnostics
summarize existing snapshots/checkpoints without changing either file format.
They reset for each new recording; reopening the app retains files without
reconstructing a checked summary of earlier sessions. Timing comparison stays
**NOT ASSESSED**, budgets and counter resolution unqualified, including after
successful reception and NTS authentication. No security verdict is added.

## Authenticated time transport and retention

The native client requires TLS 1.3, platform certificate trust, endpoint identity
and `ntske/1` ALPN before deriving separate client/server RFC 8915 exporter keys.
Conscrypt provides TLS/exporters; Cryptomator's `siv-mode` provides AES-SIV-256.
The UDP exchange authenticates the NTP header, request identifier, origin,
nonce and cookie framing. No plain NTP fallback or address retry is attempted.
If NTS-KE does not negotiate another hostname, UDP uses its actual TCP peer.
The explicit NTP era is 0; there is no host-calendar era inference or wall-clock
comparison. TLS certificate validity still needs a plausible device calendar;
NTS does not solve its own calendar bootstrap.

All twenty planned slots are retained. Each completion checkpoints the JSON
with authenticated exchanges, failures and unattempted slots; orderly stop
adds its terminal. Certificates/response hashes and public peer addresses are
recorded, while session keys/cookies are not exported. Stop closes active sockets
and interrupts scheduled waits. Socket operations have five-second stage
timeouts; Android DNS resolution is OS-managed and can delay final stop. The
client checks cancellation/deadlines after resolution before connecting.

The two PTB endpoints share one authority; they are not independent clock roots.
Same-app association is provenance, not hardware attestation. Sudden process
termination can leave the last checkpoint in progress and a Raw file without
a terminal. Retain those partials; neither file alone proves completeness.
The network sends NTS protocol requests, never the collected GNSS file. There
is no upload service or public API.

## Observables and limits

- Native `GnssClock` fields: hardware `TimeNanos`, full/fractional bias, leap
  metadata, discontinuity count, uncertainty/drift fields and presence flags.
  `ChipsetElapsedRealtimeNanos` is a compatibility name for
  `GnssClock.getElapsedRealtimeNanos()`, **not** callback time.
- `ElapsedRealtimeUncertaintyNanos` and its presence flag. Android defines this
  as a receiver estimate with **68% confidence**; it is not an independent or
  deterministic bound. Missing optional fields stay blank, never zero-filled.
- Callback index, `SystemClock.elapsedRealtimeNanos()` at callback entry and
  after reading/copying clock and measurement fields, **before CSV formatting
  or file I/O**. Snapshot construction includes converting native values to strings.
  These delimit app work; they do not measure RF arrival, interrupt time or the
  entire callback duration. Their difference from the native epoch is
  diagnostic, not a calibrated association error.
- Session source revision, version/device/SDK, start counter and Android boot
  count (`-1` if unavailable). They describe collection, without proving a
  trustworthy receiver or independently bounding its clock.
- Every delivered Raw measurement, including non-GPS constellations and
  unsupported signals. Native long integers are decimal strings without float
  conversion. No coordinate, fix, Android wall-clock UTC or inferred bound is
  written. GNSS-derived time/measurements can still be sensitive; keep raw files
  private unless explicitly intended for publication.
- Each callback also has an `# Event` comment containing its index, the two
  callback counters, measurement count and the clock fields in the Raw header's
  clock order. Empty events retain their clocks. Status changes, errors and
  orderly terminals are comments retained by the existing intake.

Format: `# Format,pnt-android-clock-collector-v1`, one Raw CSV header, metadata,
event comments, Raw rows, and (on orderly closure) a terminal with reason,
stop counter and event/row counts. Each completed callback is flushed; storage
failure or process termination can leave a partial event or no terminal.
Such a file does not establish capture completeness. A file without any Raw
measurement is preserved but rejected by the existing intake. No file seals,
new replay or scientific authority are introduced; reuse input hashes and Git
provenance already present in the workflow.

The source revision defaults to `UNSPECIFIED`; set the build property to the
actual clean checkout's commit for a traceable acquisition. An embedded Git SHA
is build metadata, not an attestation of the installed binary. Record the APK
hash/version used alongside the existing acquisition notes.

## Build and checks

JDK 17, Android SDK platform 36 and Build Tools 35.0.0; set `JAVA_HOME` and
`ANDROID_HOME` or a local untracked `local.properties`. Gradle 8.13 and Android
Gradle Plugin 8.13.0 are pinned. The standard Gradle wrapper and distribution
checksum are included.

```sh
cd pnt/android-collector
./gradlew --no-daemon -PsourceRevision=<full-git-sha> testDebugUnitTest assembleDebug lintDebug
adb install -r app/build/outputs/apk/debug/app-debug.apk
```

Windows: use `.\gradlew.bat` with the same arguments. The APK is a development
build, not a Play Store release. Use the same local debug signing key to update an
installed build without clearing its data.

Linux/Windows collector CI builds, runs Java unit tests and Android lint, checks
the synthetic CSV/JSON with Python intake/UTC adapter/replay, then runs the native
client against local Python TLS/NTS servers. Shared synthetic vectors cover
tampering, replay, framing and negotiation. Loopback cases cover valid exchange,
wrong identity, untrusted certificate, missing ALPN, TLS 1.2, altered UDP and
timeout. Existing Python Linux/Windows CI is preserved.
This checks engineering behavior; device API availability and physical bounds
still require acquisition/qualification on the actual phone.

Dependencies: Conscrypt 2.7.0 (Apache 2.0), `siv-mode` 1.6.1 (MIT), Gson 2.13.2
(Apache 2.0). Native TLS libraries increase APK size. The debug APK has been
smoke-tested on Galaxy S21 FE / Android 16; the minimum API remains 29, without
claiming device testing across every supported Android version.

Sources: [GnssClock](https://developer.android.com/reference/android/location/GnssClock),
[callback status semantics](https://developer.android.com/reference/android/location/GnssMeasurementsEvent.Callback#onStatusChanged(int)),
[measurement callbacks](https://developer.android.com/reference/android/location/LocationManager#registerGnssMeasurementsCallback(android.location.GnssMeasurementsEvent.Callback,%20android.os.Handler)),
[elapsed realtime](https://developer.android.com/reference/android/os/SystemClock#elapsedRealtimeNanos()),
[AGP 8.13 compatibility](https://developer.android.com/build/releases/agp-8-13-0-release-notes),
[RFC 8915](https://www.rfc-editor.org/rfc/rfc8915.html),
[Conscrypt](https://github.com/google/conscrypt),
[siv-mode 1.6.1](https://github.com/cryptomator/siv-mode/tree/1.6.1).
