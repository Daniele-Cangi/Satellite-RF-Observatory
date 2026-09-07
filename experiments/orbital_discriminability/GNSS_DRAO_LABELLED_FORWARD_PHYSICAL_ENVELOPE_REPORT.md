# DRAO labelled-forward rank-1 physical envelope

## Outcome

```text
DRAO_LABELLED_FORWARD_PHYSICAL_MARGIN_ADMITTED
```

This audit regenerated only the exact-hash DOY237 broadcast model. No observation product was queried, selected or opened.

## Corrected geometry

- fixed codebook: `G14/G15/G17/G20/G24/G30`;
- controlling null: `TIME_REVERSED_GEOMETRY`;
- screened separation: `36546.470629473 m`;
- retarded separation: `36546.465333663 m`;
- prefix-affine separation: `102950.697704612 m`;
- time-reversed separation: `36546.465333663 m`;
- minimum nominal retarded elevation: `15.211970482 deg`;
- minimum `t+/-15 s` retarded elevation: `15.104333444 deg`.

## Date-specific model-side bounds

| Term | State | Held-out bound m |
|---|---|---:|
| EVENT_TIME_DIRECT_RETARDED_TRAJECTORY_ENVELOPE | MODELED_DIRECT_TRAJECTORY_ENVELOPE | 1396.870323188 |
| BROADCAST_ORBIT_USER_RANGE_ACCURACY_FAMILY | MODELED_CONSERVATIVE_INTERVAL | 16.000000000 |
| OMITTED_BROADCAST_SATELLITE_CLOCK_NONAFFINITY | MODELED_FROM_BROADCAST_CLOCK_FIELDS | 0.582436051 |
| DIFFERENTIAL_TROPOSPHERE_RELAXED_BOX | MODELED_CONSERVATIVE_INTERVAL | 52.522061740 |
| STATION_DISPLACEMENT_EOP_AND_RELATIVITY | MODELED_CONSERVATIVE_INTERVAL | 4.000000000 |

The troposphere term is deliberately stronger than a constant-delay approximation: every satellite and epoch is relaxed independently inside its 0--3.5 m zenith-mapped slant interval, then propagated through the exact centering and prefix projection.

## Decision

- model-side total: `1469.974820979 m`;
- conditional measurement reserve: `2506.001723837 m`;
- one-model bound `B`: `3975.976544816 m`;
- required `3B`: `11927.929634448 m`;
- remaining physical margin: `24618.535699215 m`.

A positive margin is conditional, not a capability result. It is usable only if a later distinct structural qualification proves all six L1C/L2W tracks, zero/blank LLI, complete C1C/C2W witnesses, geometry-free continuity and exact timing/format coverage over all 139 epochs. Extra tracks remain descriptive.

## Claim boundary

A later positive can reach only `ORBITAL_MODEL_PREDICTIVELY_PREFERRED` for receiver-labelled tracks. It cannot independently establish PRN identity. G14/G17 provide temporal, not satellite-family, independence.

## Stop

Observation locators, products, headers, payload bytes, values, decoders and scores: `0`. Stop before any DOY237 observation lookup.
