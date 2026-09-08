# G12 DOY250 — seven-root positioning attempt

**Terminal: `SOURCE_OR_MEASUREMENT_NOT_QUALIFIED`**

Reason: `NO_COMMON_STRUCTURAL_WINDOW`. No position was fitted, no target
navigation was admitted, and neither target values at GOLD nor the orbit oracle
were opened. This closes exactly the predeclared target/day/network attempt.

## Frozen physical change

Target G12, 2026-09-07 GPST. Fit stations ALGO00CAN, DRAO00CAN, STJO00CAN,
YELL00CAN, BOGT00COL, BRAZ00BRA and AREQ00PER. GOLD00USA was reserved for
confirmation. BRAZ and AREQ extend the terrestrial north-south geometry.

The plan required the first block of 41 consecutive 30-second epochs with both
target codes C1C/C2W and at least four non-target GPS references at every station.
Only its central eleven epochs would enter calibration and positioning. The
twenty-minute support block was a prospective design choice, not a mathematical
minimum for one position.

Plan SHA-256:

`fcbacd7201cd37470621cc387d12379bd62906b9620896329d7493668ea60816`

## Observation result

All eight exact public daily products were acquired and hashed before decoding.
Every file has 2,880 observation epochs and between 706 and 1,147 epochs with
both target codes. All station sources individually contain the target.

Across the eight roots, only **19 epochs** meet the common structural criteria:

- **10:19:00–10:27:30 GPST:** 18 consecutive samples, spanning 510 s.
- **10:28:30 GPST:** one additional isolated sample.

The required 41-sample block does not exist. The run stopped at this condition;
there was no later-window substitution, shorter-window retry or satellite swap.
The code reports this terminal before either estimate or verify can proceed.

## Information gained

A premeasurement synthetic design compared the original five roots against the
seven-root geometry on 80 invented jointly visible positions, using three
radii and a latitude/longitude grid. It used ground coordinates and physical
constants, never G12 orbit data. The median approximate uncertainty radius
changed from 19.191 km to 7.029 km; the median improvement factor was 2.294.
Those numbers excluded the additional correlated error terms and did not
predict this target's pass or guarantee success.

The real data expose the tradeoff: additional geographical extent can improve
position observability while shortening simultaneous observed coverage.
Geometry and common measurement availability must both support a proof.

## Block analysis

**What failed:** the predeclared 41-sample joint support requirement.

**What did not follow:** impossibility of G12 positioning, absence of all joint
measurements, or poor measured xyz accuracy. There is no xyz estimate here.
Eighteen consecutive epochs would meet an eleven-sample rule, but that was not
the frozen selection rule of this event. Numerical quality/elevation for such
an alternative has not been evaluated.

**Alternatives for a separate unexposed event:**

1. A shorter, physically justified support rule, frozen before new observations.
2. A southern station subset with an explicit common-visibility tradeoff.
3. More frequent observations where the independent sensor geometry overlaps.
4. Multiple emitted events with explicit free-state dynamics, changing the model.

The shortest next physical design is to justify the actual interpolation and
clock support duration, then preregister that duration on new evidence. Do not
automatically repair this failure by building more data-discovery infrastructure.

The G08 and DRAO results remain unchanged. This attempt and its failure are
retained alongside them; there is no new successful positioning claim.
