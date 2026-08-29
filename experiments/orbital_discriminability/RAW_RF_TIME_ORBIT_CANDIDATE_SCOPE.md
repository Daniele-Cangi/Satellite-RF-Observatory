# Bounded raw-RF time/orbit candidate scope

## Purpose

This is a predeclared metadata-only SHOCK boundary, not a new gate or an
observation authority.

```text
Physical question:
Can one public raw-RF recording support a prospective held-out comparison in
which a known orbital trajectory predicts recorded frequency dynamics better
than frozen affine and alternative-orbit nulls, without relying on a
PRN-labelled GNSS measurement pipeline?

New information produced:
Whether any bounded public measurement path simultaneously exposes raw
pre-Doppler samples, finite ADC-to-UTC and frequency bounds, and an
outcome-independent pre-pass orbit authority.

Why existing experiments cannot answer it:
PIE and AMC are PRN-labelled GNSS observables. RSP-03 lacks absolute-time
provenance; MAVEN lacks an independent pre-pass orbit solution; and the
Cassini candidates are already closed by their physical-envelope audits.

Minimum experiment:
Audit exactly five predeclared public product families using metadata only.
Admit at most one development/primary/reserve structure and stop before all
sample access.

Stop condition:
Stop with NO_TIME_AND_ORBIT_QUALIFIED_RAW_RF_VERTICAL if none can bind raw
pre-Doppler samples to finite time/frequency uncertainty and an orbit solution
that was independent of the target RF outcome.
```

## Frozen candidate families

The following order was fixed before opening any product-specific SigMF
metadata, RSR header, sample payload, spectrum or signal-derived diagnostic:

1. `BREAKTHROUGH_LISTEN_VOYAGER1_GBT_SIGMF`
   - public Breakthrough Listen Voyager 1 raw-voltage/SigMF release;
   - Green Bank Telescope measurement root.
2. `CAMRAS_DSLWPB_DWINGELOO_RELEASE_V1`
   - public DSLWP-B release;
   - CAMRAS Dwingeloo Telescope measurement root.
3. `CAMRAS_SLIM_LEV1_LANDING_SIGMF`
   - public SLIM/LEV-1 landing raw-IQ family;
   - CAMRAS Dwingeloo Telescope measurement root.
4. `CAMRAS_ARTEMIS1_TRACKING_SIGMF`
   - public Artemis I tracking raw-IQ family;
   - CAMRAS Dwingeloo Telescope measurement root.
5. `ROSETTA_RSI_OPEN_LOOP_PDS`
   - public Rosetta RSI open-loop DSN/IFMS family;
   - PDS/PSA radio-science receiver roots.

No sixth family may replace a refusal in this audit. Multiple CAMRAS products
are distinct physical phenomena/product families but share one hardware root;
they must not be counted as independent observers.

## Excluded concluded paths

- `RSP03`: blocked by absolute-time provenance;
- `MAVEN_DSN_RSR`: reconstructed orbit prevents the intended independent
  orbital claim;
- `CASSINI_DSN_RSR`: single- and distributed-observable paths are closed by
  their frozen physical-envelope and composite-observable results;
- the concluded GNSS cross-family station set: no further station search is
  permitted.

These exclusions may be cited as prior evidence but not re-audited or used as
fallback candidates.

## Admission clauses

Each candidate is assessed independently for:

1. immutable product identity, checksum and usable license;
2. complex raw samples before Doppler correction or ridge extraction;
3. sample rate, center-frequency and receiver-transform semantics;
4. first-sample UTC bound physically tied to ADC sample zero;
5. declared frequency-reference accuracy and sample-rate discipline;
6. station coordinates and measurement-root identity;
7. historical orbit authority available before the recording;
8. proof that the selected orbit solution did not assimilate target-pass RF;
9. a predicted held-out non-affine signature larger than the conservative
   timing, frequency, transform and nuisance envelope;
10. distinct development and sealed primary/reserve artifacts or a defensible
    reason why the family cannot supply them.

Missing clauses remain `UNKNOWN`; they are never converted to zero. Metadata
may be read, hashed and cited. Sample payloads, spectra, previews, waterfalls,
signal levels and decoded content remain forbidden.

## Outcome boundary

The audit may end only as:

```text
RAW_RF_VERTICAL_METADATA_ADMITTED
NO_TIME_AND_ORBIT_QUALIFIED_RAW_RF_VERTICAL
```

An admitted outcome still grants no download, detector development or sample
access. It only identifies the smallest candidate for a separately reviewed
prospective plan.
