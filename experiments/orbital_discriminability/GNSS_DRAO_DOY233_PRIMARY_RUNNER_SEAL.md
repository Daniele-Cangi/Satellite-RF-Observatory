# DRAO DOY233 one-shot primary runner

**DRAO_DOY233_PRIMARY_RUNNER_FROZEN_UNEXECUTED**

The final transport and execution boundary is frozen at source commit
`c40be1045469a956c046b64e1d940b2ecd79bb4c`. The runner binds the merged
artifact-selection receipt, the already frozen integrated parser/admission
core, opaque prediction bundle, identity reveal and scorer.

The one allowed execution has this immutable order:

```text
one-use authority marker
  -> exact same-locator GET (at most two pre-hash attempts)
  -> complete byte count and SHA-256 receipt persisted
  -> in-memory decompression
  -> attributable header and all-track admission
  -> opaque score receipt hash
  -> identity reveal
  -> one terminal outcome
  -> buffer zeroization
```

Transport retry is limited to timeout or interruption before any complete hash
exists. The implementation uses a complete same-locator restart rather than a
range resume. Once a complete artifact hash exists there is zero retry,
fallback, replacement date, station, feature or second execution.

`ARTIFACT_MATERIALIZATION_FAILED` and `DESCRIPTION_ERROR` produce
`PRIMARY_NOT_EVALUATED`; they cannot reject the physical hypothesis. A parsed
structural or predeclared physical-admission failure produces
`MEASUREMENT_INVALID` with the orbital score still `NOT_EVALUATED`.

This seal grants no live authority. At freeze, network requests, body bytes,
RINEX headers, observation values and scores all remain zero. No compressed
artifact, decoded RINEX, observation value or derived series has a persistence
path.

The official offline CI surface passes 1,625 tests.
