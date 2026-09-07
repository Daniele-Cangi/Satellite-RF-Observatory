# DRAO DOY233 integrated primary executor

**DRAO_DOY233_INTEGRATED_PRIMARY_EXECUTOR_FROZEN_ARTIFACT_UNSELECTED**

The experiment-specific offline core is frozen at source commit
`505237d3fa962a441e8a7a8389e854120881d9da`. Its canonical source SHA-256 is
`b7f46defd23001d553952ca38f5f6f8eee43dbd37ac996842167df030d0fd2cc`.

The core parses every GPS track in the frozen 139-epoch window, admits exactly
seven tracks only from complete L1C/L2W/C1C/C2W and zero-LLI structure, applies
the geometry-free bound, and evaluates the same-path phase/code witness for all
seven possible exclusions. No PRN subset is selected before admission.

Only opaque track IDs and the 10,087-hypothesis symmetric orbital,
time-reversed and affine surface reach the scorer. The code-label mapping is
hashed in RAM before scoring; the model and track identity reveal occurs only
after the opaque score receipt hash exists. Observation and derived values have
no persistence path.

Real execution currently hard-refuses `PRIMARY_ARTIFACT_UNSELECTED`. The DOY233
logical product, locator, byte count and complete SHA-256 are all still absent;
there has been no network request, header read, payload access, observation
decode or orbital score. Selection and one-use execution require a later,
separately reviewed exact artifact authority.

The official offline CI surface passes 1,611 tests.
