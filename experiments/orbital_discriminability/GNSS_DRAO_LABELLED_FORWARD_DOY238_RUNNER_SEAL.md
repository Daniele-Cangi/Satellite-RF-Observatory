# DRAO labelled-forward DOY238 runner seal

**DRAO_DOY238_RUNNER_FROZEN_UNEXECUTED**

The one-use runner is frozen at commit
`8daa5727c0e0defbb0ef0fdccbe4f972fcbb1fa1`. Its source, runtime manifest,
executor seal and exact metadata-only artifact selection are hash-bound.

The runner has one URL, one product, one frozen experiment and no fallback.
It consumes its one-use authority receipt before network access, permits at
most two same-locator transport attempts before a complete hash exists, writes
the complete byte count and SHA-256 before decompression, and permits no retry
afterward. Compressed and decoded RINEX remain in volatile buffers and are
zeroed after one terminal outcome.

The seal grants no live authority. At seal time it had made zero network
requests and accessed zero body bytes, RINEX headers, observation values or
scores.
