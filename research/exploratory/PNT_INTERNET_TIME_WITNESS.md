# Independent Internet time channel — development qualification

The new `python -m pnt time-probe` obtains authenticated Internet UTC and checks
a co-captured host clock reading. It addresses an observable missing from the
geometry workflow: a common time shift can cancel in double differences.
It is read-only and needs no GNSS/SDR hardware. This result qualifies transport
and conditional arithmetic, **not GNSS spoof detection, clock accuracy or P2**.

## Source and scope

PTB states that ptbtime1/ptbtime2 distribute UTC(PTB), synchronized via two fiber
paths to its atomic clocks independently of GPS. Its public servers support NTS
without registration. These are two endpoints of one authority, not two
independent clock sources. Source provenance is declared by PTB, not established
by packet authentication alone. [PTB clock source](https://www.ptb.de/cms/en/ptb/fachabteilungen/abt4/fb-44/ag-442/dissemination-of-legal-time/time-dissemination-via-the-internet.html),
[PTB NTS service](https://www.ptb.de/cms/en/ptb/fachabteilungen/abt9/gruppe-95/ref-952/time-synchronization-of-computers-using-the-network-time-protocol-ntp.html).

The [saved report](results/pnt_internet_time_v1.json) retains the two successful
NTS-KE feasibility contacts, two preliminary full exchanges, and the two final
CLI exchanges. No failed top-level probe was observed in this development session. The
initial clock discrepancy was exposed before the interval implementation;
this is exploratory software qualification, with no prospective claim.
The retained server UTC corresponds to 8 October 2026 UTC / 9 October locally.
Collector/runtime provenance and all numerical timestamps are in the JSON.

### Transport correction after PR review

The saved snapshot used the original TCP connector, which could try more than
one DNS address before succeeding. Address-level failures were not logged;
their historical count is unknown. The snapshot's statement that no Internet
attempt failed therefore establishes only successful top-level probes, not
an absence of failed TCP contacts. Its original bytes and numerical results
remain unchanged; this is a separate correction to the reporting claim.

The corrected client selects one TCP address and retains a failed connection
without trying another. If no NTP server is explicitly negotiated, UDP reuses
the authenticated TCP peer IP, preserving IPv6 scope/flow and the negotiated
port; an explicit redirect is resolved once. Reports now identify both peers
and whether redirection was negotiated. Opaque cookies of any length remain
unchanged at key establishment, with padding only in their NTP extension field.
Offline regressions cover these cases; no new Internet measurement or adjustment
to the UTC interval arithmetic, uncertainty budgets or saved result is required.

## Bound and trust assumptions

Let `s,r` be monotonic send/receive bounds, `R,T` the authenticated server
receive/transmit UTC, and `[a,b]` the monotonic bracket of the local UTC claim.
The event must lie wholly within `[s,r]` in the same collector capture domain.
With server UTC error `epsilon` and monotonic fractional rate error `rho < 1`,
nonnegative forward/backward delays imply:

```text
event UTC >= T - upper_elapsed(r - a) - epsilon
event UTC <= R + upper_elapsed(b - s) + epsilon
upper_elapsed(d) = ceil((d + 2 * counter_resolution) / (1 - rho))
```

Integer nanoseconds preserve precision; a further 1 ns allowance accounts for
NTP fractional timestamp conversion. Server processing exceeding the total
exchange plus the declared error is rejected. Overlap of claim/witness intervals
is `NOT_DISTINGUISHABLE`, disjoint intervals `INCONSISTENT_WITH_WITNESS`.
Missing authentication, unsupported time state, wrong capture or stale event
is `INSUFFICIENT_EVIDENCE` / an unavailable witness. There is no extrapolation.
The result never becomes ALLOW, RF authenticity, position validation or attack
attribution. An attacker increasing delay can hide a discrepancy by widening
the interval; the method cannot guarantee detection under denial of service.

This run declares **1 ms server error and 100 ppm monotonic rate error** as
uncalibrated development assumptions. Neither is a measurement of this machine
or a certified PTB bound. Root delay/dispersion stay server-reported metadata.
The result is conditional on these budgets, a sufficiently correct calendar
for TLS certificate validity, trusted platform roots, trusted collector/counter,
and an honest source within the budget. No weaker calendar bootstrap is used.

## Actual result

| Endpoint | Authenticated exchanges in final CLI | UTC interval width | Host minus witness UTC interval |
| --- | ---: | ---: | ---: |
| ptbtime1.ptb.de | 1/1 | 74.881789 ms | [-252.821942, -177.939953] ms |
| ptbtime2.ptb.de | 1/1 | 82.500686 ms | [-267.547961, -185.047075] ms |

Both report a host wall clock behind the witness interval under the declared
assumptions. **The host reading is not a GNSS measurement**; this is no evidence
of a cyber attack. Endpoints remain separate; no intersection or quorum is
presented as stronger independent evidence. No best-RTT selection, retries,
clock discipline, tuning or old-result changes were performed.

These widths cannot resolve the earlier synthetic 20 m common-code ramp
(about 67 ns). Deterministic tests exercise shifted UTC claims of 1 second and
smaller indistinguishable shifts, asymmetric delays, oscillator error, integer
boundaries, and widened uncertainty under delay. They demonstrate the time
mechanism, not the RF behavior of a receiver or population performance.

## Authentication and replay

The minimal single-exchange client follows [RFC 8915](https://www.rfc-editor.org/rfc/rfc8915.html)
for TLS 1.3, platform PKIX/hostname verification, ALPN, authenticated endpoint
negotiation, TLS exporter separation, AEAD_AES_SIV_CMAC_256 and request freshness.
AES-SIV and TLS use maintained libraries; no cryptographic primitive is
implemented here. Unprotected responses, modified headers/tags, replayed IDs,
wrong origin/key, bad framing, unknown critical KE records, missing cookies,
unsynchronized servers, leap-announcement states and unsupported modes fail
closed. Session secrets stay in memory and no NTP fallback is attempted.

The existing `compare_claim` function replays arithmetic from retained exchange
and claim fields; tests require equality with the saved comparisons. Saved
fingerprints do not authenticate the report to a third party. **NTS is symmetric,
not a transferable digital signature**; discarded keys cannot be used to
independently reverify a saved packet. Collector trust remains necessary. This
adds no seal, authority, experiment executor or separate replay framework.
The Linux/Windows positioning CI keeps its existing suites and adds these tests;
CI uses loopback TLS and offline packets, not public-server availability.

The next physical requirement is UTC from a receiver co-captured in the same
monotonic domain, with timestamp semantics and uncertainties established
independently. Current probes cannot authenticate 2023 Yunnan timestamps.
Recorded benign/challenge evidence and equal-false-alarm comparisons remain
open before any detection-gain claim or automatic security decision.
