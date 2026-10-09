# Yunnan recording: usable original observations, unresolved temporal alignment

The search found an accessible fixed-receiver recording with actual code,
phase, Doppler, quality/lock flags, PVT and receiver clock messages. We acquired
two hours from [Yunnan University, Mendeley Part III V3][data] rather than
building an adapter for an unavailable dataset. The [source excerpts and
attribution](inputs/yunnan20231221/README.md), [ordinary analysis module](pnt_yunnan_intake.py) and [result](results/pnt_yunnan_recording_intake.json)
retain the observations and allow offline reproduction. **This qualifies
input availability and limitations; it does not demonstrate network benefit.**

## Selection and observation scope

We chose host-file hours 12 and 18 on 21 December 2023 before decoding their
original archives: the first available hour in the published disturbance
period and the first complete hour after it. The detailed [article Table 13]
[paper] was read after the first data inspection. The entire selected hours
remain included, without selecting successful receiver captures.

Table 13 lists attacks 1–4 starting at 12:32:30, 12:38:41, 12:44:05 and
12:57:00. Attack 4 ends at 13:02:00 and is only partially captured here.
We count half-open windows and keep all intervening periods. The article's
broader text says spoofing starts at 12:00; the detailed log starts later.
Neither an interval without a logged transmission nor hour 18 is promoted
to an independently certified benign control. Recovery effects can persist.

The article declares receiver latitude/longitude 25.0571632/102.6987051 and
ellipsoidal height 1896 m, without an independent survey uncertainty. Those
coordinates are metadata, not a qualified position oracle. GPS `gnssId=0,
sigId=0` denotes L1 C/A; `sigId=3` denotes L2C and must not become C2W.

## What the original messages show

| Quantity | Hour 12 | Hour 18 |
|---|---:|---:|
| RXM-RAWX messages / expected acquisition seconds | 3600 / 3600 | 3524 / 3600 |
| GPS L1 source measurements | 20,408 | 20,684 |
| L1 codes with valid flag and finite positive value | 18,634 | 20,684 |
| Valid-flag L1 codes with unusable numeric value | 1774 | 0 |
| Epochs with fewer than four usable L1 codes | 520 | 0 |
| Receiver clock-reset messages | 17 | 0 |
| Receiver-declared UTC date differs from host-file date | 248 | 0 |
| Messages within the existing 1 ms / 30 s GPST grid | 0 | 0 |

The native first epoch has week 2293 and `rcvTow=360017.007`, giving receiver
GPST 04:00:17.007, whereas its host label is 12:00:00. With its declared
18 leap seconds, the offset is eight hours plus 0.993 s. This suggests a
local timezone and collection delay; it does **not** qualify the host clock.
At host 12:33:33, receiver GPST becomes **23 December 00:01:03.207**. We retain
this excursion rather than retiming it to the acquisition day.

All four selected logged attack intervals contain epochs lacking four usable
GPS codes: 120/270, 96/159, 190/705 and 83/180, respectively. The first three
also contain reset/date anomalies. These are descriptive local symptoms, not
detection rates: transmission activity does not prove receiver capture, and
no false-alarm threshold or qualified benign denominator exists here. They
prevent presenting this recording as proof that only an Internet witness
reveals the attack. We have not tested whether the network adds information
on its remaining locally usable epochs.

## Processed data must not be treated as synchronized native measurements

The processed PVT file contains 3600 position/timestamp entries, **3593 clock
entries** and **3597 DOP entries**. Joining these arrays by row number would
hide gaps and change alignment. In the retained hour 18 native files,
17 RAWX `start_time` values disagree with their filenames and seven are
duplicates; 1581 of 3530 PVT/clock pairs sharing a filename label declare
different `iTOW`. The analysis preserves filename and message labels separately
and reports those disagreements. Matching host labels is not enough to
establish a shared measurement epoch.

The first processed G31 L1 entry also stores native phase
119555602.08583662 cycles under `doMes_G1`, and native Doppler
−911.17236328125 Hz under `cpMes_G1`. This directly checked sample has swapped
field identities. No general correction of the processed archive is assumed;
any future physical calculation should read the original RAWX fields.

The first analysis attempt stopped on duplicated message `start_time`; the
next stopped on valid-flag codes with unusable values. The final description
retains files by their original names and counts rejected values explicitly.
Neither repair alters source bytes or turns these measurements into valid codes.

## Decision and concrete next work

**Candidate retained for development; not admitted as the decisive P2
comparison.** The present grid-based diagnostic admits none of these native
timestamps. Rounding them, substituting host time, or silently widening the
tolerance would introduce an unmeasured model error. No engine tolerance,
historical outcome or detector threshold has been changed.

BKG's 2023/355 observation and navigation directories were attempted through
HTTP clients and the browser, and returned connection resets. This is an
access failure in this run, not evidence that contemporary references do not
exist. We have not acquired two witnesses or measured common signal coverage.

Before a geometry comparison, resolve actual measurement epochs and PVT/clock
association using the native `rcvTow`/`iTOW`, treating date excursions and gaps
explicitly. Then obtain two same-signal contemporary reference observations
and evaluate each receiver at its actual epoch with a justified alignment
error. Reuse the existing model and comparison primitives; do not add another
seal or executor. Evaluate local and combined diagnostics on the same admitted
epochs and retain the discarded epochs. Independent absolute-time verification
and population false-alarm claims remain unavailable without their witnesses.

Reproduce without network access, using a new output path:

```console
python -m research.exploratory.pnt_yunnan_intake yunnan-intake.json
python -m pytest research/exploratory/tests/test_pnt_yunnan_intake.py pnt/tests -q
```

Other discovery outcomes on 8 October: [CG-SpoofGNSS][cg] still publishes only
its description and explicitly postpones the data release. [HK-UrbanSpoof][hk]
publishes GPS L1 IF recordings, with a static reference coordinate, but its
roughly 10 GB captures require signal decoding and do not expose RAWX/RINEX
in the inspected repository. S7AM1NA still has no GitHub release assets; its
previously tested Pixel sample remains outside the stated attacks. These
findings do not justify new parsers, bulk IF downloads or claims of coverage.

[data]: https://data.mendeley.com/datasets/nxk9r22wd6/3
[paper]: https://pmc.ncbi.nlm.nih.gov/articles/PMC11220923/
[cg]: https://github.com/agilawood4/CG-SpoofGNSS
[hk]: https://github.com/Fangjingxiaotao/HK-UrbanSpoof
