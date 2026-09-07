# DRAO labelled-forward geometry screen

## Outcome

```text
DRAO_LABELLED_FORWARD_GEOMETRY_SHORTLISTED
```

The frozen compiler at commit
`834da0c10de2ef075cb137f19bd165750546fe46` evaluated only the five
predeclared NOAA broadcast-navigation products for GPS DOY234--238. It queried
or accessed no observation product, locator, header, payload, measurement value
or decoder.

All five days contained positive orbit-only cells. The three retained daily
winners are:

| Rank | DOY/date | Raw window GPS | Held-out start GPS | Frozen PRN codebook | Jointly visible | Controlling null | Exact separation m | Direct time-shift envelope m | Robust lower margin m | Min shifted elevation deg |
|---:|---|---|---|---|---:|---|---:|---:|---:|---:|
| 1 | 237 / 2026-08-25 | 04:55:00--06:04:00 | 05:34:30 | G14/G15/G17/G20/G24/G30 | 9 | time reversed | 36,546.470629 | 1,396.870014 | 14,527.366926 | 15.103639 |
| 2 | 238 / 2026-08-26 | 04:50:00--05:59:00 | 05:29:30 | G14/G15/G17/G20/G24/G30 | 9 | time reversed | 36,418.383973 | 1,392.806994 | 14,399.280269 | 15.491858 |
| 3 | 234 / 2026-08-22 | 05:05:00--06:14:00 | 05:44:30 | G14/G15/G17/G20/G24/G30 | 9 | time reversed | 36,208.704481 | 1,385.863580 | 14,189.600777 | 15.226520 |

The prefix-affine separations are much larger than the controlling values:
`102,951.569261 m`, `102,651.842705 m` and `103,856.212770 m`
respectively. Event ordering, not generic curvature, is therefore the harder
frozen null.

## What the result changes

Each shortlisted interval has nine robustly visible GPS satellites. Under the
old inverse contract that would have caused another cardinality refusal. In
the labelled forward topology, every six-satellite combination was evaluated
from orbit geometry only and the winning six PRNs can be frozen before any
measurement access. The other three satellites neither invalidate the sensor
nor enter the later score.

This is the first direct numerical confirmation that removing total-track
cardinality did not remove orbital discriminability. It removed only the
targetless identity claim.

## Claim and independence boundary

The screen authorizes no physical observation claim. A future positive can at
most support `ORBITAL_MODEL_PREDICTIVELY_PREFERRED` for receiver-labelled
tracks. The receiver's PRN identity is model-conditioned and is not an
independent discovery.

G14 and G17 have appeared in historical development work. Their inclusion was
chosen by this new orbit-only geometry, not by a new observation, but the
prospective vertical will provide temporal independence rather than a new
satellite-family replication. This limitation must remain in the claim scope.

The low controlling elevation, especially `15.103639 deg` for rank 1, also
means raw geometric rank is not yet measurement admission. Troposphere and
multipath sensitivity may reverse the practical ordering after an
outcome-independent physical-envelope audit; the current ranking must not be
changed using observation data.

## Remaining causal cut

Before selecting any observation artifact, the rank-1 date/codebook/window
must receive an exact physical-envelope audit on the same grid. At minimum it
must bound:

- direct event-time displacement, already measured here as `1,396.870014 m`
  under `+/-15 s` and below the historical guard;
- broadcast orbit and satellite-clock non-affine error for the six PRNs;
- differential troposphere at the near-15-degree edge;
- ionosphere-free and higher-order ionosphere remainder;
- antenna PCV and phase wind-up;
- receiver clock/implementation and signal-specific hardware;
- phase-minus-code multipath witness and RINEX quantization.

The historical `7,339.701235 m` guard is only a screen. No term may be carried
forward as zero or considered admitted solely because the robust geometry
margin is positive.

## Evidence boundary

- receipt SHA-256:
  `06161af57ada12e081faef7cf470e540ea5fff5dd7cf2f6614077b738852ed62`;
- source SHA-256:
  `cada0d5694e85cbf4d710b998e4df0f55b51f43212ca841e27692ee477adf4b9`;
- scope SHA-256:
  `fee2577189e47460bd7efe210e978c00e756c376ed4d7241316d16af95f8cf1c`;
- navigation payloads retained: `0`;
- observation-access counters: all `0`;
- primary selected: `false`;
- prospective plan frozen: `false`.

## Stop

Stop before querying whether a DRAO DOY237 observation product exists. The
next maximum action is the rank-1 date/codebook-specific physical-envelope
audit. If any unresolved term can absorb the `36,546.470629 m` controlling
separation under the frozen decision rule, close this route without selecting
an artifact.
