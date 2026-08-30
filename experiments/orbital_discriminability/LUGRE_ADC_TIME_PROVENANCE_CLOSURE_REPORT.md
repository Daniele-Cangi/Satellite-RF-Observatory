# LuGRE ADC-time provenance closure

## Outcome

```text
LUGRE_ROUTE_CLOSED_BY_ABSOLUTE_TIME_PROVENANCE
```

The positive OP76 geometry result remains exactly as frozen: the controlling
orbital-versus-null separation is `11.019310141610 Hz`, with a symmetric total
per-track RMS ceiling of `5.509655070805 Hz`. This audit neither recomputed nor
weakened that result.

The LuGRE path nevertheless closes before detector development and before any
IQS access. The bounded public record describes the intended time coordinate
and the receiver clock mechanism, but it does not publish a numerical,
product-applicable error from IQS ADC sample zero to true GPST/UTC.

The deterministic audit source is frozen at commit
`657019d7b50cbc9fe4fa3ef3cd2b9e8b1fbc671c`. The resulting 7,115-byte strict
JSON receipt has SHA-256
`68b6467fc7b1984031d9e20986ca618d8f25b50a373954f08c49919eb711f39e`.

```text
new IQS compressed payload bytes = 0
new IQS uncompressed bytes = 0
new IQ sample values = 0
new telemetry bytes = 0
new signal-derived diagnostics = 0
roles frozen = false
prospective plan frozen = false
```

## Physical question and information value

Can the public, outcome-independent record bind the LuGRE IQS sample-zero epoch
to true GPST/UTC tightly enough that a future negative can mean `NOT DETECTED`
rather than `PREDICTION EVALUATED AT THE WRONG EPOCH`?

This is the last metadata question on the route because it changes the physical
interpretability of the otherwise positive OP76 geometry. It is not a search or
provenance gate: failure closes LuGRE rather than creating another successor.

## Bounded evidence set

| Evidence | What it establishes | Why it does not close the bound |
| --- | --- | --- |
| LuGRE Receiver ICD issue 2.0 and Product Handbook, already frozen in the preceding receipt | `rxTime` is receiver time, the mission uses GPST, and `SC_Start` denotes actual IQS capture start | semantic names and millisecond fields do not quantify latch, synchronization or absolute-time error |
| NASA, *Science Objectives and Investigations for LuGRE*, NTRS `20240012279` | startup time is commanded by the lander; after first acquisition it is synchronized to GNSS and then propagated by the VCTCXO; IQS is collected at the ADC output | no operation-specific synchronization state, command latency, ADC latch error or residual clock-error number is published |
| NASA, *Navigation Performance Analysis and Trades for LuGRE*, NTRS `20220010106` | a typical space-grade VCTCXO model was used in preflight navigation simulations | Allan deviation bounds frequency stability over an interval, not initial absolute phase; the paper explicitly deferred measurement of the flight oscillator |
| Pulliero et al., *The Space Qualification Process of the LuGRE GNSS Payload* | functional and environmental qualification was performed on the receiver/payload models | the public manuscript provides no numerical end-to-end timing verification result |
| Qascom QN400-S public product-family page | a generic `50 ns` timing-accuracy performance is advertised | it is not bound to the custom LuGRE flight configuration, sample-capture mode, synchronization state or ADC sample zero |

Exact bytes and SHA-256 hashes for every newly inspected document are recorded
in `LUGRE_ADC_TIME_PROVENANCE_CLOSURE_RECEIPT.json`. The search is bounded to
the archive-native product documents, official NASA mission/clock documents,
the public preflight qualification manuscript and the manufacturer product
family page. It makes no claim that no private or future calibration exists.

## Causal ledger

| Edge | Semantic support | Finite product-applicable bound |
| --- | --- | ---: |
| ADC sample zero -> IQS `rxTime` tag | `SC_Start` is described as actual capture start | `UNRESOLVED` |
| IQS `rxTime` -> receiver reference time | the ICD defines `rxTime` as receiver time | `UNRESOLVED` |
| receiver reference time -> GPST | command/GNSS/VCTCXO mechanism is described | `UNRESOLVED` for the capture-specific state and residual |
| GPST label -> true GPST/UTC | intended time scale is described | `UNRESOLVED` end to end |

Because every end-to-end path contains at least one unbounded edge, no finite
ADC-to-true-GPST value can be composed. `UNRESOLVED` is not replaced with zero.

## Why the tempting numbers do not qualify

- The repeated `-0.001 s` SDRX/OPTABLE difference is a convention or
  representation fact. Both values can share the same clock error.
- The QN400-S `50 ns` figure is a family-level timing performance, not an IQS
  sample-zero specification for the custom flight unit.
- VCTCXO Allan deviation describes frequency stability, not initial absolute
  time offset, synchronization state or ADC tagging latency.
- A lander time command establishes a mechanism, not its end-to-end error.
- Postflight PVT clock-bias or startup-transient estimates are derived from
  received GNSS measurements and are outcome-conditioned for this purpose.
- Fitting a time phase from the future target RF would let the held-out data
  choose its prediction and is forbidden.

## Authorized claim

> Within the bounded public evidence set, LuGRE provides time semantics and a
> documented clock/synchronization mechanism, but no finite,
> product-applicable IQS ADC-sample-zero-to-true-GPST/UTC error bound.

Not authorized:

- a global assertion that no calibration exists;
- promotion of timestamp resolution, nominal sample rate or clock stability to
  absolute timestamp accuracy;
- opening OP73, OP76 or OP74 to estimate time from their signals;
- detector development, role freeze or any orbital measurement;
- weakening the frozen nulls with a free time phase.

## Closure and next physical route

OP73, OP76 and OP74 become closed, unopened candidates. The geometry work is
preserved as a useful demonstration that simultaneous multi-carrier snapshots
can be highly discriminative. It is not an executable prospective experiment
with the public timing provenance now available.

The next physical route must start orbit-first with a different raw-IQ family
whose numerical sample-zero time provenance exists before geometry is promoted
to a prospective plan. There is no automatic LuGRE successor.

## SHOCK

Common-clock multi-carrier projection removes offset and scale, but it cannot
remove the missing origin of the time axis: at a cislunar observer, changing
the epoch changes the four-satellite geometry itself. A beautifully reversible
frequency coordinate can therefore remain scientifically unusable for a
negative outcome because its absolute temporal coordinate is uncalibrated.

## Public sources

- LuGRE mission data: <https://zenodo.org/records/16411687>
- NASA mission time architecture: <https://ntrs.nasa.gov/citations/20240012279>
- NASA preflight clock model: <https://ntrs.nasa.gov/citations/20220010106>
- LuGRE qualification manuscript: <https://hdl.handle.net/11583/2986317>
- Qascom receiver family: <https://www.qascom.com/products/gnss-receivers/>
