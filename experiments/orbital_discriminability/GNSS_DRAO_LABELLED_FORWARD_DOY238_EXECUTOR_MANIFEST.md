# DRAO labelled-forward DOY238 executor

**DRAO_DOY238_EXECUTOR_FROZEN_ARTIFACT_UNSELECTED**

The experiment-specific offline executor is frozen at source commit
`93e4c2dacbc503516c4f5fa1cfb43e7353655adf`. It binds the raw SHA-256 of the
prospective plan and prediction bundle, the NumPy version and every numerical
admission and decision parameter. It contains no locator, transport, fallback
or generic adapter.

The real entry point verifies the frozen local inputs and stops with
`DRAO_DOY238_ARTIFACT_UNSELECTED`. A separately reviewed, immutable selection
receipt is required before any observation network request or file open.

## Frozen execution boundary

The future one-use path is:

1. composite DRAO identity, with `MARKER NAME` descriptive rather than a
   literal alias;
2. all 139 normal epochs and all L1C/L2W/C1C/C2W fields for the fixed
   G14/G15/G17/G20/G24/G30 codebook, with zero-or-blank phase LLI;
3. typed scale-factor, phase-shift and receiver-clock transform receipts;
4. model-blind geometry-free and phase-minus-code witnesses;
5. release of the frozen bundle to three symmetric family evaluations;
6. prefix-only constant/rate calibration and one untouched held-out result;
7. buffer erasure and zero observation-value persistence.

Scale-factor and phase-shift absence are represented as specification-defined
states. Malformed, conflicting or incomplete records are description failures,
not physical rejections. Declared phase shifts are validated but never applied
again because the stored RINEX phase already includes them. Receiver-clock
event-time and measurement corrections are applied exactly once when the
header declares that the receiver did not apply them.

The controlling score is the maximum held-out peak-to-peak residual over the
six labelled tracks. `B = 3971.647488808212 m`. The orbit must both remain at
or below `B` and beat both frozen null families by strictly more than `B` to
authorize `ORBITAL_MODEL_PREDICTIVELY_PREFERRED`. A failed orbital prefix
detectability check produces `NOT_DETECTABLE`, never a null or physical claim.

Synthetic controls cover nominal orbital preference, prefix-affine preference,
time-reversed decision semantics, non-detectability, transform absence and
explicit records, transform conflicts, missing required topology, same-path
witness failure, descriptive marker identity, extra tracks and strict JSON.
The full offline suite passed with `1697 passed` before this seal was written.

No DOY238 observation artifact was queried, selected or opened. No observation
value or orbital score was produced.
