# CODE product convention audit

The two admitted rapid SP3 headers resolve the **declared ocean-loading CMC
handling**. They identify FES2014b, ocean CMC enabled during processing, and
`ORB:CoN CLK:CoN`. The paired daily rapid ERP files identify `IAU2000R06` and
`DESAI2016`. No new calibration, satellite-state parsing or EOP reconstruction
was performed. This is a product metadata audit, not an accuracy result.

## Evidence specific to the products

| Property | G14 / 2026-09-03 | G12 / 2026-09-05 |
|---|---|---|
| Product family | COD0OPSRAP | COD0OPSRAP |
| SP3 frame | IGc20 | IGc20 |
| Antenna model | IGS20_2425 | IGS20_2425 |
| Ocean model / CMC flag | FES2014b / Y | FES2014b / Y |
| Orbit / clock origin declaration | CoN / CoN | CoN / CoN |
| Atmospheric header field / flag | NONE / N | NONE / N |
| ERP nutation / subdaily pole | IAU2000R06 / DESAI2016 | IAU2000R06 / DESAI2016 |
| Event-specific mean-pole model | not declared in these headers | not declared in these headers |

The SP3 comments were already in the immutable reference-only extracts from
the earlier reference-product study. The audit hashes those exact buffers and parses only through the first
epoch marker, never any satellite record. The old receipt supplies the orbit
and separate clock source identities; clock values are not read. CoN for clocks
is the declaration in the paired SP3, not an independent inspection of the
30-second clock adjustment.

The two newly retained ERP files are terrestrial products with no satellite
states. URLs, compressed/decompressed hashes and acquisition times are in
`inputs/code_conventions/receipt.json`. Their processing dates are 4 and 6
September, respectively. The audit checks their rapid family and middle day
against the corresponding archived product. Numeric pole coordinates, rates,
UT1 and LOD are retained as original bytes but not interpreted in this audit.

## What the CMC declaration resolves

The [IGS SP3 comment specification](https://acc.igs.org/sp3-comments.html)
distinguishes CMC flags used during estimation from corrections used when
producing terrestrial SP3 coordinates. `ORB:CoN` declares that the applicable
loading CMC has been corrected in that output; `CLK:CoN` identifies the
ITRF-fixed station convention during clock adjustment. Thus the `Y` flag does
not instruct this consumer to add the BLQ geocenter translation again.
Retain the local FES2014b `CMC:NO` component with these CoN products.
The specification marks the atmospheric model field as not currently used:
`NONE` alone cannot establish absence of atmospheric tides.

The [CODE team's 2024 geocenter presentation](https://www.bernese.unibe.ch/publist/2024/pres/IGSWS2024_gcc.pdf)
(slides 5, 7 and 19) distinguishes terrestrial station/SP3 coordinates from the
instantaneous mass-centered inertial system used for orbit dynamics. It also
shows coupling between geocenter handling and estimated satellite clocks.
Its rapid-scheme experiment concerns June/July 2023, not our event dates; it
explains the mechanism but is not the provenance of our 2026 files.

The new report therefore resolves a **declaration-level** question which PR146
left open. It does not certify CODE's execution, the physical loading accuracy,
or the entire local station model. The immutable PR146 flags and numerical
reports remain unchanged; this is subsequent evidence, not a rewritten outcome.

## Pole and atmospheric questions remain distinct

The paired ERP headers explicitly name DESAI2016. A reconstruction using only
daily Bulletin A interpolation is not automatically the same instantaneous
Earth orientation used by CODE. Daily ERP values alone also do not supply a
complete subdaily reconstruction. This audit does not add those terms, rotate
SP3 coordinates again, or reuse ERP formal errors as physical error bounds.

The [Bernese example configuration table](https://www.bernese.unibe.ch/faq/table_exampleBPEs.html)
associates ITRF2020/IGS20 processing with `IERS2010_v1.2.0` for the mean pole and
DESAI2016 for the subdaily model. These are different models and settings.
The example is supporting context; it does not prove the configuration of the
two rapid processing runs. In particular the old generic label “IERS 2010”
does not establish the original polynomial mean pole rather than its update.
Preserve both PR146 pole variants without selecting a convention by smaller RMS.

The older [CODE analysis summary](https://www.aiub.unibe.ch/download/CODE/CODE_ACN.TXT)
mentions S1/S2 atmospheric tides, whereas the SP3 atmospheric field is NONE.
Because that field is not normative evidence of absence, do not interpret this
as a demonstrated missing correction or choose an atmospheric model from it.
Source-specific atmospheric configuration and a compatible local model remain
necessary.

## Reproduction and next step

`code_convention_audit_v2.py` uses only the standard library. Input hashes are
checked before interpretation. The evidence receipt also records hashes of
consulted documentation; those documents are linked, not redistributed.

```powershell
python -m research.exploratory.code_convention_audit_v2 NEW_REPORT.json
python -m pytest research/exploratory/tests/test_code_conventions.py research/exploratory/tests/test_code_conventions_v2.py -q
```

The implementation and evidence were frozen at `aef3c2e` before producing
`results/code_convention_audit_v1.json`. Review then identified missing explicit
checks for the first epoch, strict JSON and paired product source names. V2 was
frozen at `46a22ee` before its report; it adds those checks, including non-finite
JSON rejection, while preserving v1 source and output. Both report exactly the
same product findings. Use `results/code_convention_audit_v2.json` for the active
boundary. All 33 targeted tests pass.
The output must not exist. Tests cover metadata interpretation, incompatible
CMC/origin flags, date/family/frame mismatches, duplicate/malformed declarations,
body exclusion, tampered evidence and exact report replay. No numerical fit
needs repeating to answer this metadata question.

Next implement a separately validated reconstruction of the paired CODE ERP
with its subdaily convention, retaining explicit mean-pole and atmospheric
uncertainties. Then expand reference-only time coverage to investigate the
larger receiver/media residual terms. CMC is no longer an unspecified reason
to repeat millimetric sensitivity trials. Physical covariance, S2/G3 completion
and a new independent confirmation remain open; production and hosting are
unchanged.
