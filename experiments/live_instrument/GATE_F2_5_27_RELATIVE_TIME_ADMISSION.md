# Gate F2.5.27 — topology-derived relative-time admission

Gate F2.5.27 is an offline successor to the F2.5.26 attribution. It does not
reinterpret the consumed F2.5.25 run and does not connect to a KiwiSDR. It
materialises the temporal evidence that a new same-Kiwi, two-channel DDC trial
would have to preserve before destroying IQ.

```text
parent outcome: QUALIFICATION_INCOMPLETE
parent receipt SHA-256:
921deca68780b6546d19d4f8be2cb3cbb0ed5c9710d333f5dd24bf5d799b7380

live authority: false
retry budget: 0 pre-freeze, 0 post-freeze
RF persistence: ZERO
```

## The causal cut

The proposed experiment remains narrower than “observe an RF signal.” It asks
whether a feature changes under one per-channel NCO/DDC retune while another
channel remains fixed.

```text
shared: antenna → front-end → ADC → ADC sample clock → server clock state
                                      ├─ fixed reference DDC stream
                                      └─ controllably retuned DDC stream
```

Absolute UTC is necessary for cross-station alignment or an external event.
It is not intrinsically necessary to compare two branches derived from the
same ADC clock. This new plan therefore does not replace “GPS age ≤ 30” with a
larger number. It tests a different invariant: server sample timestamps must
advance exactly as the decoded sample counts predict.

## What must be retained

Every transient SND frame is hashed before analysis and then destroyed. The
future scalar receipt must retain:

- pre-analysis artifact hash and byte count;
- endpoint, branch role and server channel ID;
- SND sequence;
- actual GPS seconds and nanoseconds from the server header;
- the descriptive GPS-solution age byte;
- decoded sample count and negotiated sample rate;
- local monotonic arrival time.

These values are sufficient to test continuity and overlap. They are not RF,
waterfall, STFT or sample persistence.

The old F2.5.25 receipt retained sequence and age, but not actual timestamps,
sample counts or arrivals. It therefore remains unusable for this new test.

## Immutable admission clauses

The plan evaluates these clauses in order:

1. `pinned_same_adc_topology`
2. `same_endpoint_distinct_channels`
3. `scalar_metadata_complete`
4. `reference_sequence_continuity`
5. `perturbed_sequence_continuity`
6. `reference_sample_clock_continuity`
7. `perturbed_sample_clock_continuity`
8. `server_clock_error_codes_absent`
9. `same_sample_rate`
10. `common_server_time_overlap`
11. `absolute_gnss_freshness`

The last clause is explicitly `NOT_REQUIRED`, not silently satisfied. The
solution-age byte remains descriptive. Ordinary values 0–252 may enter the
relative-time test; reserved clock/error states 253–255 may not.

Continuity tolerance is derived from sample geometry, not fitted to an
outcome. For each adjacent frame:

```text
observed timestamp step
        versus
decoded_sample_count / sample_rate
```

The residual may not exceed one sample period. Sequences must be contiguous
modulo uint32. Both branches must use the same rate within the existing
`1e-6 Hz` equality tolerance. Their common continuous interval must contain at
least 2048 samples: two windows of the existing 1024-point STFT geometry.

## Initialization and GPS-week rollover

An initial all-zero timestamp is not treated as fresh time. It is excluded and
counted in the receipt. A later timestamp wrapping from the end of the GPS week
to zero is unwrapped only when a prior near-week-end value establishes a
forward jump larger than half a GPS week. An unexplained backward jump fails
sample-clock continuity.

This prevents the initialization value observed in F2.5.25 from masquerading
as a timestamp while still permitting a real week rollover.

## Command-boundary witness

Relative stream admission alone does not prove that a retune was applied. Each
future `A1_TO_B` and `B_TO_A2` transition must separately retain:

- command hash;
- local monotonic issue and settling-complete times;
- last pre-command perturbed frame hash;
- first post-settling perturbed frame hash;
- reference frame hashes bracketing the same boundary.

The boundary is witnessed only if:

- the fixed and perturbed channel identities remain distinct and stable;
- the last perturbed frame precedes command issue;
- the first admitted perturbed frame arrives after the frozen settling period;
- its server sample time advances beyond the end of the last pre-command frame
  by at least that settling period;
- the reference stream spans the same command issue time.

This closes timing and channel-continuity cuts. It still does not prove retune
application: the existing target-excluded distributed spectral witness must do
that before any target prediction is examined.

## Outcome semantics

`ADMISSIBLE_FOR_RELATIVE_TIME_EXPERIMENT`
: Every non-optional clause passes. The streams may enter local feature
  discovery. No feature or DDC-location claim is yet authorized.

`NOT_ADMISSIBLE`
: Metadata exist, but topology, sequence, clock continuity, rate or overlap
  fails. Feature extraction must not begin.

`QUALIFICATION_ERROR`
: No scalar measurement receipt can be evaluated. This is not a physical
  rejection.

`BOUNDARY_WITNESSED`
: One predeclared command/settling boundary is bracketed by both streams.

`BOUNDARY_NOT_WITNESSED`
: The intervention timing cut remains open; downstream feature comparison is
  `NOT_EVALUATED`.

None of these outcomes supports `UPSTREAM_OF_CHANNEL_DDC` or
`DOWNSTREAM_CHANNEL_FIXED`. They only decide whether those future hypotheses
would be testable.

## Synthetic controls

Offline fixtures prove that:

- two streams with GPS age 103 seconds can be admitted only when sequence,
  sample-time progression, rate and overlap all independently pass;
- sequence loss refuses admission before feature analysis;
- a timestamp jump refuses even with contiguous packet sequences;
- non-overlap and sample-rate mismatch remain distinct failures;
- reserved server clock states 253–255 cannot be mistaken for merely stale
  but ordinary time;
- initialization zero and real GPS-week rollover have different semantics;
- an invalid command/settling order cannot become a witnessed boundary;
- all results are strict finite scalar JSON with zero RF persistence.

## Authorized claim

The offline code demonstrates that a topology-specific relative-time contract
can distinguish data delivery from sample-clock admissibility without using an
external absolute-time root.

It does not demonstrate that any live capability currently satisfies the new
contract, that the prior session would have passed, that a stable feature
exists, or that a retune causes a predicted spectral displacement.

## SHOCK

The clock root is not universally “GNSS.” The required clock root is the one
that crosses the hypothesis boundary. For two independent receivers this may
be absolute event time. For two DDC branches of one ADC, sample-count closure
on the shared clock is a more direct witness—and stale absolute position fixes
need not destroy falsification power.

Shared hardware is therefore not only tolerated. At this causal cut it removes
propagation and oscillator differences that would otherwise weaken the
intervention. The cost is that local common-mode ADC artifacts remain upstream
of both channels and cannot be called external RF.

Gate F2.5.27 stops before any live seal or execution. The next admissible work
is a post-commit audit showing exactly where these scalars are captured and
destroyed in a one-use runner. No live authority is implied.
