# GFZ NAV content during a recorded JammerTest episode

**The new witness works, but matching NAV does not detect this attack.** The
already-exposed JammerTest 2.1.1 capture has three complete local CEI cycles:
G17 and G21 agree with GFZ on all 54 compared fields; G14 declares a future
issue absent from the same-day archive. Under the existing provisional capture
timeline, G21's matching cycle falls inside the official spoofing ramp. No
field contradiction is found in the two comparable cycles, and the missing
issue is insufficient evidence. None of these outcomes is an RF allow/block
decision. This is exploration on a previously exposed recording, not a blind
confirmation or a detection-rate experiment.

## Inputs and comparison

Local data are the [previously retained captured GPS messages]
(PNT_NAVIGATION_JAMMERTEST_211.md), from the [public dataset][capture]. All
207 local cycles remain accounted for: **3 complete and 204 incomplete**.
Two transport-corrupt packets remain explicitly excluded under the earlier
recovery contract. The entire local file was decoded again during development
and its frame/cycle trace matched the unchanged historical report. CI replays
the three complete cycles from their nine original UBX packet excerpts;
the other cycle denominators and payloads remain in that historical report.

The [GFZ archive for 2024 day 255][gfz] contains 32 daily members,
3,348,480 bytes, SHA-256
`a50e06b6da62b95f85a55ab5a3eae74b5e67f1c087c0828a2be3e1e3ea5d915b`.
All daily data for **every satellite with a complete local cycle** are retained:
G14/G17/G21, 308,831 compressed bytes. This is selection by comparability,
not by agreement. The [input provenance](../../pnt/tests/fixtures/gfz20240911/provenance.json)
also binds the unchanged full NOAA same-day NAV used previously. GFZ is one
provider aggregate with CC BY 4.0 attribution; station multiplicity does not
constitute independently accessible votes or independent receiver clocks.

The shared `read_gfz_navbit_issues` reader validates daily NetCDF layout,
date/week/PRN, ordered six-second slots, word parity and HOW/time consistency.
It scans the **entire three retained daily files**, without a victim-HOW
window or a nearest-issue replacement. Of 43,200 subframes, all pass parity;
the 8,640 CEI cycles yield 8,637 structurally decoded issues and three
`UNUSABLE_ISSUE` cycles with inconsistent IODE/IODC. Those failures stay in the
report with their original source rows. Parity does not guarantee a coherent
three-subframe issue. Missing/bad pieces cannot be borrowed from another cycle.
The daily grid retains all 2,880 expected CEI cycles per satellite, including
wholly absent SF1–SF3 at the day's edges or between received messages. Such
cycles are `INCOMPLETE_CYCLE`, with no source rows or fabricated issue. This
correction for sparse members leaves the complete retained files' report bytes
and scientific outcomes unchanged.
Unavailable URA/TGD are retained as unqualified diagnostics, not usable bounds.

The existing V2 representation comparator receives every decoded issue,
including duplicates and the future-dated local G14. It does not change any
field interval, candidate rule, threshold or historical outcome.

| Local cycle | Declared toc, GPST | GFZ matching cycles | GFZ content outcome |
|---|---|---:|---|
| G17, 17 | 2024-09-11 08:00:00 | 240 | `SAME_BROADCAST_FIELDS`, 27 fields |
| G21, 140 | 2024-09-11 07:59:44 | 110 | `SAME_BROADCAST_FIELDS`, 27 fields |
| G14, 161 | 2024-10-01 14:00:00 | 0 | `MISSING_ISSUE` |

NOAA alone leaves the two matching issues `REPRESENTATION_UNQUALIFIED`, notably
with coarse zero clock-acceleration intervals. Joint GFZ/NOAA intersection
uniquely resolves them and retains the same two agreements, with no external
conflict. This differs from the earlier CTTC conversion conflicts: both
sources' individual results remain explicit. No NOAA decimal precision is
invented and no source is silently corrected or omitted.

## Event association and limits

The unchanged [official-window extract](inputs/pnt_jammertest_211_windows.json)
places the ramp at 07:00:59–07:37:07 GPST. Reusing the original 5 Hz RAWX
packet-order model and its one inferred missing tick gives these **preceding
RAWX tick brackets**, not independently timed SFRBX reception timestamps:

| Cycle | Provisional brackets, GPST | Scheduled segment |
|---|---|---|
| G17 | 06:59:05.997–06:59:17.997 | Pre-event, not certified benign |
| G21 | 07:12:05.997–07:12:17.997 | Logged ramp |
| G14 | 07:24:12.997–07:24:24.997 | Logged ramp |

[Retained associations](../../pnt/tests/fixtures/gfz20240911/capture_association.json)
include original packet/epoch indices and preceding RAWX payloads. The full
12,518-packet timeline requires the original external UBX file to reproduce;
CI checks retained payload time decoding, tick arithmetic and classification
against the unchanged official window. Cadence, initial victim-derived time
and the missing-tick assumption supply no independent absolute-time witness.
The prior large local clock jumps remain visible and are not retimed away.

The two G21/G17 content agreements and 240/110 repetitions are not independent
attack trials, receiver-hours or detection probabilities. G14's missing issue
does not prove that RF came from a spoofer. Neither source independence,
freshness, position/range authenticity, attack attribution nor a P2 advantage
over local controls has been established. This sparse capture cannot settle
false alarms or incremental detection benefit. Stop expanding this episode
administratively; the next useful evidence must challenge the geometric or
timing observable that a stronger PNT claim actually needs. A NAV match alone
cannot serve as that observable.

## Reproduction

```console
python -m pytest pnt/tests/test_gfz_recorded_attack.py research/exploratory/tests/test_pnt_rawx_recovery.py -q
```

The [machine result](results/pnt_gfz_recorded_attack_v1.json.gz) retains all
GFZ cycle outcomes, individual/joint representation results, input hashes,
previous-capture denominators and provisional associations. Uncompressed
JSON: 3,731,958 bytes, SHA-256
`489512ba6f47248ec17fa777a2a5e864d961e6ed02a8a1c3e9b5e66880ee4fea`.
The new reader is a reusable local-file API, not a new CLI, downloader,
experiment executor, authority or seal. The optional RAWX timeline collector
leaves prior numerical outputs unchanged. Historical results are untouched.

[capture]: https://zenodo.org/records/15911589
[gfz]: https://isdc-data.gfz.de/gnss/GNSS-GPS-1-NAVBIT/y2024/GNSS-GPS-1-NAVBIT+2024_255_A.tar
