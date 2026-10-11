# Android window-side live transfer — 11 October 2026

Exploratory engineering trial of the optional native collector -> private PC
HTTPS receiver -> existing session monitor. This tests collection, transport,
retention and completion handling, without a numerical timing or RF claim.

## Setup and retained inputs

The Galaxy S21 FE (SM-G990B, Android 16) was stationary at the window, per the
user's confirmation, with Wi-Fi and the app visible. The window/sky geometry
was not measured. Collector **0.5.0** was built from
`f52e3cd4a4fa197ba3056885f6744fd78ececc9e`; its embedded source revision was
checked before installation. The live PC monitor recorded
`63e73d432e35be226ff657b63fe1a4a65db26a0e`, with a clean working tree.
Acquisition ran once using the existing ten-round, two-endpoint NTS schedule.

No analysis options were supplied. The receiver's required `1` ns local-counter
argument was an explicit unqualified transport-test parameter; it enabled no
numerical comparison and establishes no device bound. Original native budgets
and resolution remain unknown. No threshold, fitting or post-reveal tuning was
performed.

Full originals, the source ZIP, transfer events, every PC snapshot/result,
reports, APK identity and before/after hashes remain in the private local
directory `C:\temp\satellite-rf-window-transfer-2026-10-11`. Credentials and the
server key are private and unpublished. The receiver is no longer listening.

Capture ID: `c8a8b833-1a73-4f0e-9a66-71ebe488ab4f`.

| Original | Bytes | SHA-256 |
|---|---:|---|
| `pnt-clock-<id>.txt` | 415238 | `3df2030085743be865d3ef7aa96f029422c921f718ba9243c9e7da8b641ed766` |
| `pnt-nts-<id>.json` | 14175 | `890ba5983b1bb0fc56ba726eecf72234ec8f6f810c6102dc18004ca86deaa0d5` |
| `pnt-transfer-<id>.jsonl` | 6746 | `0a1ee2fc1245960e0a0f4202c1a7e4159b5b01bf68243ee32934a5881829f656` |

## Observations

- **43 GNSS callbacks / 1082 Raw rows**, with `SCHEDULE_COMPLETED` terminal.
  Intake normalizes **376 GPS rows**; **17** GPS rows have unresolved transmit
  time and **689** belong to unsupported constellations. All remain accounted
  for. This window location supplied actual GNSS measurements in this trial.
- NTS collection lasted **43.960 s**: **9/20 authenticated exchanges** and
  **11/20 unavailable attempts (timeouts)**. No replacement/retry acquisition.
  The lower authenticated fraction than the previous 13/20 outdoor trial is
  visible; these sessions are not an A/B reception or network comparison.
- **35/35 snapshot requests acknowledged**, zero retained transport failures,
  **35 PC monitor updates**. The final PC Raw/NTS pair is byte-identical to the
  retained phone originals. All **34 preexisting private app files** retain
  their original SHA-256 after installation and collection.
- Phone request duration (snapshot preparation through receipt, on the phone
  CLOCK_BOOTTIME counter): **220.400 / 304.673 / 436.277 ms**, min/median/max
  over 35 requests. PC read/processing/publication duration, measured separately
  on PC MONOTONIC: **169.920 / 211.252 / 296.691 ms** over 35 updates. These are
  engineering durations, not GNSS RF-to-operator alert latency or synchronized
  cross-device measurements.

Every result is **INSUFFICIENT_EVIDENCE** with the missing-analysis-budget reason;
no local/external/combined numerical outcome was computed. The initial snapshot
without Raw measurements also remains in the monitor history.

## Completion defect and correction

The acquisition and final upload completed correctly, but the original receiver
waited until its **300 s duration limit**: the monitor incorrectly coupled its
native-completion flag to the absence of analysis issues. The original summary
and all 35 updates are retained, including that false completion flag. An earlier
receiver setup expired while awaiting screen unlock with zero uploads; its
summary is also retained. Neither setup expiry is an extra GNSS acquisition.

`ac3384b4b429e9de1e6c08d2ee3333d96ab362f4` separates valid native completion from
optional numerical analysis. Missing budgets still mean insufficient evidence;
invalid terminals and rewritten history still cannot complete a session. A
separate replay of these already exposed final bytes now marks native completion
true while keeping the same insufficient status and empty numerical outcomes.
This is a replay, not a second live trial of the corrected stop behavior.

Synthetic regression tests also confirm that the receiver stops on a valid
unqualified closed pair, and that a changed completed NTS slot blocks completion.
The targeted transport/monitor suite passes **41 tests**, with one native
integration skipped there; that integration passed in its separate local run.
Before the completion correction, the full PNT/provenance suite passed **845
tests**, with six integration skips; Android build/lint and 36 Java tests also
completed (three environment-dependent integration skips in the standalone run).

The first Codex review's storage invalidation, private directory creation and
writer-lock findings were corrected in `f52e3cd`; Codex re-reviewed that commit
without new findings. Previously published scientific evidence is unchanged.

## Remaining scope

This validates useful GNSS reception at this window and real phone -> PC live
transport for one short session. It does not qualify timing budgets, position
accuracy, RF authenticity, spoofing attribution or P2/P3. The phone currently
shows transport receipts; delivering the existing numerical outcomes live to
the phone, including revisions and operator timing, remains the next increment.
The existing ZIP/report import path remains available separately.
