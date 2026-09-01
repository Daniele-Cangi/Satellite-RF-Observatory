# METEOR OpenWebRX pair characterization — attempt 1

## Typed result

```text
QUALIFICATION_ERROR
DESCRIPTION_ERROR
DOWNSTREAM_MEASUREMENT_ADMISSION_NOT_EVALUATED
```

This is neither a capability refusal nor an RF/orbital outcome.  The one-shot
runner at source commit `eee7a7f7e1a0ef3dc68680401c3ff4b4dcf74098`
opened the qualification path, but stopped before the selected profile was
admitted.  No spectrum bin was decoded, interpreted or persisted.

## Exact attribution

`status.json` publishes the bare Alkmaar profile name `AIR 136 - 142`.  The
official OpenWebRX+ source shows that the WebSocket `profiles` message prefixes
every profile label with its SDR name:

```text
<SDR name> <profile name>
```

The audited upstream source commit is
`e3b9292e03c314fc87164a67184e69597e0e4ef3`.

The frozen runner required an exact comparison with the bare profile name.
It therefore rejected the descriptive label before checking the delivered
profile id, center, span or FFT configuration.  The first collected future is
the frozen Alkmaar endpoint, so the traceback attributes this exact failure to
`OPENWEBRXNL_ALKMAAR`.  The YO3BN downstream result is `NOT_EVALUATED`; the
concurrent control flow does not authorize an inferred result for it.

Any pre-admission binary frames were structurally discarded without decoding.
The failed diagnostic did not retain their count or hash, so those fields are
explicitly `unknown`, not zero.  No physical decision depends on them.

## Minimal offline correction

The corrected matcher accepts either the exact frozen profile name or the
official `<SDR name> ` prefix followed by that exact name.  It does not use a
substring search.  Profile id, delivered center/span, carrier coverage and FFT
size remain independent mandatory checks.  Capture duration, endpoints,
target carrier, forbidden windows, retry count and all scientific semantics
are unchanged.

The frozen retry count for attempt 1 was zero.  The corrected runner must not
be executed without a separate authorization for one replacement session.
