# Bounded continuous-phase geometry screen

## Outcome

~~~text
GNSS_PHASE_GEOMETRY_SELECTED
~~~

One new geometry has positive physical margin in the continuous-phase
coordinate:

~~~text
GOLD00USA / NLIB00USA
target / reference: G22 / G30
GPS DOY 220
raw window:     2026-08-08 04:30:30--07:43:00 GPS
feature window: 2026-08-08 04:31:00--07:42:30 GPS
~~~

This is a broadcast-navigation-only selection. It is not a prospective plan,
measurement admission or orbital observation.

## Pre-execution freeze

The compiler and candidate rules were committed and pushed as 282657d before
the single calculation.

The bounded set contained:

- the five already exact-hash broadcast NAV products for DOY 216--220;
- fixed observer geometry GOLD00USA and NLIB00USA;
- L1C/L2W continuous phase as the future core coordinate;
- 60 pre-roll plus 386 raw epochs at 30 seconds;
- four-link elevation at least 15 degrees;
- one guard-maximizing window per unordered pair and date;
- prefix constant/rate fitted on 77 feature epochs;
- a 307-epoch held-out suffix;
- prefix-affine and every jointly visible wrong-orbit null;
- the complete phase physical envelope before ranking.

G14 and G17 were excluded from all candidate roles because they developed the
new coordinate. The closed G11/G21 pair was also excluded. These exclusions
were frozen before the calculation.

An excluded satellite remains eligible as a physical wrong-orbit null. Removing
G14 from the null family merely because it controls the selected candidate
would weaken the experiment after seeing the result and is prohibited.

## Candidate topology

Across five dates, 2,325 unordered satellite pairs were evaluated for the
guarded-window condition. Twenty pair/date windows had both the required guard
and at least one jointly visible wrong-orbit alternative.

Before phase scoring, three of the four surviving windows on each date were
excluded because G14 or G17 occupied a candidate role. The remaining set
contains five dates of one distinct pair: G22/G30. All five have strictly
positive phase physical margin.

The ranking first sorts every positive window by remaining physical margin and
then retains distinct target/reference pairs. Consequently the requested
three-entry shortlist contains one scientifically distinct pair rather than
three dates of the same geometry.

## Selected geometry

| Quantity | Value |
|---|---:|
| Guarded minimum elevation | 15.612095 deg |
| Prefix-affine separation | 1,380,516.833519 m p-p |
| Controlling wrong orbit | G14 |
| G14 separation | 824,736.025364 m p-p |
| Controlling separation | 824,736.025364 m p-p |
| One-model physical envelope | 9,883.962026 m p-p |
| Pairwise physical envelope | 19,767.924052 m p-p |
| Remaining physical margin | **804,968.101312 m** |
| Historical frequency-coordinate separation | 98.855964 Hz p-p |

The controlling separation is 41.721 times the pairwise envelope, and 97.603%
remains after subtraction.

## Physical-envelope structure

Station event time remains the dominant term at 17,788.528347 m pairwise,
89.987% of the total. The deliberately coarse independent +/-15 second
trajectory envelope therefore remains explicit; it is not replaced by an
assumed precise RINEX timestamp.

The next terms are broadcast-orbit SV accuracy at 925.592302 m, four separate
231.398076 m path families, higher-order ionosphere at 115.699038 m,
troposphere at 12.412340 m and carrier-phase quantization at 0.099723 m.
No probability, root-sum-square reduction or post-result smoothing was used.

The relatively low 15.612-degree guard increases the direct troposphere term,
but it remains negligible relative to the frozen G14 separation. This does not
authorize ignoring actual multipath or phase continuity.

## What is and is not selected

Selected:

- one orbital geometry and time window;
- one fixed two-station observer geometry;
- one L1C/L2W phase coordinate;
- one G14 wrong-orbit controlling alternative;
- one physical-margin ordering.

Not selected or evaluated:

- any RINEX observation filename or product;
- actual L1C/L2W presence for G22 and G30;
- epoch continuity or LLI;
- geometry-free phase health;
- C1C/C2W witness cadence;
- actual event-time semantics;
- measurement validity;
- calibration or held-out observation values.

The maximum current claim is therefore that G22/G30 DOY 220 is physically
discriminative in the frozen broadcast model and conservative phase envelope.

## Exact blocker before a forward experiment

The measurement path must demonstrate, on an independent qualification
artifact before any primary:

- complete GOLD and NLIB coverage of the selected-duration topology;
- L1C and L2W phase for G22 and G30 on both roots;
- zero segment-bridging and no nonzero LLI inside the retained segment;
- geometry-free phase continuity;
- a predeclared C1C/C2W same-path witness cadence;
- TIME OF LAST OBS and actual full-window coverage;
- receiver configuration consistent with a later distinct primary.

Code and signal witnesses may refuse the measurement but cannot correct or
tune the held-out phase score. S1C/S2W remain optional.

The smallest next candidate structure is:

~~~text
independent qualification candidate: G22/G30, DOY 216
prospective primary candidate:        G22/G30, DOY 220
~~~

These roles are a recommendation, not yet a product selection or plan freeze.
No observation product may be opened until the structural-only contract is
reviewed.

## Verification

- pre-execution compiler commit: 282657d;
- 20 compiler tests passed before the single calculation;
- 35 focused phase/geometry regressions pass with the frozen receipt;
- the complete generic offline suite passes: 941 tests;
- sealed Cassini CI remains separately excluded because it requires the
  external exact-hash kernel environment.

## Access and integrity

- observation products discovered: zero;
- observation products selected: zero;
- headers opened: zero;
- payload and values accessed: zero bytes;
- prospective plan frozen: false;
- measurement authorized: false;
- new gate created: false.

The single-run receipt matches the in-memory output exactly. Its repository
SHA-256 is
228359ad8e65dfe0191562ca601c6f47dad44ab36bab07736c63e8f9188f293c
and it contains 26,319 bytes.
