# Independent GNSS forward vertical — navigation-only review

## Outcome

`GNSS_INDEPENDENT_VERTICAL_READY_FOR_QUALIFICATION`

This is not a prospective-plan freeze and grants no observation access. The
review used one exact-hash broadcast navigation product, public IGS station
descriptions and HTTP `HEAD` metadata only. No observation payload, RINEX
observation header, epoch, carrier phase, SNR or LLI value was opened.

## Physical question

Can a new broadcast-orbit hypothesis predict a two-station held-out GNSS
coordinate better than a calibration-prefix affine null and jointly visible
wrong-orbit alternatives, after the same conservative physical envelope used
by the concluded GOLD–NLIB experiment?

The new information is a pass-specific geometry and detectability result for a
genuinely distinct qualification/primary structure. It does not repair, retry
or reinterpret the closed GOLD–NLIB primary.

## Bounded set and selection rule

Six explicitly scoped IGS stations produced eight predeclared pairs. Pair
selection applied this order:

1. documented antenna-calibration provenance required by the existing PCV
   envelope;
2. positive pairwise physical margin;
3. largest remaining physical margin;
4. deterministic pair-ID tie break.

This is not a receiver inventory. Station descriptions came from the official
IGS pages for [WTZA00DEU](https://network.igs.org/WTZA00DEU),
[ONSA00SWE](https://network.igs.org/ONSA00SWE),
[BRUX00BEL](https://network.igs.org/BRUX00BEL),
[DLF100NLD](https://network.igs.org/DLF100NLD),
[KIRU00SWE](https://network.igs.org/KIRU00SWE) and
[MAT100ITA](https://network.igs.org/MAT100ITA).

| Pair | Best remaining margin | Navigation-only state |
|---|---:|---|
| WTZA–ONSA | 1616.486636 Hz | excluded: public antenna-calibration provenance unknown |
| BRUX–ONSA | 834.371427 Hz | excluded: public antenna-calibration provenance unknown |
| WTZA–DLF1 | 150.953997 Hz | eligible |
| BRUX–DLF1 | -486.401180 Hz | below detectability |
| WTZA–BRUX | 51.711229 Hz | eligible but fragile |
| WTZA–KIRU | 3275.419030 Hz | eligible |
| KIRU–MAT1 | **5524.079066 Hz** | selected |
| WTZA–MAT1 | 1013.697831 Hz | eligible |

ONSA is not classified as physically unsuitable. Its stronger raw opportunity
is refused only because the current envelope explicitly claims provenance from
IGS robot-calibrated antennas and the public ONSA description leaves that
field blank. An unknown is not silently converted to zero.

## Selected orbital coordinate

- stations: KIRU00SWE and MAT100ITA, independent receiver/antenna roots;
- target/reference: GPS G20 / G22;
- controlling wrong-orbit alternative: G14;
- input UTC window: `2026-08-03T16:02:12Z` to `19:11:42Z`;
- input GPS labels: `16:02:30` to `19:12:00 GPS`;
- feature UTC window after derivative edges: `16:02:42Z` to `19:11:12Z`;
- feature records: 378 at 30-second cadence;
- calibration prefix: 76 records;
- held-out suffix: 302 records;
- minimum elevations: KIRU G20 `15.2073°`, KIRU G22 `15.0871°`,
  MAT1 G20 `41.7371°`, MAT1 G22 `32.9410°`.

The calibration feature labels run from `16:03:00` through `16:40:30 GPS`.
The held-out suffix begins at `16:41:00 GPS`; it may not fit any nuisance,
choose a signal family or change a threshold.

The measured coordinate remains the time derivative of the ionosphere-free
dual-frequency carrier-phase double difference:

```text
[(KIRU G20 - KIRU G22) - (MAT1 G20 - MAT1 G22)]
```

RINEX PRN labels and the broadcast product condition identity. A future result
can test forward predictive geometry, not independently establish transmitter
identity.

## Detectability envelope

| Frozen term | One-model held-out p-p bound |
|---|---:|
| direct station time shift, independently ±15 s | 11.191258 Hz |
| differential troposphere | 0.109631 Hz |
| RINEX carrier-phase quantization | 0.017418 Hz |
| broadcast-orbit path interval | 161.666414 Hz |
| higher-order ionosphere | 20.208302 Hz |
| antenna PCV and phase wind-up | 40.416604 Hz |
| multipath and signal-specific hardware admission limit | 40.416604 Hz |
| station displacement, EOP and relativity | 40.416604 Hz |
| satellite-clock retarded-time remainder | 40.416604 Hz |

The one-model envelope is `354.859437 Hz`; the symmetric pairwise comparison
reserves `709.718875 Hz`. The controlling orbital-versus-G14 separation is
`6233.797940 Hz`, leaving `5524.079066 Hz`. The prefix-affine separation is
larger (`6290.892123 Hz`) and therefore does not control.

MAT1 declares an internal clock. This does not itself invalidate the
coordinate because the same-epoch satellite difference removes the common
receiver-clock term to first order. It does make the delivered epoch semantics,
`RCV CLOCK OFFS APPL` state and same-record simultaneity mandatory qualification
clauses; none is inferred from the filename or `HEAD` response.

## Independent product roles

The products below are descriptions only. SHA-256 remains `unknown` until a
separately authorized materialization.

Qualification, DOY 214:

- `KIRU00SWE_R_20262140000_01D_30S_MO.crx.gz`, HEAD 200, 5,126,492 bytes;
- `MAT100ITA_R_20262140000_01D_30S_MO.crx.gz`, HEAD 200, 4,237,763 bytes.

Prospective primary, DOY 215, still sealed:

- `KIRU00SWE_R_20262150000_01D_30S_MO.crx.gz`, HEAD 200, 5,113,772 bytes;
- `MAT100ITA_R_20262150000_01D_30S_MO.crx.gz`, HEAD 200, 4,255,324 bytes.

The qualification day may establish only decoder-native record topology,
common dual-frequency signal families, epoch/clock semantics, continuation
handling and structural continuity. It cannot prove that the primary contains
continuous G20/G22 measurements or that a future negative will be detectable.

## Exact blocker and stop condition

The remaining blocker is:

`QUALIFICATION_PRODUCT_FIELD_TOPOLOGY_AND_DECODER_NATIVE_CONTINUITY_UNPROVEN`

A later, explicit authority may materialize and inspect only the two DOY 214
qualification products. Before any primary access it must freeze one exact
common signal family, structural parser, missing-field semantics and timing
convention. If the qualification products do not prove these, terminate the
GNSS route. Do not open the primary, switch stations, relax the coordinate or
create another parser gate.

The receipt is `GNSS_INDEPENDENT_FORWARD_REVIEW_RECEIPT.json`. It records zero
observation access, `qualification_access_authorized=false`,
`primary_access_authorized=false`, `prospective_plan_frozen=false` and
`new_gate_created=false`.
