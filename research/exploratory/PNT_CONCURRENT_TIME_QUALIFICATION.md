# Concurrent UTC collection — live transport qualification

The [retained report](results/pnt_concurrent_time_transport_v1.json) exercises
`time-capture` against real PTB NTS endpoints and a **synthetic UBX/TCP source**.
It tests interoperability without GNSS/SDR instruments. No GNSS measurement,
RF attack, independently benign interval or P2 detection benefit is claimed.
The UTC variants are host wall-clock readings plus fixed software offsets;
receiver validity flags and iTOW are synthetic. Nothing is fitted to NTS.

## Inputs and controls

On 9 October 2026, collector revision `bfe9b2df7c5b002a86c5847cd8da254fcf084d7f`
sampled ptbtime1.ptb.de and ptbtime2.ptb.de in two declared rounds, with
one-second round-start offsets. Both endpoints share the same PTB authority.
Each hostname was probed once per round, without automatic retries, clock
adjustment or address replacement. Existing TLS/hostname/AEAD checks apply.

The virtual source emitted three UTC packets every 50 ms: the host reading,
that reading plus one second, and that reading minus one second. Its original
packets and independent monotonic brackets around seed generation are saved.
The full temporary driver, its hash, Python/library versions and acquisition
configuration are embedded in the report; no additional executor is required.
The original factory is `packet` in `pnt/tests/test_time_capture.py` at the
recorded revision. The source is never described as an RF receiver.

Before access, development assumptions were set to 1 ms server error, 100 ppm
counter rate error, 1 ms software-claim error and 0–20 ms source-to-receipt age.
These are **uncalibrated assumptions**, not metrological bounds. In particular,
the host baseline was not independently qualified as correct UTC or benign.
The NTS era was explicitly zero. No budget changed after seeing the results.

## Retained outcome

- **4/4 authenticated NTS exchanges**, with send/receive spans of 33.283,
  42.808, 33.899 and 36.442 ms in request order.
- **84 received packets / 87 generated packets**; the final three generated
  packets are outside the retained acquisition. All generation records remain
  visible. The stream retained 2352 bytes without parser errors or truncation.
- **336 receiver/witness pairs**, of which 333 are insufficient evidence
  because their solution brackets are outside the individual NTS exchange.
  Only three pairs are evaluable, all against the second endpoint in round 0.
- Three other packets, indices 36–38, have independently observed age
  22.2552–22.3236 ms, exceeding the assumed 20 ms maximum. The violation stays
  in the report; their comparisons were already insufficient. It is not repaired
  by enlarging the bound or relabeling the qualification as calibrated.

| Software variant | Inconsistent pairs | Insufficient pairs | Claim minus witness for the evaluable pair |
|---|---:|---:|---|
| Host baseline | 1 | 111 | [-459.217107, -392.396219] ms |
| Host +1 s | 1 | 111 | [540.782893, 607.603781] ms |
| Host -1 s | 1 | 111 | [-1459.217107, -1392.396219] ms |

The three evaluable pairs share one source epoch and one conditional witness
interval of width 64.820888 ms. **Even the host baseline is inconsistent**
under the declared assumptions; this is not a benign-versus-attack success
rate, a false-alarm estimate or proof of GNSS spoofing. A discrepant host clock
is also visible in the earlier [host-only qualification](PNT_INTERNET_TIME_WITNESS.md),
whose original bytes and results remain unchanged. No time series between the
two sessions, cause attribution or clock-accuracy claim is established.

## Replay and next physical question

The existing `compare_receiver_capture` replays every embedded record and
witness attempt offline. A reusable retained-capture regression checks exact
arithmetic, stream hashes, variant denominators and the independently observed
age-budget failures. Saved NTS reports require collector trust and are not
transferable server signatures.

The result establishes that the collector interoperates with live NTS and
retains failures, while **temporal coverage is poor** in this schedule. A real
receiver's cadence, buffering and independently bounded solution age may
reduce it further. Do not filter these failures or tune a latency budget to
obtain a favorable result. The next physical question is whether an available
GNSS source and defensible timing bounds provide enough simultaneous support
for useful comparison; a synthetic source cannot answer it.

Snapshot SHA-256: `9afddab9cd9fc73e9fdf02de0f2e4e13085afac0c9bbb2dc8e06c4627e1efb42`.
