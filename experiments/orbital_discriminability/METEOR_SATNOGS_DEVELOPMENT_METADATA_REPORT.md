# METEOR-M N2-4 SatNOGS development metadata characterization

## Outcome

```text
SATNOGS_DEVELOPMENT_METADATA_PATH_BLOCKED
development observation IDs opened: 14904366, 14907984
signal values / waterfall pixels exposed: 0
primary artifacts opened: 0
detector built: no
```

This bounded characterization exercised only the two previously declared
development observations. The four primary candidates `14919555`, `14919561`,
`14919551` and `14919554` remain sealed and are still not a frozen primary
pair.

The terminal is a measurement-transform refusal, not a negative orbital
result. Geometry remains positive, but this product pair cannot carry the
frozen orbit-versus-null comparison.

## Access boundary and immutable identity

Every complete file was hashed before parsing. HDF5 value access was limited
to `relative_time`, `absolute_time` and `frequency`. The `data`, `offset` and
`scale` datasets were described structurally but never indexed. PNG `IDAT`
chunks were hashed and skipped by seek; they were never decompressed.

| Observation | Product | Bytes | SHA-256 |
|---:|---|---:|---|
| 14904366 | SatNOGS HDF5 artifact v2 | 3,781,711 | `cbf9ec168433144454853fe4190e9070d278d8c5e5bf68aaf3bfdbf98c60a750` |
| 14904366 | PNG display raster | 1,400,594 | `4c0cd9fcf051d0b211c2694127bc6d2de02068db7c0c6d2050d2cb94a6fb2a21` |
| 14907984 | PNG with embedded native-header configuration | 1,390,034 | `f1eb5a5d486cf160353a3de5fa3cc5a7348d37a84c91454d317b5a2272d410a6` |

The parser source hash is
`d1bf76991ef02b61d699fed534f9c4ac90df43e67b7a90d79966566decf6a6bd`.
The complete machine-readable receipt is
[`METEOR_SATNOGS_DEVELOPMENT_METADATA_RECEIPT.json`](METEOR_SATNOGS_DEVELOPMENT_METADATA_RECEIPT.json).

## Development receipt A — OE9BKJ / 14904366

The HDF5 product contains a `4702 × 1024` uint8 waterfall plus three native
coordinate vectors. Only those vectors were read.

| Property | Observed value | Interpretation |
|---|---:|---|
| artifact center frequency | 137,900,000 Hz | metadata value; the stored frequency vector is relative baseband |
| native baseband span | 160,000 Hz | `-80,000` through `+79,843.75` Hz |
| native bin count | 1,024 | coordinate length |
| native bin spacing | 156.25 Hz | exact coordinate spacing, not an ENBW claim |
| effective spectral resolution | unknown | window and equivalent-noise bandwidth are not exposed |
| nominal row cadence | 0.096 s | exact spacing of the relative-time grid |
| median event-time cadence | 0.089263 s | measured from the independent absolute-time vector |
| event-time cadence range | 0.006688–0.901252 s | observed client-clock intervals |
| event-time interval | 13:21:45.309990–13:29:17.268987 UTC | artifact client timestamp plus stored microseconds |
| gaps above 1.5× nominal | 2 | structural continuity result, not a signal result |
| explicit sequence number | absent | monotonic client row time is the only continuity witness |

The HDF5 attribute labels `absolute_time` as seconds, while the stored values
are microseconds relative to `start_time`. The relative and absolute duration
coordinates differ by `0.662997 s`, and their pointwise disagreement reaches
`0.932407 s`. Both facts are retained rather than silently normalizing one
clock to the other.

All datasets use HDF5 gzip level 4. The signal raster is uint8 and has separate
offset/scale datasets, so an amplitude quantization/clipping transform exists;
its values were intentionally not accessed. The legacy PNG has no embedded
native-header metadata and is only a `823 × 1603` RGBA display raster.

## Development receipt B — SA1CKW / 14907984

Only a `832 × 1603` RGBA PNG was published through the examined product path.
Its permitted text chunks expose the native producer configuration:

| Property | Observed value | Interpretation |
|---|---:|---|
| center frequency | 137,900,000 Hz | native-header configuration |
| sample rate / span | 160,000 Hz | product input span; not spectral resolution |
| native bin count | 1,024 | producer configuration |
| native bin spacing | 156.25 Hz | `sample_rate / nchan`; not an ENBW claim |
| FFTs per native row | 15 | producer configuration |
| nominal native row cadence | 0.096 s | `15 × 1024 / 160000` |
| native timestamp | 2026-08-29 13:22:48.269677 UTC | client header time |
| displayed time extent | 0.401203–610.490885 s | plot metadata only |
| actual native row event-time sequence | absent | cannot audit continuity or gaps |
| pixel-to-native-bin map | absent | displayed pixels cannot be treated as FFT bins |

The PNG uses DEFLATE compression. Overlap, FFT window/ENBW, raster resampling
and the precise mapping from native rows/bins to display pixels are not
exposed. Consequently `156.25 Hz` is a native coordinate spacing, not the
defensible effective resolution of the delivered display product.

## Timing semantics

Neither development receipt supplies a documented numerical binding from ADC
sample time to a server-disciplined UTC clock. OE9BKJ exposes a useful
client-clock row sequence, but its absolute UTC error remains `UNKNOWN`.
SA1CKW exposes a client start timestamp and aggregate plot extents, not the
native row timestamp sequence. There is therefore no defensible finite pair
bound for held-out row alignment.

## Transform ledger and controlling blocker

The observed causal path is:

```text
station RF front end
→ receiver samples
→ deployed SatNOGS flowgraph
→ model-driven Doppler compensation
→ native FFT accumulation
→ native row/bin coordinates
→ optional HDF5 uint8 offset/scale transform
→ PNG plot/raster/compression
```

The official source audit established that the waterfall is downstream of
the Doppler compensation block. The concrete products reveal neither the
applied correction samples/polynomial nor an exact deployed flowgraph commit.
This matters even when the geometry-only separation is large: the frozen
orbit and every null must receive the same actually applied control before a
recorded-baseband residual can be compared.

Two independent blockers remain:

1. SA1CKW does not preserve the native row event-time sequence or a reversible
   pixel-to-native coordinate mapping.
2. Neither root exposes the applied Doppler control trace with a finite error
   envelope.

Recreating the nominal correction from the same TLE would not solve either
problem; it would reinsert the tested model and leave update timing,
quantization and deployed implementation differences unbounded.

## Decision

```text
geometry:                              POSITIVE, unchanged
native frequency configuration pair:  PRESENT
native row event-time sequence pair:   ABSENT
applied Doppler-control trace pair:     ABSENT
model/null transform equivalence:       NOT DEMONSTRATED
detector development:                  NOT AUTHORIZED
primary access:                        ZERO
```

The SatNOGS route is closed for the first METEOR forward vertical. No repair
of the PNG path, artifact API or flowgraph provenance is justified inside this
experiment. The smallest scientifically different next move is to select a
predeclared product family that preserves raw pre-Doppler samples or a fully
reversible receiver-control ledger with bounded event time. That selection
must return to the orbital question; it must not become another receiver
catalog.

## SHOCK

The apparent instrumental margin was not controlled by the `156.25 Hz` bin
spacing. It was controlled by whether the delivered coordinate still contains
the orbital effect being tested. A high-resolution raster downstream of an
unrecorded model-driven control can be less falsifiable than a coarser raw
pre-control product.
