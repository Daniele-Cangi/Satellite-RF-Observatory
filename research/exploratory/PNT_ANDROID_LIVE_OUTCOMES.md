# Android live PC outcome delivery — 11 October 2026

## Scope and retained inputs

One **exploratory engineering acquisition** on a stationary Galaxy S21 FE
(SM-G990B, Android 16) at the user's window, with Wi-Fi Internet and the app
visible. The user confirmed readiness before Start. No RF challenge, numerical
analysis options, budget qualification or prospective security claim.

Collector **0.6.0** and PC receiver used clean source
`17df8593d92d593108a6829bbb46609dc346afbf`. The installed APK's hash and
installation receipt are retained privately. No previous recording was uploaded.
The earlier [0.5.0 transfer trial](PNT_ANDROID_LIVE_TRANSFER.md) remains unchanged.

Capture: `207ae41b-087b-46e6-9a41-d06fe80923e4`.
Full originals, all monitor snapshots/results, received summaries, UI timestamps,
final UI dump, installation record and before/after hashes remain privately in
`C:\temp\satellite-rf-live-outcomes-2026-10-11`. No token, private key, native
phone epochs or device fingerprint is published here.

| Original | Bytes | SHA-256 |
|---|---:|---|
| `pnt-clock-207ae41b-087b-46e6-9a41-d06fe80923e4.txt` | 545133 | `02923cc0a6c3bad449e274958f7472bc81987d9b54af4235157997b3f9f6e861` |
| `pnt-nts-207ae41b-087b-46e6-9a41-d06fe80923e4.json` | 15771 | `730dd345503ff9fa1c2f877fea15984219584ebf96c7f7539e5ffd2b101b7586` |
| `pnt-transfer-207ae41b-087b-46e6-9a41-d06fe80923e4.jsonl` | 75169 | `c975c1ad89cdaea9fca13607f1ba0703656adfcbbef774bd50bc970f68df1a24` |

## Outcome, including unavailable evidence

- **49 GNSS callbacks / 1,419 Raw rows**: 509 normalized GPS and 910 unsupported
  constellation rows retained. This is reception accounting, not accuracy.
- Native NTS acquisition: **49.280983731 s**, **11/20 authenticated exchanges**
  and **9/20 unavailable**, all `SocketTimeoutException: Poll timed out`.
  No replacement attempts or rerun acquisition.
- **37/37 requests acknowledged**, **zero transport failures**, **37 PC updates**
  and **37 `UI_TEXT_APPLIED` events**, correlated through phone request counters.
- Both final native files are byte-identical between phone and PC.
  All **37 preexisting private files** retained identical hashes through
  installation and acquisition; the new three files bring the total to 40.
- Every response remains **INSUFFICIENT_EVIDENCE**, with zero numerical
  local/external/combined outcomes and the explicit missing-budget reason.
  The first empty-GNSS snapshot also remains retained. No numerical budget was
  selected from this run. The explicit `1 ns` local resolution argument is an
  unqualified receiver configuration, not an established phone bound.
- The receiver stops at **SESSION_TERMINALS_OBSERVED**, with native completeness
  true and scientific evidence still insufficient. A fresh UI dump confirms
  **FINAL PC SNAPSHOT**, the matching capture ID and insufficient status.
  There is no duplicate upload after receiver exit or false late transport error.

| Engineering duration in this run | Minimum ms | Median ms | Maximum ms |
|---|---:|---:|---:|
| Phone snapshot/request start -> parsed receipt | 261.745989 | 409.469010 | 526.780937 |
| Phone receipt -> Activity text assignment | 4.481823 | 7.311823 | 12.311458 |
| PC read/analysis/result publication | 199.730300 | 254.625000 | 370.922100 |

Phone durations use `CLOCK_BOOTTIME`; PC processing uses `PC_MONOTONIC`.
Counters are **not mapped across devices**. Text assignment includes the UI
queue, but is not proof of frame presentation or operator observation; text
may be below the visible viewport. These are not physical attack onset,
GNSS-callback-to-alert latency or evidence of faster detection. All observed
durations and unavailable NTS slots remain retained; no stable performance
improvement is inferred by comparing this single run to an earlier trial.

## Software checks and remaining scope

The complete PNT/provenance suite passes **852 tests**, with six optional
integrations skipped. Android build, lint and **39 unit-test cases** pass
(four environment-dependent cases skipped). A separate native Java -> local
HTTPS -> Python integration passes all 30 Python transport cases and exercises
the real existing engine's inconsistent -> inconclusive revision, unavailable
current state with historical presentation, and malformed-input clearing.
It also retains the complete-pair worker shutdown and TLS identity tests.
Those scenarios are **synthetic**, not observations of an attack on this phone.

The app now closes the engineering loop acquisition -> PC monitor -> phone
presentation using existing outcomes and replay evidence. Independent timing
qualification, useful benign/challenge benefit and physical RF/security
claims remain open. This run adds no detector, scientific threshold, endpoint
vote, ALLOW/BLOCK decision or operational service qualification.
