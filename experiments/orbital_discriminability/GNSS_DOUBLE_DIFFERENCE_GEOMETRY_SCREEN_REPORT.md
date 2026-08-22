# GNSS double-difference prospective geometry screen

> Time-axis amendment: this geometry-only checkpoint preceded real header
> admission and labelled the delivery grid as UTC. The headers later proved
> GPS time. Corrected windows, margins and the frozen experiment are recorded
> in `GNSS_DOUBLE_DIFFERENCE_PROSPECTIVE_PLAN.md`; the historical numbers below
> remain only to preserve the checkpoint audit trail.

## Outcome

`GNSS_DOUBLE_DIFFERENCE_GEOMETRY_SHORTLISTED`

This is a broadcast-navigation-only result. No RINEX observation file was
opened, no receiver sample or carrier observable was read, and no prospective
experiment is frozen.

## Physical question

Can a frozen broadcast orbit predict the held-out dynamics of a dual-frequency,
two-station carrier-phase double difference better than a calibration-prefix
affine null and frozen wrong-orbit alternatives?

The proposed observable is not an absolute received frequency. It is the time
derivative of an ionosphere-free carrier-phase double difference:

```text
[(GOLD target - GOLD reference) - (NLIB target - NLIB reference)]
```

That coordinate removes nuisance dimensions structurally before asking a
detector to resolve them.

## Why this route was selected

Four physically different routes were compared at the block boundary:

1. two-station, two-satellite, dual-frequency GNSS double differences;
2. DSN ODF Doppler;
3. DSN Delta-DOR/VLBI with a quasar reference;
4. multi-satellite closure coordinates.

GNSS double differencing is the shortest path to a held-out observation whose
dominant clock, ambiguity and first-order plasma terms are removed by the
measurement coordinate itself. ODF remains closer to the Cassini absolute-
frequency problem. Delta-DOR is an excellent later route because the quasar
preserves angular information while cancelling station terms, but it requires
a new archival and pre-pass-orbit audit. A blind closure loop can cancel the
absolute orbital signature together with the nuisance and was therefore not
selected.

## Frozen screening inputs

- day: 2026-08-03 UTC;
- stations: GOLD00USA and NLIB00USA, two independent receiver/antenna/clock
  roots with external hydrogen masers;
- model: exact-hash GPS mixed broadcast navigation product
  `BRDM00DLR_S_20262150000_01D_MN.rnx`;
- geometry cadence: 30 s;
- minimum elevation: 15 degrees at both stations for target and reference;
- minimum continuous joint window: 2,400 s;
- calibration prefix: 20 percent;
- nulls: prefix-only affine extrapolation and other jointly visible GPS
  broadcast orbits passed through the same projection.

The broadcast navigation file has SHA-256
`a8be80bbc5ad857381b8b4d662a08c9fb56a015b78c928d084f32799077aeb24`.
The structural manifest has SHA-256
`68d5f24eca97ab35e0ba5fd4fc82b4ab753150c880f8a1014ef8a5b388761a12`.

## Observation products: existence only

On 2026-08-22 a metadata-only HTTP `HEAD` check returned 200 for:

- `GOLD00USA_R_20262150000_01D_30S_MO.crx.gz`, 2,197,353 bytes;
- `NLIB00USA_R_20262150000_01D_30S_MO.crx.gz`, 2,534,492 bytes.

The payloads remain unopened and therefore have no locally verified SHA-256.
The `30S` product-name field is not treated as proof of actual epoch
continuity, time quantization, phase availability or measurement resolution.

## Geometry shortlist

| Rank | Target / reference | Joint UTC window | Minimum elevation pattern | Controlling held-out separation |
|---:|---|---|---|---:|
| 1 | G11 / G21 | 10:01:30–13:13:30 | GOLD target/reference both about 15.1 degrees; NLIB reference 15.5 degrees | 2,156.819 Hz |
| 2 | G19 / G24 | 07:15:30–10:09:00 | three links at least 25.3 degrees; NLIB reference 15.0 degrees | 2,067.227 Hz |
| 3 | G18 / G20 | 13:19:00–16:19:30 | NLIB target and GOLD reference about 15.0 degrees | 2,034.003 Hz |

There are 176 qualifying geometry windows. The table deliberately keeps three
distinct target/reference pairs instead of three overlapping slices of one
pair.

Rank 1 is not yet the recommended physical experiment. Its slightly larger
geometric separation comes with three low-elevation links, so the differential
troposphere and multipath envelope may be worse than rank 2. Final selection
must maximize remaining physical margin after those terms are bounded; it may
not maximize raw geometry and then retrofit the envelope.

## Causal cut and residual terms

| Term | State before observation access |
|---|---|
| receiver clock | structurally cancelled by same-station satellite difference |
| satellite clock | cancelled by station difference, except the finite retarded-time remainder |
| integer carrier ambiguity | removed by time derivative only while every link remains cycle-slip free |
| first-order ionosphere | cancelled by a frozen dual-frequency combination |
| common receiver frequency reference | cancelled to first order by same-station satellite difference |
| troposphere and multipath | still require an outcome-independent differential envelope |
| antenna phase centre and signal-specific hardware bias | still require metadata/model admission or an explicit unresolved state |
| phase wind-up, Earth orientation, tides and relativistic conventions | must be identical in model and alternatives and bounded where non-common |

This is the principal SHOCK: the next useful experiment need not estimate each
large receiver error independently. It can choose a quotient observable in
which several nuisance coordinates are symmetries and disappear before the
held-out comparison. `UNRESOLVED` terms still do not become zero.

## Blockers before a prospective freeze

1. Materialization authority and complete-file hashes for the two exact
   observation products.
2. Header-only admission of matching dual-frequency carrier phase and LLI for
   all four links in one selected window.
3. Actual epoch continuity, receiver clock-offset semantics and phase
   quantization.
4. Outcome-independent bounds for differential troposphere, retarded-time
   satellite-clock coupling, multipath and signal-specific hardware/antenna
   effects.
5. A physical-margin comparison of the three windows. No observation values
   may enter that selection.

Only after these five items may one exact target, reference and held-out window
be frozen. The next block is therefore metadata/header admission plus a
differential physical-envelope compiler. It is not a detector, receiver
catalog, new gate family or observation run.

## Stop condition

Stop without opening measurement values if no candidate retains a positive
margin against every admitted physical envelope, or if either product lacks
the same four dual-frequency phase/LLI streams with continuous event time.
