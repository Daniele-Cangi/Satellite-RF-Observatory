# GNSS observer-transfer real-geometry screen

## Outcome

```text
OBSERVER_TRANSFER_GEOMETRY_SHORTLISTED
```

This is an orbit-only result. It selects no capability, observation product,
qualification artifact or primary and authorizes no measurement.

## Physical question

Does the frozen G22-minus-G30 ionosphere-free phase prediction retain a
positive orbital-versus-null margin at one observer C not used by the
GOLD/NLIB primary and replication?

The synthetic observer-transfer spike showed that the topology can work. This
screen adds the missing physical information: whether real station geometry
and real post-A/B broadcast orbits preserve the distinction.

## Bounded predeclared scope

The observer set is limited to four stations already frozen in the prior IGS
metadata receipt:

| Observer | Latitude deg | Longitude deg | Height m | Role here |
|---|---:|---:|---:|---|
| DRAO00CAN | 49.322600 | -119.625000 | 542.0 | unused observer candidate |
| WES200USA | 42.613336 | -71.493328 | 85.0 | unused observer candidate |
| PIE100USA | 34.301506 | -108.118927 | 2347.711 | unused observer candidate |
| AMC400USA | 38.803125 | -104.524597 | 1911.394 | unused observer candidate |

GOLD/NLIB are excluded because they are observers A/B. ALGO/MDO are excluded
because both bounded primary paths were consumed. No station inventory or new
station metadata search was performed.

The date set is exactly DOY221--223. The three NOAA broadcast NAV files were
temporarily re-materialized, matched their already frozen byte counts and
SHA-256 values, used in RAM and destroyed. They are orbital-model inputs, not
receiver observations.

## Frozen comparison

For every station/date case the compiler searches only jointly visible
139-epoch windows at 30 s cadence. G22, G30 and wrong-orbit families G01, G14
and G17 must remain above 15 degrees for the nominal grid and the direct
`t +/- 15 s` grids.

The coordinate is:

```text
Q_C(t) = IF_phase(C,G22,t) - IF_phase(C,G30,t)
Q'_C(t) = Q_C(t) - Q_C(t_0)
```

Sample zero removes one constant ambiguity. There is no free rate, time warp,
suffix fit or observation-informed anchor. The affine rate is chosen from the
target prediction alone. Every wrong orbit receives the same event-time,
troposphere, transform and interval treatment. The timing and troposphere
envelopes use the maximum across the target and all wrong-orbit families.

## Results

All 12 station/date cases have at least one completely visible window with
positive conservative margin. Ranking retains only the best date/window per
distinct observer:

| Rank | Observer/date | Window GPS | Controlling null | Separation m p-p | Pairwise envelope m | Margin m | Min shifted elevation deg |
|---:|---|---|---|---:|---:|---:|---:|
| 1 | PIE100USA / DOY223 | 05:42:00--06:51:00 | frozen affine | 190,232.341 | 2,907.821 | 187,324.520 | 17.802 |
| 2 | WES200USA / DOY223 | 05:29:00--06:38:00 | wrong orbit G17 | 161,836.833 | 1,674.939 | 160,161.894 | 33.330 |
| 3 | AMC400USA / DOY221 | 05:41:30--06:50:30 | frozen affine | 162,247.193 | 2,347.701 | 159,899.492 | 25.726 |
| 4 | DRAO00CAN / DOY223 | 05:11:00--06:20:00 | frozen affine | 22,067.015 | 2,699.515 | 19,367.500 | 15.017 |

The geometric selection is PIE100USA on DOY223. Its held-out interval begins
at `06:21:30 GPS`. The dominant envelope contribution is the direct event-time
trajectory term: `2,836.291 m` pairwise, controlled by G22 at `-15 s`. The
signal-specific hardware term remains
`REQUIRES_PREDECLARED_C_PREFIX_ADMISSION`; it has not been measured or set to
zero.

## Interpretation

The very large PIE margin means a single observer can, in principle, test
spatial transfer without constructing another four-link station pair. It does
not prove that PIE supplies the required phase fields or continuity.

WES remains a geometry-positive but capability-rejected historical route: its
known RINEX v2 primary feed does not establish the frozen L1C/L2W signal
identity. This screen does not reverse that refusal. If PIE fails capability
admission, AMC is therefore the next not-already-refused observer in the
geometry ranking, not WES.

## Exact remaining blocker

Before any prospective primary can be frozen, a bounded PIE-only capability
check must establish, without inspecting target values:

1. an explicit RINEX 3 observation product path for the relevant receiver
   configuration;
2. hardware/configuration continuity between one distinct qualification day
   and DOY223;
3. `L1C + L2W` phase and both LLI fields for G22/G30;
4. same-path `C1C + C2W` witnesses under a predeclared quantitative rule;
5. complete first/last-observation coverage of the 139-epoch window and 30 s
   event-time semantics compatible with the frozen `+/-15 s` envelope;
6. a deterministic continuous segment with no interpolation, gap bridging or
   nonzero LLI.

Failure of any required clause must stop before primary selection. No global
inventory, adapter or retry of ALGO/MDO is justified.

## Frozen receipt

[`GNSS_OBSERVER_TRANSFER_GEOMETRY_RECEIPT.json`](GNSS_OBSERVER_TRANSFER_GEOMETRY_RECEIPT.json)
is `164,520` bytes with SHA-256
`4982a32459d880a17abab9cf726ee6e8f6383e1d0b570abbf77fd07341d459d5`.
It binds source commit `48afe8e59bc97d2fc0afc5afc7015176018af89c`, source
SHA-256 `144d08128f59c2a6d8b3c38d161efdb54231eb3c3e8129425590a7d016491e4f`
and manifest SHA-256
`864421a47a91f20a19ca755b8156459762d561709e6e1e4dfa16cc98e7c7637f`.

All observation access counters are zero. Stop before capability discovery.
