# KIRU–MAT1 G20/G22 primary outcome

## Terminal result

MEASUREMENT_INVALID

Reason: GEOMETRY_FREE_PHASE_DISCONTINUITY.

This is the single authorized outcome for the frozen DOY 215 KIRU00SWE and
MAT100ITA products. Decompression began, so zero retry is now binding. No
alternate artifact, station, satellite, field, window, threshold or nuisance
may be substituted into this experiment.

The outcome JSON Lines artifact is 931 bytes with SHA-256
5e4e54c1cae1f431eacc8101bb995de18c548e4ea7dcb46a71313517e90ea02b.

## What passed before refusal

- the authority receipt matched the frozen prospective plan, source commit,
  source hash and evaluator seal;
- both complete compressed artifacts matched their predeclared filenames and
  byte counts;
- KIRU SHA-256 was
  e65de2fe6db79a9908a87ee7892f75558601c9bd28edd98fd61e22a21b4812f2;
- MAT1 SHA-256 was
  48a973ae7ad1f365553c590337fc5ea838bc06a9db6d567417109f2dde0ad65f;
- the exact broadcast navigation file matched its frozen byte count and
  SHA-256;
- both primary products decompressed and their headers, exact 380-epoch grid,
  G20/G22 links, six required fields and finite scalars parsed successfully.

The evaluator validates KIRU first. Its array shape and zero-LLI clauses
passed, then at least one absolute second difference of
lambda1 times L1C minus lambda2 times L2W exceeded the frozen
0.09514683639918244 m bound. The list evaluation stopped there. MAT1 had
parsed successfully, but its station-level LLI and geometry-free clauses were
not evaluated.

## What was not evaluated

The observed double-difference feature was not constructed. The nominal
prefix detectability test was not run. No calibration nuisance was fitted and
none of H_G20, H_AFFINE or H_G14 reached held-out scoring.

Therefore this outcome says nothing about:

- whether the G20 orbital prediction fits the observation;
- whether the affine or G14 alternative is better;
- satellite identity or orbit reconstruction;
- the physical cause of the phase discontinuity.

The receipt does not preserve the offending epoch, satellite, magnitude or
stream. A true cycle slip, unreported tracking discontinuity, unsupported
phase behavior or an overly brittle admission invariant remain possible.
None is selected as the cause.

## Custody and stop

No decompressed RINEX, observation array, feature or hypothesis array was
persisted. After the terminal receipt was hashed, the temporary quarantine
containing both compressed primaries and the navigation files was deleted.
It is not recoverable from the workspace.

This exact KIRU–MAT1 primary is closed. Any future use of arc segmentation,
different slip semantics, Doppler observables or another station set would be
a new prospective physical experiment, not a retry or repair of this outcome.
