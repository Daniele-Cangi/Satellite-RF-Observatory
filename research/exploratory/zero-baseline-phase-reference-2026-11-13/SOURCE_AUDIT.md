# Source audit for an independent GPS wide-lane DD reference

The [WUT analysis](RESULTS.md) compares Melbourne–Wübbena (MW) with a
conditional carrier-phase label. To qualify an absolute integer, the next
source must constrain the phase contribution in the same ambiguity convention.
An independent bound on the full DD residual, tight enough to leave a single
candidate integer, is an equivalent input.

## RingCalVal inspection

The [observation archive](https://doi.org/10.5281/zenodo.16878951) publishes
a short baseline and an external rubidium frequency reference. Its companion
[ANTEX archive](https://doi.org/10.5281/zenodo.16816983) publishes antenna
phase-center offsets and patterns. The
[evaluation report](https://doi.org/10.15488/18995), section 2.2.5, documents
the IfE common-clock equipment. The 0.2 mm figure in the source metadata is
the precision of the mount-to-antenna-reference-point measurement.

ZIP CRC was verified on METADATA.README and the two members in
LEIAR25-R3_NONE_08360013 listed below. Only the receiver metadata and RINEX
headers were decoded. The archive-wide digest was not verified by the partial
transfer.

| Source member | SHA-256 of the member bytes |
|---|---|
| METADATA.README | bc54792d5008957d4165899f88a12f0f40b1f845c235dfabc5d9f273841d3bec |
| MSD500DEU_R_20222351335_10H_30S_MO.crx.gz | d46eb77d2892287fd11aadaedbacac13d3330943fb64e38e04755d08f0c266e3 |
| MSD800DEU_R_20222351335_10H_30S_MO.crx.gz | 094b2be8578a97f391c7bc5f1a1b8fc20b214c8d4886fb3478e60334f4e56091 |

The two receiver headers identify distinct antenna serials and radomes
(08360013/NONE and 09330001/LEIT) and different firmware builds. Both declare
GPS C1C/C2W/L1C/L2W observation types. The tabulated 2024.00 coordinates
imply a 20.650 m baseline. Neither header declares that receiver clock
offsets were applied. A shared frequency source gives no numerical
bound on the relative epoch offset by itself. The public package gives no
per-arc labels, traceable bound on that offset, or unwrapped phase
characterization of both receiver chains. A correction for antenna phase
center can reduce a geometric residual while leaving the receiver phase
datum undetermined. [RINEX 3.05, §5.2.14](https://files.igs.org/pub/data/format/rinex305.pdf)
[NGS calibration equations](https://www.ngs.noaa.gov/CORS/Articles/Bilich-and-Mader_ION2010.pdf)

A third-party receiver calibration would have to match the receiver's
tracking convention. In particular GPS L2C observations do not qualify
L2W semi-codeless tracking. [GPS signal tracking and observables](https://gnss-sdr.org/docs/sp-blocks/observables/)

The [PTB common-antenna study](https://doi.org/10.1007/1345_2022_145) is a
better match for repeatable timing. It uses the same antenna and UTC(PTB)
frequency reference with matched RF paths. Its published ambiguities are
obtained by rounding carrier measurements under that experiment's model.
The [NIST common-clock experiment](https://tsapps.nist.gov/publication/get_pdf.cfm?pub_id=842482)
removes a per-pass phase constant and measures changes. Neither publication
provides an independent integer origin transferable to the WUT data.

## Optical geometry as an independent constraint

[Cortes de Pallás](https://doi.org/10.1088/1361-6501/ac6f45) provides an
optical Mekometer distance check and two GNSS sessions on a roughly 1916 m
line. All four [open observation files](https://doi.org/10.5281/zenodo.6566948)
declare 1 Hz GPS C1C/C2W/L1C/L2W and use Leica GS10 receivers. Header inspection
used byte ranges through END OF HEADER. The public record contains these
observation files without independent per-arc labels. The companion
[reference-frame paper](https://doi.org/10.1007/s12518-022-00481-9)
uses GNSS-derived directions to orient the terrestrial network. Its distance
check alone cannot supply an independently oriented baseline for phase DD,
and the published GBDM+ distance budget does not bound each receiver's
differential phase delay.

For a short baseline of length L, an orientation error of angle theta can
change the baseline vector by 2 L sin(theta/2). The first-order DD projection
multiplies this by the separation of two line-of-sight unit vectors, at most 2.
For L = 1916 m, limiting this orientation contribution to 0.025 GPS L1 cycles
in that worst case requires theta below about 0.26 arcseconds. An independently
measured length removes radial uncertainty from this calculation while leaving
the orientation contribution. The 0.025-cycle allocation is illustrative,
and the actual projection depends on the chosen pair.

The [RISE laser-tracker campaign](https://doi.org/10.1007/s00190-020-01433-0)
is a closer candidate. It reports L1 and L2 work on an approximately 7.18 m
baseline and describes imposing external geometry to identify carrier-phase
integers. It also reports refining the baseline azimuth with a GNSS subset.
Using the three uncertainty magnitudes in its Table 2 simultaneously as a
sizing check gives 2 sqrt(0.45² + 0.63² + 0.05²) = 1.55 mm for the maximum
first-order geometric DD projection, or 0.0082 GPS L1 cycles. This is neither a
joint-confidence statement nor a total DD phase bound. The tracker-only
orientation, separate reacquisitions, the exact GPS signal types and the
receiver phase/clock calibration remain to be confirmed. The authors make
measurements available on request. The published phase model also treats the
clock and hardware term as common across satellites. Independence of a DD
label requires evidence for that assumption at the required accuracy, or a
calibrated bound on the noncommon term.

## CASSIOPE flight observations and star-tracker geometry

The [April 4 GAP archive](https://epop-data.phys.ucalgary.ca/2019/04/04/GAP/)
offers a short-baseline flight benchmark independent of the terrestrial
campaigns. Three GPS-0/2/3 RINEX 3.02 headers declare 1 Hz C1C/C2W/L1C/L2W.
The archive lists repeated GPS-0/2 turn-on sessions on April 4 and 5, some
with over an hour of nominal overlap. The
[mission handbook](https://epop.phys.ucalgary.ca/data-handbook/gap-lv2-rinex-file/)
documents the conversion from receiver logs, and the
[daily attitude product](https://epop.phys.ucalgary.ca/data-handbook/cas-ephemeris-text-files/)
identifies which interpolations use nearby star-tracker solutions. A file
overlap establishes candidate coverage. Continuous carrier lock and
star-tracker coverage are still to be verified.

The [flight paper](https://doi.org/10.1007/s10291-019-0907-2), Tables 3–4,
compares single-epoch code/phase fixes against DD phase interpreted using
star-tracker attitude and antenna baselines calibrated from 2018 GPS
observations. The star tracker provides an independent orientation.
The [companion calibration paper](https://doi.org/10.1002/navi.348), Table 3,
also gives the GPS-0/2 baseline from the mechanical design. Its difference
from the dual-frequency in-flight calibration has norm 9.92 mm. For a common
baseline error of that size, the worst first-order DD projection is 19.84 mm
or 0.023 wide-lane cycles. This comparison sizes one geometry contribution.
The published baseline dispersions measure repeatability, and the reported
differential antenna phase patterns are fitted corrections. They supply no
independent bound on the full unwrapped L1/L2 DD phase residual.

The [mission operations report](https://epop.phys.ucalgary.ca/wp-content/Swarm-E_Final_Operations_Report.pdf),
Table 4, lists RANGE (43) and PSRXYZ (243) as default GPS-0/2 messages for
these dates. Four complete April 4 Level 1 files were hashed and inventoried
using OEM4 frame headers and CRC32. RINEX inspection ended at END OF HEADER,
and the packet inventory decoded no measurement payloads.

| GAP Level 1 file | SHA-256 | RANGE / PSRXYZ packets |
|---|---|---:|
| GAP_20190404_000000_000042_RCVR_0_3.1.2.lv1 | 50e23d722724cece0434d1b6df8a4b01c1fbd9784f42c01ce3fc19c40c2876a0 | 42 / 42 |
| GAP_20190404_000000_000043_RCVR_2_3.1.2.lv1 | 5c951d995c63eab06b8b02421e8307927908a391c8777c7b3318bd7ec1f06c36 | 44 / 44 |
| GAP_20190404_020123_032841_RCVR_0_3.1.2.lv1 | b935c1fb097eac9571eb0d4fbd47fca1e007585556dbdce49791a0ac4962efa3 | 5230 / 5235 |
| GAP_20190404_020126_032841_RCVR_2_3.1.2.lv1 | 8bac40fc523d3f8e86b47e08818d192d3b0040e27c9826f73fa7d9b12c78a061 | 5227 / 5223 |

These files contain no clock-offset or external-event message. RANGE still
offers lock, parity and half-cycle status for checking continuity, as
documented in the [OEM4 manual](https://epop.phys.ucalgary.ca/wp-content/uploads/2022/09/R2-OEM4-User-Manual-Volume-2-Rev-18.pdf),
sections 1.3 and 3.4.47. Receiver time status is internal. The
[flight receiver qualification](https://www.dlr.de/de/rb/medien/publikationen/publikationen/gsoc-dokumente/nav_04a.pdf/@@download/file),
Figure 4, removed the initial phase ambiguities from the displayed
zero-baseline residuals to examine slips and noise. The demonstrated
repeatability therefore leaves the original cycle datum unspecified.

With the current public evidence, a CASSIOPE benchmark would produce labels
conditional on a differential phase and timing model. Counting those labels
as independently known integers would omit the link-specific cycle
reassignment below. A same-chain unwrapped residual envelope or independently
anchored labels from distinct turn-ons would change that decision. Even a
successful flight benchmark would first qualify the GAP receiver pair and
its short baseline. Transfer to the distributed G12 case needs its own
evidence.

## What the WUT observables cannot distinguish

For an aligned carrier DD on band i, write observed phase F_i = N_i + A_i
after removing the known geometric term. A_i collects the remaining phase
contribution in cycles. For raw MW write Z = N_1 − N_2 + B. Assign one extra
L1 integer cycle to the receiver-A/G04 link and remove one cycle from that
link's residual phase term. At the DD level the change is signed according
to the pair order. Every F_i and Z stays the same.

This transformation was applied algebraically to the archived scores using
decimal arithmetic. It changes 8 of 36 labels in the first window and 9 of
45 in the second. It leaves all 204 within-window triangle closures and
all six between-window changes in B unchanged. For a connected graph of
n simultaneously tracked satellites, integer link reassignments span n − 1
independent DD directions. One labelled pair protects that pair; qualifying
a complete graph requires a spanning set of labels or an equivalent bound
covering the remaining directions. For G04–G26 the two
indistinguishable decompositions are:

| Start GPST | Conditional integer and effective offset | Alternative integer and effective offset |
|---|---|---|
| 00:00 | −14 + 0.06467195 | −13 − 0.93532805 |
| 12:00 | −39 + 0.17694615 | −38 − 0.82305385 |

This is an identifiability check on the existing measurements. It does not
create a new observation or claim the alternative bias is physically likely.
A bound established outside this decomposition can reject one branch.
Longer repetitions, low within-arc scatter and an estimate of the change
between windows cannot reject it by themselves.

## Smallest new evidence that changes the decision

Request an existing recording with one calibration session and one held
session, independent reacquisitions, and simultaneous C1C/C2W/L1C/L2W.
The most direct option is a shared-antenna or conducted RF setup that measures
the receiver epoch difference and establishes either the unwrapped L1/L2
DD phase contributions or the per-arc DD integers in the receiver's reported
convention. Attach the phase-origin mapping, sign, units, uncertainty, and
scope for transferring the calibration. A logged epoch difference can
qualify the timing correction but cannot, on its own, anchor a carrier cycle.

As a sizing check, half a carrier cycle is approximately 95 mm on L1
and 122 mm on L2. A per-band deterministic residual budget below half a
cycle must include the joint contributions of geometry, timing,
nonseparable hardware delay, multipath and noise if they are present.
For example, allowing 0.025 cycles for timing at the largest sampled WUT
L1 DD rate gives 3.7 microseconds. This example specifies a measurement
target for the stated allocation, not a validated error budget.

With a new source, use the calibration to predict the compatible integers
on held arcs before reading their labels. Retain every correct fix, wrong
fix, ambiguous set, empty set and unsupported arc. A laboratory result
would first qualify that signal chain and documented conditions. Transfer
to the distributed G12 geometry needs independent support in that domain.
