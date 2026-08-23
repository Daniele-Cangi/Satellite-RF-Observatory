# GOLD/NLIB G11/G21 geometry-guard audit

## Physical purpose

Physical question:

> Can the unchanged GOLD/NLIB, G11/G21 experiment provide the complete frozen
> 386-epoch window after both receiver roots have already had a conservative
> 30-minute interval of joint geometric visibility?

New information produced: whether the failure of the first independent
qualification can be bypassed by choosing another date without changing the
satellites, stations, duration, elevation rule or physical coordinate.

Why the existing qualification cannot answer it: the DOY 214 artifact begins
at a satellite-acquisition boundary. NLIB-G21 is absent for 27 epochs and its
first phase record has nonzero LLI.

Minimum experiment: a broadcast-navigation-only screen of the predeclared DOY
216--220 set. No observation product, header or value enters the screen.

Stop condition: if no candidate provides 386 epochs at or above 15 degrees
after a preceding 30 minutes also at or above 15 degrees, select no
qualification artifact. Do not shorten or move the window after inspecting an
observation.

## Frozen scope

- Stations: GOLD00USA and NLIB00USA.
- Satellites: G11 target and G21 reference.
- Grid: 30 s.
- Required raw window: 386 epochs.
- Window guard: all four station/satellite links at or above 15 degrees.
- Acquisition pre-roll: preceding 60 epochs (1,800 s) under the same guard.
- Candidate dates: 2026 DOY 216--220.
- Observation access: zero.

The broadcast-navigation hashes and every candidate result are retained in
`GNSS_GEOMETRY_GUARD_AUDIT_RECEIPT.json`. DOY 214 and DOY 215 are historical
audit inputs, not candidates.

## Result

```text
NO_GEOMETRY_GUARDED_QUALIFICATION_ARTIFACT
```

| DOY | 15-degree segment | 20-degree segment | 25-degree segment | Best 386-epoch window | Preceding 30-minute minimum | Admission |
|---:|---:|---:|---:|---|---:|---|
| 216 | 386 | 328 | 271 | 09:57:30--13:10:00 GPS | 3.405 deg | pre-roll fails |
| 217 | 385 | 327 | 271 | none | n/a | full window absent |
| 218 | 385 | 327 | 270 | none | n/a | full window absent |
| 219 | 386 | 327 | 271 | 09:45:00--12:57:30 GPS | 3.380 deg | pre-roll fails |
| 220 | 386 | 328 | 271 | 09:41:00--12:53:30 GPS | 3.435 deg | pre-roll fails |

The orbital-versus-prefix-affine separation remains large in the three dates
that contain 386 epochs: 2,144.749--2,146.384 Hz peak-to-peak. The failure is
therefore not loss of modeled orbital discriminability. It is absence of an
acquisition-margined measurement window of the frozen length.

At 20 degrees, the longest candidate segments contain only 327--328 epochs.
At 25 degrees they contain 270--271. Those shorter windows were not promoted,
because doing so would change the confirmation design after a measurement-path
failure.

## Historical failure geometry

On DOY 214 the original window starts with a four-link minimum elevation of
14.967 degrees. At the first NLIB-G21 record, 10:19:00 GPS, that link is at
21.154 degrees and both phase LLI fields are nonzero. At 10:19:30, the first
admissible joint epoch, it is at 21.375 degrees.

This is consistent with an acquisition boundary but does not establish why the
receiver omitted G21. No receiver mask, tracking policy or failure cause is
inferred from geometry alone.

## Authorized conclusion

No new observation artifact is selected or accessed. The unchanged
GOLD/NLIB-G11/G21 route is closed for the 386-epoch design: it combines high
orbital discriminability with insufficient pre-acquisition visibility margin.

The result does not claim that GOLD/NLIB cannot support another satellite pair
or a separately justified shorter physical experiment. Either would require a
new orbit-first comparison, not another retry of this qualification chain.
