# Bounded raw-GNSS capability consideration

## Terminal

```text
NO_FALSIFIABLE_RAW_TRACK_EXPERIMENT
```

This is a metadata-only result for one bounded set. It is not a global claim
about raw GNSS data, it does not reject either instrument family for other
questions, and it authorizes no sample access.

## Physical question

Can a currently reachable public raw-GNSS artifact support the already proven
anonymous-track/sealed-code-witness topology while leaving a negative orbital
result interpretable?

The minimum causal path considered here is:

```text
ADC-bound event time + simultaneous raw GNSS samples
    -> frozen acquisition/tracking
    -> anonymous continuous tracks
    -> orbital score receipt

same samples
    -> separately sealed code witness

after both hashes exist
    -> concordance / discordance / unresolved
```

This work can add physical information only by determining whether a real
measurement path can preserve the synthetic orbital distinction. Improving a
dataset inventory or receiver adapter would add none, so neither is built.

## Bounded set

Only two physically plausible public families were retained after
reconnaissance:

1. University of Texas TEX-CUP, May 9 and May 12, 2019, RadioLynx/NTLab raw
   IF;
2. LuGRE mission data, the published L1/E1 and L5/E5a IQ-sample products in
   Zenodo record `16411687`.

TEX-CUP is the long, continuous, dual-frequency ground route. LuGRE is the
immutable, reachable, dual-band space-receiver route. CTTC's 100-second L1
teaching capture, TEXBAT's replay/spoofing products, and the single-signal
SVN49 recordings are not expanded into a catalog because they already miss a
required causal edge: continuous duration with absolute sample-zero authority,
an unmodified live-sky physical path, or two anonymous code-bearing tracks.

No development, primary or reserve role is frozen by this consideration.

## Admission clauses

A family could enter a future proof only if all clauses below were supported
before sample access.

| Clause | Required evidence |
| --- | --- |
| raw measurement coordinate | pre-correlation complex IF/IQ retaining at least two simultaneous code-bearing signals |
| event time | sample zero tied to GPST/UTC with an explicit finite ADC-binding error |
| sample clock | declared rate plus a finite accuracy/stability envelope over the intended window |
| physical duration | enough independent temporal or simultaneous structure for an orbit-versus-null margin computed before access |
| oscillator | common terms cancel or project out; differential non-affine terms have a conservative bound |
| propagation | same-session dual-frequency witness or an independent conservative non-affine envelope |
| continuity | sample sequence and gap semantics make discontinuity detectable before scoring |
| orbit inputs | historical, outcome-independent transmitter and observer trajectories |
| artifact identity | immutable locator and checksum; full SHA-256 before decoding |
| witness separation | code identity is sealed outside the orbital scorer and revealed only after the score receipt hash |

`UNKNOWN` cannot satisfy a clause and is never converted to zero.

## TEX-CUP

### What is documented

The official description states that May 9 and May 12 each contain about two
hours of rover and reference data. The RadioLynx front-end records two-bit raw
IF at 10 MS/s with simultaneous L1 and L2 channels. Its published bit-packing
document identifies 4.2 MHz passbands, L1 C/A IF at
`2.503333333 MHz`, L2C IF at `2.516666667 MHz`, and two antenna branches.
The experiment paper says the RadioLynx sample clock is traceable to GPS time
and describes an external 10 MHz OCXO. The long duration and dual-frequency
coordinate are therefore the right physical shape for anonymous-track work.

### Session availability

The official TEX-CUP page still links to the public data root, but that root
is empty in the current session. Direct metadata-only `HEAD` requests to the
previously documented products returned HTTP 404:

- `2019May09-reference/radiolynx/radiolynx.bin`;
- `2019May12-reference/radiolynx/radiolynx.bin`;
- `2019May09-rover/ntlab/ntlab.bin`.

Search-index descriptions of former 60 GB, 71 GB and 370 GB objects are not
live capability evidence. No current immutable checksum or retrievable product
was demonstrated. The public papers also do not provide a numerical
sample-zero-to-ADC error bound for these exact files; the documented
sub-millisecond computer NTP bound is not an ADC bound.

```text
state = CAPABILITY_DESCRIBED_NOT_AVAILABLE_IN_SESSION
```

This family cannot supply development/primary separation until the same
official surface again exposes exact immutable products. No operator contact,
mirror search or adapter repair follows.

## LuGRE

### What is documented

Zenodo record `16411687` exposes one 256.1 MB `LuGRE.zip` object with published
MD5 `cec32df1ca17cb95887762762c16629f`. Its archive preview lists complex IQ
sample messages and their small SDR metadata companions without requiring the
IQ payloads to be opened.

The receiver product is multi-constellation and dual-frequency. The archive
contains same-operation L1/L5 pairs for OP32, OP37, OP38, OP40, OP73, OP74 and
OP76. Their individual captures are only `0.3--2.0 s`; the complete public
set is a collection of separated snapshots, not one continuous track window.
The OP40 listing also disagrees between a `300MS` L1 payload name and a
`400MS` metadata name, so duration must ultimately come from the exact
validated header rather than the filename.

The independent public Qascom-to-SigMF converter documents the IQS payload
header fields:

```text
receiver GPST
sample count
sample type and quantization
spectrum inversion
sampling frequency
central and intermediate frequency
bandwidth
CRC-24
```

It converts the receiver GPST field to the SigMF sample-zero timestamp. The
mission documentation says receiver time is synchronized to GNSS time after
first acquisition and then propagated by the common VCTCXO. It also reports a
10--15 minute startup frequency transient. Qascom publishes a generic 50 ns
timing performance for the receiver family, but the material inspected here
does not bind that number specifically to the first ADC sample of each LuGRE
IQS product. That bound therefore remains `UNKNOWN`, not `50 ns`.

The same front-end/FPGA oscillator is favorable for simultaneous track
differencing, and simultaneous L1/L5 snapshots could witness dispersive
propagation. Neither fact proves that the same two code-bearing satellites are
present and trackable on both bands in a sealed primary; that is signal-derived
and remains unopened.

### Clause result

| Clause | State | Reason |
| --- | --- | --- |
| immutable public artifact | `SUPPORTED_AT_ARCHIVE_LEVEL` | stable DOI, object size and MD5; full SHA-256 still required before decode |
| raw complex samples | `SUPPORTED` | IQS product type and reversible header layout are documented |
| simultaneous L1/L5 | `SUPPORTED_FOR_SEVEN_SNAPSHOTS` | paired operation timestamps are listed |
| continuous anonymous track | `NOT_SUPPORTED` | each product is 0.3--2.0 s and snapshots are separated |
| sample-zero GPST field | `SUPPORTED_DESCRIPTIVELY` | receiver GPST is present in the IQS header |
| finite ADC-to-GPST bound | `UNKNOWN` | generic receiver timing performance is not product-applicable ADC binding |
| sample-rate value | `HEADER_DECLARED_UNOPENED` | exact value is inside the unopened IQS header |
| sample-rate accuracy | `UNKNOWN` | no product-applicable numerical stability bound admitted |
| common oscillator topology | `SUPPORTED_DESCRIPTIVELY` | one VCTCXO feeds front-end and FPGA |
| non-affine oscillator envelope | `UNKNOWN` | startup transient exists; no exact per-product envelope admitted |
| dispersive witness | `POTENTIALLY_SUPPORTED` | paired L1/L5 exists, but common satellite availability is signal-derived |
| exact orbital discriminability | `NOT_EVALUATED` | no outcome-blind snapshot geometry sweep has been frozen |

```text
state = CAPABILITY_DISCOVERED_NOT_ADMITTED
```

LuGRE is real and reachable, but it does not instantiate the demonstrated
69-minute anonymous-track mechanism. Opening IQ now would allow sample content
to choose a replacement experiment post hoc.

## Conservative combined result

TEX-CUP has the required temporal shape but is not a live, immutable capability
in this session. LuGRE is live and immutable but has the wrong temporal shape
and two unresolved admission terms. Consequently neither family can currently
produce an interpretable negative for the frozen long-track mechanism.

```text
NO_FALSIFIABLE_RAW_TRACK_EXPERIMENT
```

This does not mean that no suitable dataset exists globally, nor that LuGRE
cannot support a different orbital experiment.

## SHOCK: replace temporal length with constellation structure

LuGRE exposes a better question than forcing snapshots into a 139-epoch
template:

```text
one simultaneous anonymous constellation snapshot
    -> vector/set of carrier frequencies across signals and bands
    -> common-clock projection
    -> frozen candidate-assignment surface
    -> opaque orbital receipt

separate code correlations on the same samples
    -> sealed identity receipt

after both hashes
    -> assignment concordance / discordance / unresolved
```

Here the discriminating dimension is the simultaneous multi-satellite Doppler
pattern, not a long temporal curve. L1/L5 can additionally expose dispersive
structure. Whether 0.3--2.0 seconds is sufficient is deliberately unknown.
The smallest next physical step is an **offline, metadata-only LuGRE
constellation-snapshot discriminability calculation** using operation times,
historical transmitter ephemerides and independent Blue Ghost geometry. It
must parameterize event-time and oscillator error, include permutation and
affine/common-clock nulls, and stop if every snapshot margin is absorbable.

That calculation would test a new physical observable; it would not be a data
adapter or another capability search. It must precede any IQ access.

```text
Physical question:
Can a simultaneous anonymous constellation-frequency pattern distinguish
candidate GNSS orbit assignments without a long temporal track?

New information produced:
Whether any published LuGRE snapshot has positive orbit-versus-null and
assignment-versus-permutation margin before signal content is inspected.

Why existing experiment cannot answer it:
The current spike proves a 139-epoch temporal coordinate. LuGRE supplies only
short simultaneous constellation snapshots, so its discriminating dimension
is across signals and bands rather than across 69 minutes.

Minimum experiment:
Propagate outcome-independent GPS/Galileo hypotheses to the independently
known Blue Ghost observer state on the listed operation times; form anonymous
simultaneous frequency sets; project a common clock; compare frozen
permutation, affine and geometry-destroying alternatives under parameterized
timing, oscillator and media envelopes.

Stop condition:
Stop NO_SNAPSHOT_DISCRIMINABILITY if every exact-operation margin is
non-positive, if reconstructed/outcome-conditioned transmitter geometry is
required, or if an unresolved term can absorb the controlling separation.
```

## Evidence boundary

- LuGRE ZIP, IQS payloads, TLM observations and signal-derived diagnostics:
  `0 bytes accessed`;
- TEX-CUP IF payloads: `0 bytes accessed`;
- no RF/GNSS sample was downloaded, decoded, ranged or persisted;
- only public HTML/PDF/text/source metadata, archive listings and HTTP `HEAD`
  status were inspected;
- no detector, acquisition loop, primary role or threshold was frozen.

## Public documentation used

- LuGRE mission data: <https://zenodo.org/records/16411687>
- LuGRE receiver/time architecture:
  <https://ntrs.nasa.gov/api/citations/20240012279/downloads/ION_GNSS_2024_ScienceInvestigations_Paper_v1.pdf?attachment=true>
- Qascom receiver specification:
  <https://www.qascom.com/products/gnss-receivers/>
- public IQS-to-SigMF parser:
  <https://github.com/daniestevez/lugre/blob/main/qascom_to_sigmf.py>
- TEX-CUP description: <https://radionavlab.ae.utexas.edu/texcup-desc/>
- TEX-CUP paper:
  <https://radionavlab.ae.utexas.edu/wp-content/uploads/texcup.pdf>
- RadioLynx bit-packing and channel definition:
  <https://rnl-data.ae.utexas.edu/texcup/2019May09-reference/radiolynx/bitpacking.pdf>
