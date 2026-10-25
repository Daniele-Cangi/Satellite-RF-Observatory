# Numerical covariance repair, exposed comparison v2

The first execution and the covariance-only diagnosis remain unchanged. This
follow-up repairs a numerical condition-number ceiling, not the predictive
hypothesis. It uses the same exposed input, five folds, masks, endpoint weights,
wet field, fixed 300 s correlation, prefix variance fit, outer numerical-use
boundary, original 1,248/874 pairs and all original acceptance criteria.
No held metric selects the solver or its numerical tolerances.

## Numerical method fixed before the new execution

Equilibrate the covariance by its diagonal standard deviations, with unit scale
for zero diagonal entries. This is a change of coordinates, not a diagonal
covariance approximation or added variance. Diagonalize the equilibrated PSD
matrix. Resolve eigenvalues above `8 * eps64 * dimension * max(abs(eigenvalues))`:
a conservative dimension-dependent floating-point backward-error scale,
rather than the original fixed `1e-10` spectral ratio. Negative eigenvalues
beyond that numerical resolution, an empty image, or incompatible errors fail.
The original error-image compatibility tolerance remains unchanged.

Certify the result in the original covariance coordinates. Require the infinity
norm of `W.T C W - I` below `1e-4` and the normwise relative backward error of
`C x = e` below `64 * eps64 * dimension`. The former is an explicit numerical
accuracy budget, not physical uncertainty qualification. Retain every check,
resolved rank and eigenvalue resolution in the prediction artifact. Also check
the process-conditioned solve's relative backward error in whitened coordinates
against the same machine-dependent limit. Failed certification remains an
unsupported model, without ridge, baseline substitution or threshold retry.

Tests include weak positive modes beyond the old ceiling, rotation and changes
of units, genuinely singular compatible/incompatible errors, deliberately
inaccurate spectral output, shared-noise Gaussian conditioning, outer-value
poisoning and preservation/replay of the original failures.

## Execution and reporting

Use the existing command with a fresh output directory:

```console
python -m research.exploratory.masked_prediction_study --mask-consistent --comparison research/exploratory/missnet-transfer-2026-10-19/original-comparison.json --output data/mask-consistent-solver-v2-2026-10-25
```

Commit the producer before execution. Freeze all five predictions before held
scoring/comparator access through the existing writer. Retain the new outputs
separately under `solver-repair-v2/`, including every failure and worsening case.
Do not overwrite the first execution or alter its outcome. This is a numerical
repair and a separately versioned exposed development result, not prospective
confirmation, physical covariance qualification or independent orbit recovery.
