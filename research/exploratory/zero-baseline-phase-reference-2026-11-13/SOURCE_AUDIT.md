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
