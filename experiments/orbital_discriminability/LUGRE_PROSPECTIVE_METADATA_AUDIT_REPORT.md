# LuGRE prospective metadata audit

## Outcome

```text
LUGRE_PROSPECTIVE_PLAN_BLOCKED_BY_ADC_TIME_PROVENANCE
```

The positive OP76 geometry result is preserved. This outcome does not weaken
its `11.019310 Hz` orbital-versus-null separation. It says that the public
descriptive products do not yet make a negative RF result interpretable.

```text
roles frozen = false
prospective plan frozen = false
LuGRE IQS compressed payload bytes = 0
LuGRE IQ samples = 0
LuGRE telemetry bytes = 0
```

OP73 remains only a development **candidate**, OP76 only a held-out primary
**candidate**, and OP74 only a reserve **candidate**. None was opened or
authorized by this audit.

## Physical question

Can OP76 produce an interpretable negative for the frozen four-signal orbital
shape without deriving absolute time, frequency transforms or target identity
from the target RF itself?

The metadata-first causal path is:

```text
public operation record
    -> IQS capture-start semantics
    -> ADC-to-true-GPST bound
    -> common L1 frequency coordinate
    -> model-blind four-carrier estimator
    -> frozen orbital shape versus frozen nulls
```

The path currently breaks at the third arrow.

## Exact evidence boundary

The Zenodo v1 object is `LuGRE.zip`, `256135673` bytes, with published MD5
`cec32df1ca17cb95887762762c16629f`. Its ZIP end record declares 224 entries, a
`27306`-byte central directory at byte `256108345`, and an end-of-central-
directory record at byte `256135651`. The exact final 65,536-byte descriptive
range had SHA-256
`fdb21440968c1198d6215b77328138811be4176dc5817bc1630e17b3469186a4`.

Only these content classes were materialized:

- six small ION SDRX metadata companions for OP73/OP74/OP76 L1 and L5;
- `OPTABLE.csv` and the archive README;
- Qascom LuGRE Receiver ICD issue 2.0;
- the LuGRE Product Handbook;
- the independent public Qascom-to-SigMF source at commit
  `ae0bb3d0ce77cc6a924fe4e8fbd5d714f29b0494`.

The six `.bin` IQS entries are ZIP method 8 (DEFLATE). Therefore the embedded
62-byte IQS header is not byte-separable from compressed sample payload. A
header-only request would necessarily consume compressed sample information.
No such request was made. This is a measurement boundary, not a parser error.

The exact member offsets, compressed/uncompressed sizes, CRC-32 values and
metadata SHA-256 values are frozen in
[`LUGRE_PROSPECTIVE_METADATA_AUDIT_RECEIPT.json`](LUGRE_PROSPECTIVE_METADATA_AUDIT_RECEIPT.json).

## Product transform actually demonstrated

All six SDRX companions agree on the following reversible description:

| property | L1/E1 | L5/E5a |
| --- | ---: | ---: |
| sample rate | `8,000,000 Hz` | `24,000,000 Hz` |
| center frequency | `1,575,420,000 Hz` | `1,176,450,000 Hz` |
| translated frequency | `0 Hz` | `0 Hz` |
| spectrum inverted | `false` | `false` |
| sample type | complex IQ | complex IQ |
| quantization | 4 bit | 4 bit |
| packed width | 8 bit | 8 bit |
| binary header/footer | 62 / 3 bytes | 62 / 3 bytes |

The product handbook describes the filename timestamp as the start of I/Q
sample capture, and `SC_Start` as the actual SC start obtained from the IQS
packet header. The ICD says the IQS `rxTime` is receiver time and that the
mission used GPST. The independent converter interprets `rxTime` as GPST and
converts it to UTC for sample zero. These statements establish the intended
time coordinate. They do not quantify its error relative to true GPST/UTC.

The same-operation L1 and L5 SDRX timestamps are identical. The SDRX values
are consistently one millisecond earlier than `OPTABLE.csv`:

| operation | SDRX UTC | OPTABLE UTC | SDRX - OPTABLE |
| --- | --- | --- | ---: |
| OP73 | 2025-03-14 10:09:45.209 | 2025-03-14 10:09:45.210 | `-0.001 s` |
| OP74 | 2025-03-14 12:47:17.386 | 2025-03-14 12:47:17.387 | `-0.001 s` |
| OP76 | 2025-03-15 13:07:27.163 | 2025-03-15 13:07:27.164 | `-0.001 s` |

This repeated difference is a representation/convention fact. It is not a
measured ADC-to-UTC accuracy bound.

## What the affine coordinate removes

The four future L1 coordinates would come from the same simultaneous sample
file. The frozen geometry score projects one common frequency offset and one
common positive frequency scale for every orbital hypothesis and every null.
Consequently:

- a shared LO offset is not a separate orbital discriminator;
- a shared sample-rate scale error is not a separate orbital discriminator;
- a shared affine receiver-frequency error is not silently counted as orbital
  information.

This cancellation is conditional on a future detector using identical sample
and frame support for all four carriers. Signal-dependent frame rejection or
unequal weighting could turn a common time-varying clock term into differential
error. That rule belongs in a future detector manifest; it is not inferred from
the nominal sample rate.

## Detectability remains plausible, not admitted

| candidate role | operation | duration | native whole-window FFT spacing | frozen separation | symmetric total RMS ceiling |
| --- | --- | ---: | ---: | ---: | ---: |
| development candidate | OP73 | `2.0 s` | `0.5 Hz` | `5.033680 Hz` | `2.516840 Hz` |
| primary candidate | OP76 | `2.0 s` | `0.5 Hz` | `11.019310 Hz` | `5.509655 Hz` |
| reserve candidate | OP74 | `0.5 s` | `2.0 Hz` | `6.328409 Hz` | `3.164205 Hz` |

The native Fourier spacing is inside each geometry ceiling. It is not a carrier
estimator error bound, a detection threshold or proof that all four frozen L1
signals are present. No detector was implemented and no signal identity was
inspected.

## Clause audit

| clause | state | consequence |
| --- | --- | --- |
| archive identity | `SUPPORTED_AT_ARCHIVE_LEVEL` | immutable DOI/object identity and central-directory member identities exist |
| L1/L5 simultaneity | `SUPPORTED_DESCRIPTIVELY` | each candidate has equal L1/L5 SDRX timestamps |
| frequency-axis transform | `SUPPORTED_BY_SDRX_METADATA` | baseband, center, rate and inversion are described |
| exact IQS header identity | `NOT_EVALUATED_SAMPLE_BOUNDARY` | DEFLATE prevents header-only access without sample bytes |
| capture-start semantics | `SUPPORTED_DESCRIPTIVELY` | handbook and ICD define intended start/receiver-time roles |
| finite ADC-to-true-GPST bound | `UNRESOLVED` | millisecond representation and generic product performance are not accuracy provenance |
| model-blind detector error | `NOT_EVALUATED` | detector development is premature |
| four frozen L1 carriers present | `NOT_EVALUATED_PRE_SCORE` | future absence must remain pre-score invalidity |
| physical correction envelope | `NOT_EVALUATED_AFTER_BLOCKING_CLAUSE` | satellite-clock residual, differential media and estimator weighting remain open |

The Qascom public QN400 family page advertises `50 ns` timing accuracy, but it
does not bind that number to LuGRE IQS sample zero, the flight configuration,
the capture mode, or these three products. It is therefore not admitted.

## Why the missing time bound controls

The geometry sweep showed that OP76 preserves the selected family at the
tested `+/-10 s` offsets but not at `+/-60 s`. That was a discrete sensitivity
test, not a product accuracy statement and not a proof of every intermediate
time. An unbounded time phase would let the target samples choose which orbital
prediction they resemble and would weaken the held-out test.

Neither timestamp precision, filename agreement, nor a time estimate recovered
from the future target signals can replace an outcome-independent finite bound.
Until such provenance exists, `NOT DETECTED` cannot be distinguished from
`PREDICTION EVALUATED AT THE WRONG ABSOLUTE EPOCH`.

## Authorized and unauthorized statements

Authorized:

> The public OP73/OP74/OP76 companions describe simultaneous dual-band complex
> sample products with a common, reversible L1 frequency coordinate whose
> nominal Fourier resolution is compatible with the previously frozen geometry
> margins.

Not authorized:

- that the SDRX millisecond is accurate to one millisecond;
- that QN400's generic `50 ns` applies to these ADC samples;
- that G31/G28/G26/G10 are present in OP76;
- that a detector can meet `5.509655 Hz` error;
- that differential media or broadcast-clock residuals fit the margin;
- that OP73/OP76/OP74 roles or any prospective threshold are frozen;
- any orbital measurement or null rejection.

## Stop and minimum next physical step

Stop before detector development and before any IQS access.

The only admissible next step on this route is a bounded, outcome-independent
provenance result that numerically binds these IQS capture starts to the ADC and
true GPST/UTC. It must not use OP76 RF content, target identities, orbital
residuals or a free fitted time phase. If no such product-applicable evidence
exists, the LuGRE route closes despite its attractive geometry.

Only after that clause passes would the still-open satellite-clock, media and
detector envelopes be worth compiling.

## SHOCK

The simultaneous snapshot topology eliminates more receiver uncertainty than a
long track: common LO and sample-scale errors can be projected out across the
four same-file carriers. Yet one apparently mundane cross-domain binding - ADC
sample zero to true orbital epoch - still controls whether absence means
anything. Excellent RF metadata can describe *where* every bin lies while
remaining insufficient to say *when* the orbital hypothesis was tested.

## Public sources

- LuGRE mission-data record: <https://zenodo.org/records/16411687>
- Qascom receiver family specification: <https://www.qascom.com/products/gnss-receivers/>
- ION GNSS SDR Metadata Standard: <https://sdr.ion.org/>
- independent IQS interpretation:
  <https://github.com/daniestevez/lugre/blob/ae0bb3d0ce77cc6a924fe4e8fbd5d714f29b0494/qascom_to_sigmf.py>

