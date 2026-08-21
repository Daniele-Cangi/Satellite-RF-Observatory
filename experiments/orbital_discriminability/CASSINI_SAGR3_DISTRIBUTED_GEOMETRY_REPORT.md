# Cassini SAGR3 distributed-geometry screen

## Physical question

Does observer-coupled Cassini downlink geometry leave a nonlinear X-band
signature between DSS-25 and DSS-65 after the same calibration-prefix affine
nuisance is applied to the held-out suffix?

No RSR header, payload, IQ, amplitude, or detector input was used.

## Change of abstraction

The prior DSS-14 single-station path was blocked because seven absolute-link
terms lacked a finite independent envelope. A raw X/Ka or S/X difference is
not by itself the solution: it cancels the common fractional component,
including the desired orbital Doppler.

The SAGR3 archive contains a stronger simultaneous topology:

| Role | PDS product | Receive root | Band | UTC coverage |
|---|---|---|---|---|
| distributed measurement left | `s23sags2006_251_1200x14x25rd` | DSS-25 | X | 12:00:01–22:30:00 |
| same-path dispersive witness | `s23sags2006_251_1200x14k25rd` | DSS-25 | Ka | 12:00:01–22:30:00 |
| distributed measurement right | `s23sags2006_251_1200x14x65rd` | DSS-65 | X | 12:00:01–16:40:00 |

All three share the DSS-14 X-band uplink and Cassini transponder. DSS-25 and
DSS-65 are independent receive roots. The X/Ka pair at DSS-25 is explicitly
not counted as a third observer.

## Frozen coordinate

The geometric observable is

```text
8.425e9 × (kinematic_factor_DSS25 − kinematic_factor_DSS65)
```

evaluated on a common Cassini transmit-time grid. Future measured receive
tracks would have to be resampled onto this single frozen coordinate, with the
same resampling applied to every null.

- common-transmit interval: `2006-09-08T10:36:28.092247Z` through
  `2006-09-08T15:16:27.092250Z`;
- 16,800 one-second records, capped by the actual shorter product;
- 3,360 calibration-prefix records;
- 13,440 held-out records;
- no suffix refit;
- required right-minus-left receive-time offset: −15.2186 ms to +15.6679 ms,
  with 30.8865 ms evolution across the interval.

## Exact-hash SPICE result

Joint visibility holds on the complete grid:

- DSS-25 elevation: 8.2810° to 63.2252°;
- DSS-65 elevation: 8.9542° to 59.3547°.

The raw distributed X-band trajectory spans `3278.6530131889685 Hz`.

Held-out null separations after prefix-only affine calibration:

| Frozen null | Peak-to-peak separation | RMS |
|---|---:|---:|
| affine continuation | 9526.2274293 Hz | 4544.6242318 Hz |
| Saturn-barycenter geometry destruction | **0.3098298838 Hz** | 0.0764300167 Hz |

Station swap was removed because it is only a sign change under differential
scoring. The Saturn-center alternative is therefore the controlling null, not
the visually larger affine separation.

The direct 100 ns per-stream timing envelope is `7.482903185973555e-06 Hz`
two-sided. If every still-unqualified measurement-path term were zero, the
optimistic three-bin ceiling would be `0.10327413363661438 Hz`. This is not an
instrument admission requirement.

## Multi-frequency witness semantics

The proposed same-path model is

```text
z_band(t) = g_common(t) + plasma(t)/f_band² + band_hardware(t)
```

X and Ka at DSS-25 can algebraically separate a common non-dispersive
coordinate from a dispersive coordinate only after the two band-specific
receiver paths are qualified. This can turn plasma into a measured witness,
but it does not independently establish Cassini geometry and it does not
calibrate the DSS-65 Earth-near path automatically.

## Outcome and blocker

```text
CASSINI_DISTRIBUTED_GEOMETRY_SCREEN_POSITIVE
```

This is a geometry screen, not physical admission. It authorizes no detector
and no IQ access.

The exact remaining blocker is a predeclared, amplitude-blind header-only
qualification of these three products for:

- RSN and first-sample-time continuity;
- actual sample mode and resolution;
- NCO/override and reversible recorded-baseband coordinates;
- independent RSR hardware for the DSS-25 and DSS-65 X streams;
- distinct, simultaneous DSS-25 X and Ka receiver paths.

Only if those clauses pass should the differential physical-envelope audit be
run. The 0.30983 Hz result must not be converted into a detector requirement
before that step.

## Sources

- [Cassini RSS archive and product logs](https://atmos.nmsu.edu/data_and_services/atmospheres_data/Cassini/inst-rss_curr.html)
- [Cassini Radio Science User's Guide](https://pds.nasa.gov/data/pds4/misc/document_cassini/Cassini_Radio_Science_Users_Guide_30Sep2018.pdf)
- [DSS-25 X label](https://atmos.nmsu.edu/PDS/data/PDS4/cassini-rss-raw-sagr/data-rsr01/2006/s23sags2006_251_1200x14x25rd.xml)
- [DSS-25 Ka label](https://atmos.nmsu.edu/PDS/data/PDS4/cassini-rss-raw-sagr/data-rsr01/2006/s23sags2006_251_1200x14k25rd.xml)
- [DSS-65 X label](https://atmos.nmsu.edu/PDS/data/PDS4/cassini-rss-raw-sagr/data-rsr01/2006/s23sags2006_251_1200x14x65rd.xml)

The labels and exact-hash kernels used for this computation were temporary
metadata. They were destroyed after verification. No RF was persisted.
