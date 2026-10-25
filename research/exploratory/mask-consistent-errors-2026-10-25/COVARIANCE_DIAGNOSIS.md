# Diagnose the original covariance-image refusals

Follow up the four retained failures without changing their numerical rule or
producing a new predictive comparison. Reconstruct all five original folds,
including the G19 control, using the same input, masks, endpoint covariance,
source response, prefix cut and inner calibration fits. The original prediction
producer/result at `12a427a` remains immutable. This is exposed-data diagnosis.

For both prefix-only and all-admitted errors, record the original spectral cut,
retained rank, discarded positive eigenvalues, error projections, acceptance
tolerance and the first rejection stage. Independently replay each error from
the raw-factor operator F and admitted whitened inputs: e=F*y_white, C=F*F.T.
The Rayleigh variance of the rejected error direction is evaluated from F
directly and from C, distinguishing nonzero discarded response from loss of
precision or an inconsistent error operator. Spectra and component values are
retained; no held RMS or alternate rank/timescale is used to select a result.

The existing report command gains a diagnostic mode:

```console
python -m research.exploratory.masked_prediction_study --diagnose-mask --output data/mask-covariance-diagnosis-2026-10-25
```

The output directory must be new. This mode does not fit the corrective process
variance, condition new corrections, access the comparison file or run the held
scorer. It saves diagnostic data through the existing report writer and source/
input identities. There is no covariance rescaling, changed guard or new
authority/replay executor. Original outcomes and model criteria stay unchanged.
