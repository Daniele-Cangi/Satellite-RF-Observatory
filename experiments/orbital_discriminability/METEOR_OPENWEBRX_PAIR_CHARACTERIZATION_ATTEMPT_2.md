# METEOR OpenWebRX pair characterization — attempt 2

## Typed result

```text
QUALIFICATION_ERROR
DESCRIPTION_ERROR / NON_ATOMIC_CONFIG_OBSERVATION
DOWNSTREAM_MEASUREMENT_ADMISSION_NOT_EVALUATED
```

This was the single authorized replacement session.  It stopped before the
12-second capture with `DELIVERED_PROFILE_DOES_NOT_COVER_CARRIER`; it is not a
capability refusal and authorizes no RF or orbital claim.  No spectrum bin was
decoded or persisted, and there will be no automatic retry.

## Exact bounded attribution

The first collected concurrent future is the frozen
`OPENWEBRXNL_ALKMAAR` endpoint, and that future raised the exception.  The
YO3BN result is `NOT_EVALUATED`: concurrent execution does not authorize an
inferred result for a future that was never collected after the exception.

The runner at source commit
`c03b81e279da45c5f4a65f2cdc1889b82a9fe5d0` accumulated every incoming
`config` object into one dictionary.  It marked the target ready as soon as
the accumulated `sdr_id/profile_id` matched, then immediately interpreted the
accumulated `center_freq/samp_rate` as belonging to that identity.

That assumption is contradicted by the official OpenWebRX source at audited
commit `e3b9292e03c314fc87164a67184e69597e0e4ef3`.  In
`OpenWebRxReceiverClient.setupStack.sendConfig`, the initial call sends a full
configuration, while subsequent property notifications serialize only the
`changes` dictionary.  `setProfile` activates the selected profile through the
SDR source; it does not emit an atomic profile/config snapshot.  Therefore a
new identity can be observed while center/span still belong to an earlier
generation or have not yet arrived.

The failed diagnostic did not retain the exact delivered center/span, nor the
count/hash of binary frames discarded before admission.  Those facts are
`UNKNOWN_BY_FAILED_DIAGNOSTIC`, not zero.  This prevents deciding whether the
server would eventually have delivered a covering tuple.  The exact physical
capability remains unresolved.

## Minimal offline repair

The corrected runner accepts either:

- an initial complete target snapshot; or
- after an explicit selection, the exact target identity plus both
  `center_freq` and `samp_rate` observed in that selection generation, a
  positive FFT size and carrier coverage.

Identity alone can no longer combine with stale coordinates.  Pre-admission
binary frames are now length-prefixed into SHA-256 in RAM and destroyed
without decoding; any later descriptive failure now returns a strict receipt
containing their count, byte count and hash without preserving RF values.
Endpoints, carrier,
duration, frozen windows, scientific thresholds and retry policy are
unchanged.

This repair is offline only.  A further live execution requires a new,
explicit authorization.
