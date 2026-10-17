# Synthetic Android session example

`android-session-synthetic.zip` is a small, invented native session for the
[diagnostic quick start](../../docs/DIAGNOSTIC_QUICKSTART.md). It is not a phone
recording, a sky observation or evidence of timing accuracy or attack detection.

Its two members contain unchanged output bytes from the existing Android unit
tests at source commit `d11c24a685d4070210d1bd7f2dd3704fe23ce5a5` (collector 0.6.0):

- `pnt-clock-synthetic-ci.txt`: `CaptureLogTest.generateSyntheticIntakeFixture`,
  byte-identical to the shared [Raw fixture](../tests/fixtures/android_collector/synthetic-collector.txt).
  It includes four Raw rows, another constellation, missing timing metadata and
  empty callbacks, all retained by the intake.
- `pnt-nts-synthetic-ci.json`: `NtsCaptureTest.retainedScheduleHasFailuresUnknownBudgetsAndNoRetry`,
  with four planned slots: three invented `AUTHENTICATED_EXCHANGE` records and
  one invented timeout. No network probe took place. Server/rate budgets and
  counter resolution remain unknown.

The Raw/NTS metadata say `SYNTHETIC_ONLY`; the exchange authentication labels
are test inputs, not verified network evidence. The test scheduler's one-ns
interval is synthetic, not the app's real acquisition schedule. ZIP timestamps
are fixed packaging metadata, not an acquisition time. The native test uses
concurrent endpoints; regenerated NTS counter ordering can differ without
changing the intended example.

Run from the repository root, with Python 3.13:

```console
python -m pnt android-session pnt/examples/android-session-synthetic.zip --output demo-report.json
```

No pip packages or Internet connection are required for this offline command.
It writes `INSUFFICIENT_EVIDENCE`, exits with code 2 and preserves the originals,
missing assumptions and failed slot in the report. It does not run a numerical
timing comparison. Use a new output filename when repeating it.

The distributed example runs through the existing session CLI regression on
Linux and Windows. It uses the existing intake and report schema; no separate
executor, verdict, authority manifest or replay mechanism is introduced.
Original scientific experiments are unaffected. To regenerate the source
members, run the named native tests using the build guide, then package the
unchanged output bytes under the same member names with standard `zipfile`.
