# PNT Clock Collector (Android 10+)

A small foreground app for the next clock diagnosis on the phone. Google GNSS
Logger remains sufficient for the first intake, but the installed 3.1.1.3 log
did not include GNSS epoch-alignment uncertainty. This collector records the
missing observables without changing NTS, the Python comparison or its budgets.
It uses Android platform APIs and has no runtime library or network dependency.

## Record and export

1. Install the debug APK below on the recording phone. Enable Location and grant
   **precise** location to PNT Clock Collector.
2. Press **Start recording** outdoors with sky view. Keep the app visible; it
   holds the screen on. Use split screen with Termux, or the already configured
   remote Termux access, to run the same-phone `android-time-probe` from the
   [Android guide](../../docs/ANDROID_GNSS_TIME.md). A USB cable is not required
   for collection. Do not reboot between GNSS and NTS acquisition.
3. Press **Stop recording**, then **Export last file**. Preserve the original
   GNSS file and NTS JSON. Import the exported file with `python -m pnt android-raw`
   and use `android-time-compare` and its existing replay as before. Same-phone,
   same-boot association remains an explicit caller assertion.

The app stops with an `ACTIVITY_STOPPED` terminal when hidden, including when
Termux takes the whole screen; it does not pretend to collect in the background.
There is no automatic restart, fallback to callback time or overwrite of an
earlier recording. Files use unique capture IDs in private app storage. Export
copies the selected last file through Android's document picker; originals stay
in app storage. Do not uninstall or clear app data before transferring files.
The debug build also permits `adb shell run-as org.satelliterf.observatory.clock
ls files` and copying retained files through `adb exec-out run-as ... cat ...`.
Copy binary output without PowerShell's text redirection/re-encoding.

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
the generated synthetic CSV against the fixture, then exercises the existing
Python intake/UTC adapter/replay. Existing Python Linux/Windows CI is preserved.
This checks engineering behavior; device API availability and physical bounds
still require acquisition/qualification on the actual phone.

Sources: [GnssClock](https://developer.android.com/reference/android/location/GnssClock),
[measurement callbacks](https://developer.android.com/reference/android/location/LocationManager#registerGnssMeasurementsCallback(android.location.GnssMeasurementsEvent.Callback,%20android.os.Handler)),
[elapsed realtime](https://developer.android.com/reference/android/os/SystemClock#elapsedRealtimeNanos()),
[AGP 8.13 compatibility](https://developer.android.com/build/releases/agp-8-13-0-release-notes).
