# G13 DOY247 — configurable request result

The single preregistered request completed automatically on 2026-09-09.
Prerequisite commit: `7a2ec9a2dc99c38e25f3c1e31904d9d6a2a8ca34`, pushed before acquisition.
Plan SHA-256: `f1f039bbb3f11dd0a8dd5c735f0044465e87b64f9d8c6a77fd3a2e9866f0fa58`.
Start UTC: 2026-09-09T07:45:50.636232+00:00. Finish UTC: 2026-09-09T07:46:37.278351+00:00.

## What was measured

All eight declared BKG daily observation files for G13, 2026-09-04 GPST,
were acquired. The structure-only scan found **zero common eligible epochs**
across ALGO, DRAO, STJO, YELL, BOGT, BRAZ, AREQ and excluded GOLD.
The predeclared minimum was eleven consecutive 30-second epochs.
BRAZ contained 1,950 epochs; the other seven files contained 2,880 each.
Each station individually had target C1C/C2W fields and >=4 reference codes,
but these records did not overlap simultaneously across the fixed network.
This does not prove that G13 cannot be reconstructed with any other network.

## Terminal and scope

`SOURCE_OR_MEASUREMENT_NOT_QUALIFIED` / `NO_COMMON_STRUCTURAL_WINDOW`.
`primary_pass=false`. No position, clock calibration, reference-navigation
download, withheld numeric reveal or target-orbit download was performed.
Missing position and error remain null in the dossier. This is a new structural
failure, not another position measurement or evidence of improved uncertainty.
The stopping rule was respected; no alternate target, day, station or window
was tried. A second invocation returned the sealed outcome without acquisition.

The reusable request worker is implemented and the negative path has now run
on real public files. The successful calibration/freeze/reveal path is covered
by the already-revealed G08 regression, not by a new passing physical result.
The private website is still the three-event read-only archive; web submission
and a persistent remote execution service are not implemented by this change.

## Evidence and next information needed

This directory contains the byte-exact request, plan freeze, structural scan,
source snapshots, job log, source receipts, terminal seal and downloadable JSON
dossier. The original raw observation payloads are preserved in the local run
and the separately delivered full ZIP. `terminal_receipt.json` verifies the
files included by the exporter used during this event. A later exporter repair
adds early transport receipts and logs to future dossiers; this event's dossier
has not been rewritten.

The fixed eight-station overlap assumption failed. A useful next design is a
bounded larger station pool with a fully predeclared presence-only subset rule,
fixed independent holdout and ground-coordinate geometry requirements. Test
that rule synthetically before acquiring a new event. More stations do not by
themselves resolve the distance/clock ambiguity; new observables such as phase
or Doppler would require separate measurement and nuisance-model work.
