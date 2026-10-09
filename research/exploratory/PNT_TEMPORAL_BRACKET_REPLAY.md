# UTC between NTS exchanges — exploratory exposed-capture replay

The [new report](results/pnt_temporal_bracket_replay_v1.json) replays the
[existing live NTS / synthetic UTC capture](PNT_CONCURRENT_TIME_QUALIFICATION.md).
It answers a software question: can bounded counter propagation support epochs
between exchanges, rather than requiring a receiver packet inside one network
round trip? There is no new acquisition, real GNSS measurement, RF attack,
independently benign baseline or P2 detection-benefit claim.

## Method and retained assumptions

Implementation: `b97232c3f4b8ceba63474e4b5790d967f99507ea`.
The existing `compare_receiver_capture` API accepts optional
`bracket_span_ns`; the CLI flag is `--bracket-span-ns`. Single-exchange results
stay separate and the default output is unchanged.

Two adjacent attempts at each configured endpoint supply the anchors: (0, 2)
for ptbtime1.ptb.de and (1, 3) for ptbtime2.ptb.de. Pairing uses retained order
and endpoint names, not UTC claims, residuals or the best round trip.
A failed intervening attempt cannot be skipped. Both PTB endpoints share one
authority; they are not combined into a quorum or independent consensus.

A solution bracket must lie wholly between the first receive and second send.
The causal UTC bound at the first receive is propagated forward, and the bound
at the second send backward, using outward-rounded elapsed-time bounds.
Their intersection constrains the event. Neither leg assumes symmetric delay.
Contradictory anchors, missing association, outside events and excessive spans
remain insufficient evidence. Delay can widen uncertainty and hide a fault.

The maximum complete outer span is explicitly **2 seconds in counter units**,
a development limit for the existing one-second round schedule. This is an
extension on already exposed observations, not a blind or preregistered test.
The original **1 ms server error, 100 ppm rate error, 1 ms claim error and
0–20 ms age assumption remain unchanged and uncalibrated**. The rate assumption
must now hold across the entire bracket span; the server bound applies at both
anchors. No parameter is fitted to receiver UTC or changed to obtain overlap.

Indices **36–38** already have independent source/receipt brackets outside
the retained age assumption. A derived copy marks each with
`epoch_age_budget_violation`; all its comparisons stay insufficient.
The original capture, bytes, failure evidence and results are untouched.
Absence of this marker does not certify the other uncalibrated assumptions.

## Outcome, with denominators

| Quantity | Retained result |
|---|---:|
| Receiver packets / original generated packets | 84 / 87 |
| Original single-exchange comparisons | 336: 3 inconsistent, 333 insufficient |
| Added bracket comparisons | 168: 57 inconsistent, 111 insufficient |
| Packets supported by a single exchange | 3 / 84 |
| Packets supported by a bracket | 45 / 84 |
| Packets supported by either method | 45 / 84 |
| Records explicitly rejected for known age failure | 3 / 84 |

Each of the three software variants has 28 captured packets, 15 with temporal
support, and 19 inconsistent / 37 insufficient bracket comparisons.
The 45 supported packets correspond to **15 seed epochs with three variants**;
they are not 45 independent observations. Some packets have support from both
endpoints, so comparison and record denominators must not be conflated.
Usable bracket widths are 55.284027–58.593412 ms under the declared assumptions.

Even the **host baseline remains inconsistent**, as do host +1 s and host -1 s.
This demonstrates expanded conditional time coverage, not a benign-versus-attack
success rate, fewer false alarms, RF authentication or calibrated accuracy.
Thirty-nine packets remain without support. Known age failures stay visible;
no latency budget is enlarged and no unavailable observation is replaced.

## Replay and next physical requirement

The report embeds the existing witness/capture records, original input hash,
implementation revision, the short temporary replay driver and its hash,
every comparison, known age violations and variant denominators.
Replay calls `compare_receiver_capture` with the embedded assumptions and
`temporal_association.maximum_span_ns`. Tests verify exact replay, unchanged
input packets/receipts/budgets, the original snapshot hash and age exclusions.
There is no new authority, verifier, permanent executor or replay protocol.

Saved NTS reports still require collector trust; symmetric authentication does
not make them transferable server signatures. For a physical P2 result, the
remaining requirement is a real GNSS UTC stream with defensible solution-age
and UTC-error bounds, then matched benign/challenge observations. This replay
does not resolve that requirement or justify further fitting to this baseline.

Original SHA-256:
`9afddab9cd9fc73e9fdf02de0f2e4e13085afac0c9bbb2dc8e06c4627e1efb42`.

New replay SHA-256:
`a530263f20783b4517a455c672581c48c9498961b5c09af88f78d118f835f830`.
