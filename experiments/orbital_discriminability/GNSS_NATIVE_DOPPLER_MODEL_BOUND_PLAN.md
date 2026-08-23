# GNSS broadcast-model bound method

This is a navigation-only hardening step inside the existing GNSS forward
vertical. It creates no gate, freezes no observation plan, and authorizes no
observation access.

## Physical question

Do the exact healthy G15/G22 LNAV records selected on each already-frozen
DOY 219--221 grid provide an outcome-independent signal-in-space range-error
interval below the per-link limit computed by the frozen native-Doppler
transfer audit?

## Frozen inputs

- orbitality receipt SHA-256
  `036413c60dc10f7a0ca41810904b3b081def91288b7b6247522938e005e3d225`;
- transfer receipt SHA-256
  `16e15a2e91712429ebb27f374558d2ab04e1a28b5e376a6317c753ed47055ebb`;
- only the three BRDM navigation products already named and hashed in the
  orbitality receipt for DOY 219, 220 and 221;
- exactly 380 epochs at 30 s from each frozen `start_model_epoch_utc`;
- satellites G15 and G22 only.

The compiler must validate both compressed and decompressed byte counts and
SHA-256 values before parsing. Decompression is in RAM. RINEX observation
product names, URLs, headers and bytes are outside the input surface.

## Admission method

At every frozen epoch, select the most recent broadcast record without first
discarding unhealthy records. Admission requires:

- a record at or before the epoch;
- `sv_health == 0`;
- finite positive RINEX nominal `SV accuracy` matching one specified LNAV URA
  category other than index 15;
- nonnegative age no greater than 14,400 s;
- a known positive fit interval and age no greater than that interval.

RINEX 3.05 stores the nominal metre value derived from the LNAV URA index.
For each selected record, recover that discrete index, take the published upper
edge of its URA category, and multiply it by the legacy integrity scale 4.42.
The largest resulting value across both satellites and all 380 epochs is the
per-link model interval used by the already-frozen transfer equation.

This quantity is classified `MODELED_INTERVAL_WITH_LEGACY_INTEGRITY_ASSURANCE`.
It is not described as a deterministic mathematical worst case, a calibrated
probability for this experiment, or a pure orbit-only error: URA also contains
other signal-in-space contributions. Those overlaps are retained
conservatively rather than subtracted.

Primary admission requires the modeled per-link interval to be no greater than
the exact candidate-specific maximum in the frozen transfer receipt and a
strictly positive final physical margin. No value may be learned from an
observation or replaced by zero.

## Outcomes

- `NATIVE_DOPPLER_BROADCAST_MODEL_BOUND_ADMITTED`
- `NATIVE_DOPPLER_BROADCAST_MODEL_BOUND_EXCEEDS_MARGIN`
- `NATIVE_DOPPLER_NAVIGATION_METADATA_INVALID`

Regardless of outcome, primary and reserve observation authority remain false.
