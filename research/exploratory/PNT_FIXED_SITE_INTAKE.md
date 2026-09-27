# Fixed-site RINEX intake: three actual receivers, no attack verdict

The reusable [intake](pnt_fixed_site_intake.py) accepts one local and two
external RINEX 3 observation files for a GPST day. It reuses the existing
strict GPS C1C/C2W reader and same-epoch/satellite pairing. It reports source
hashes, declared marker names and approximate coordinates, exclusions,
paired-satellite counts by epoch, and gaps in paired epoch coverage. Files
with duplicate bytes or marker names, ambiguous time scales, unsupported
corrections or malformed observations fail instead of counting as independent
witnesses. The output is a coverage qualification, not another authority or
experiment-specific replay layer.

We exercised it on already exposed [BKG IGS observations][bkg-access] from
11 September 2024 (DOY 255): [NYA200NOR][nya] as the **exercise local
receiver**, [TRO100NOR][tro] and [KIRU00SWE][kiru] as external references.
The three are distinct physical markers, but all three files came through BKG;
they do not establish independent data distribution, independent time or a
victim under attack. The [versioned result](results/pnt_fixed_site_intake_2024255.json)
records SHA-256 of each original compressed file. It finds 28,515 common
satellite/epoch rows on all 2,880 30-second epochs; each epoch has 8–12
paired GPS satellites. NYA2 has 34,705 locally usable dual-code rows. This
shows that the same-file-format path works on a complete real day, not that
the observations are benign ground truth or that the network improves a
detector. RINEX approximate XYZ is self-declared metadata, not an independent
survey of the local antenna.

With the original three downloads, reproduce from the repository root:

```console
python -m research.exploratory.pnt_fixed_site_intake 2024-09-11 NYA200NOR_R_20242550000_01D_30S_MO.crx.gz TRO100NOR_S_20242550000_01D_30S_MO.crx.gz KIRU00SWE_R_20242550000_01D_30S_MO.crx.gz OUTPUT.json
python -m pytest research/exploratory/tests/test_pnt_fixed_site_intake.py research/exploratory/tests/test_pnt_observation_pairing.py -q
```

For the next P2 recording, use the actual fixed receiver as the local input
and two contemporary external files. A zero or sparse overlap must remain
visible; it cannot be repaired by changing the day or silently replacing a
station. This adapter currently qualifies GPS C1C/C2W at exact 30-second
GPST epochs. It does not inspect phase, Doppler, C/N0, lock flags, PVT,
independent capture timestamps or the event schedule. Those original fields,
an independent antenna position and the paired benign/challenge intervals
remain required by the [recording decision](PNT_P2_RECORDING_DECISION.md) for
the decisive local-only versus local-plus-network comparison. A different
receiver format requires a signal-qualified adapter, not relabeling its
observations as C1C/C2W.

[bkg-access]: https://igs.bkg.bund.de/access
[nya]: https://igs.bkg.bund.de/root_ftp/IGS/obs/2024/255/NYA200NOR_R_20242550000_01D_30S_MO.crx.gz
[tro]: https://igs.bkg.bund.de/root_ftp/IGS/obs/2024/255/TRO100NOR_S_20242550000_01D_30S_MO.crx.gz
[kiru]: https://igs.bkg.bund.de/root_ftp/IGS/obs/2024/255/KIRU00SWE_R_20242550000_01D_30S_MO.crx.gz
