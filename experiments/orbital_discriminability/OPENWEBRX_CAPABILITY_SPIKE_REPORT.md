# Bounded OpenWebRX capability characterization

Date: 2026-08-19  
Scope: DC7JZB Berlin and PI4UTR Utrecht only  
Frozen target/shortlist changes: ZERO  
G0/G1 code changes: ZERO  
Orbital or RF feature claims: ZERO

## Outcome

```text
MEASUREMENT_PATH_INSUFFICIENT
```

The two receivers remain a useful predeclared geometric pair, but the product
actually delivered to a public OpenWebRX client does not currently satisfy the
measurement semantics needed to reinterpret a negative held-out result.

The G1 shortlist was not recalculated. Recalculation was conditional on both
receivers becoming admissible; that condition was not met.

## Bounded method

The spike ran outside every frozen shortlist window. It requested the already
declared `436-438 MHz` profile and inspected only configuration messages,
WebSocket frame type/length, client arrival times and incremental hashes.

Spectrum values were never decoded, interpreted or persisted. There was no
LO-19 search and no feature selection. The successful PI4UTR stream was hashed
in RAM and discarded. DC7JZB frames from the operator-locked non-target profile
were discarded before admission and were not used as physical evidence.

Two early DC7JZB attempts failed descriptively: first on a transient
`center_freq: null`, then because the initial diagnostic did not retain the
remote refusal description. Neither error was treated as a capability refusal.
The final diagnostic observed the server's explicit refusal.

## Receipt A — DC7JZB Berlin

The status description still advertised RX2 `436-438 Mhz`, center
`436,995,000 Hz`, sample rate `2,400,000 S/s`. The real WebSocket session exposed
global `fft_size=2048` and `fft_compression=adpcm`, but the server did not switch
to that profile. It returned:

```text
This profile is locked, keeping current profile.
```

The product actually delivered was the locked `APRS & LORA` profile:

| Property | Observed value |
|---|---:|
| Center | 433,400,000 Hz |
| Span/sample rate | 2,000,000 Hz |
| FFT size | 2,048 bins |
| Bin spacing | 976.5625 Hz |
| Compression | ADPCM |
| Target carrier covered | No |

Frame cadence and arrival gaps were not retained after the pre-admission
profile refusal and therefore remain `unknown`. This is not repaired by using
the advertised target profile or by calculating a hypothetical target-profile
bin spacing.

DC7JZB result: `NOT_ADMITTED — TARGET_PROFILE_LOCKED`.

## Receipt B — PI4UTR Utrecht

PI4UTR accepted the requested profile and delivered spectrum frames:

| Property | Observed value |
|---|---:|
| Center | 437,000,000 Hz |
| Span/sample rate | 2,048,000 Hz |
| Effective covered interval | 435,976,000–438,024,000 Hz |
| FFT size | 4,096 bins |
| Bin spacing | 500 Hz |
| Compression | ADPCM |
| Retained frame descriptors | 110 over 12.168 s |
| Overall arrival cadence | 8.958 Hz |
| Median arrival interval | 0.096881 s |
| p95 arrival interval | 0.213321 s |
| Maximum arrival interval | 0.224569 s |

These are client-arrival measurements. The 21 intervals above twice the median
show transport burstiness, but cannot establish lost FFT frames because the
protocol carries no sequence number.

PI4UTR result: `NOT_ADMITTED — EVENT_TIME_AND_SEQUENCE_NOT_BOUNDED`.

## Protocol and transform audit

The official OpenWebRX 1.2.1 source and observed wire behavior agree on the
following path:

```text
RTL-SDR source
→ complex-float server buffer
→ FFT
→ LogPower or LogAveragePower
→ FFT-side swap into centered order
→ optional ADPCM (enabled on both endpoints)
→ WebSocket binary frame type 1
→ client arrival
```

The client configuration exposes FFT size and compression. It does not expose
`fft_fps`, `fft_voverlap_factor`, the averaging count, an FFT-frame timestamp or
a sequence number. Consequently:

- actual overlap and multi-FFT averaging remain `unknown`;
- no upstream resampling is demonstrated, although none is declared inside the
  spectrum thread itself;
- ADPCM is lossy and log-power removes phase;
- FFT binning and possible averaging can broaden or smooth a ridge;
- `FftSwap` establishes centered bin order but unexposed RTL oscillator PPM and
  LFO offset can shift the absolute frequency axis;
- client UTC/monotonic arrival is not sample event time.

The tightest defensible temporal statement is one-sided:

```text
spectrum event time <= client arrival time
```

No finite maximum event-time error follows from the protocol or this short
session. HTTP `Date`, measured arrival cadence and network round-trip time do
not close unknown server processing, queueing or transport delay.

## Exact residual blocker

The immediate pair blocker is conjunctive:

1. DC7JZB did not deliver the required band because the advertised profile was
   operator-locked at runtime.
2. Even on PI4UTR, the public spectrum product has no server-side frame time or
   sequence continuity, so a held-out Doppler ridge cannot be assigned a finite
   event-time error or missing-data bound.

The measured `500 Hz` PI4UTR bin spacing is far coarser than the earlier
conditional `5 Hz` reference envelope, but it was not used to reject the pair
by itself. The hardened G1 margin must only be recomputed after both offers have
admissible timing, continuity and target-band delivery.

The two atomic machine-readable receipts are retained in
`OPENWEBRX_CAPABILITY_RECEIPTS.jsonl`. The ephemeral characterization program
had SHA-256
`19493a0dd6d7d7ba1c37090a58bc2452f50f867c9d9521412a20625fb4740f51`.
