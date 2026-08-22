# Cassini dual-root X/Ka pass selection

## Physical question

Does the bounded official Cassini SROC corpus contain a media-clear session
with two independent DSN receive roots and simultaneous X/Ka products whose
central, pre-pass orbital geometry remains distinguishable from frozen nulls?

This is a metadata-only selection result. No RSR header, sample, amplitude,
waterfall, detector, or IQ input was accessed.

## Bounded source scope

The search was limited before label inspection to the three official PDS4
SROC RSR collection inventories:

- `rsr01`: 122,992 bytes,
  SHA-256 `73d0a017c1db060a787ad96803f46cb85949806b371cf74ac95acc6ec14fd7d2`;
- `rsr02`: 1,230 bytes,
  SHA-256 `7f2e7d09e2e839b4c009172ccfff4c7c22b4368c96e69af7797ed9722ebd3e68`;
- `rsr16`: 73,636 bytes,
  SHA-256 `d5b84215078e9e784362ba64c2f1787985116d635d05c4276543ec5514db356a`.

The official SROC occultation-planning table was frozen at 25,835 bytes,
SHA-256 `e0b22b90160f5c8d778d09fd397c246090fcad85bec9a7c7fdcac7a68c5f4eff`.

Filtering 1,499 inventory rows found 16 exact-start, cross-complex, dual-band
sessions. Five were predeclared before their 20 labels were inspected; no
post-label substitution was allowed.

| Session | Receive roots | Label overlap | Media state | Geometry |
|---|---|---:|---|---|
| 2005-159 17:15 | DSS-25 / DSS-55 | 12,598 s | documented post-occultation window | evaluated |
| 2008-139 00:00 | DSS-25 / DSS-55 | 3,992 s | unknown in bounded planning snapshot | not evaluated |
| 2008-168 06:00 | DSS-25 / DSS-34 | 3,299 s | unknown in bounded planning snapshot | not evaluated |
| 2016-182 06:30 | DSS-25 / DSS-35 | 7,200 s | full overlap in Saturn/ring occultation | not evaluated |
| 2017-110 12:30 | DSS-26 / DSS-35 | 12,600 s | occultation followed by deadband | not evaluated |

Every row has exactly X and Ka labels at each of two DSN complexes. That is
label-level topology, not proof of stream continuity or measurement validity.

## Selected media-clear sub-window

The 2005 planning table places the ring-occultation activity at 16:30–18:33
UTC and a following X-to-Earth deadtime at 18:33–19:17 UTC. The frozen receive
window is therefore only:

`2005-06-08T19:17:00Z` through `2005-06-08T20:44:59Z`.

The trajectory is the pre-pass PREDICT SPK
`050426AP_SCPSE_05116_05216.bsp`, created 2005-04-26 and covering the
session. It is not a reconstructed, target-RF-conditioned orbit.

## Central geometry screen

The screen uses a five-second common Cassini transmit-time grid. This is a
selection approximation, not the future SFDU grid. The first 20% is the only
calibration prefix; suffix refitting is prohibited.

- common transmit-time interval:
  `2005-06-08T17:54:57.178445Z` to
  `2005-06-08T19:22:52.178447Z`;
- 1,056 records: 212 calibration and 844 held out;
- DSS-25 elevation: 46.1467° to 63.5448°;
- DSS-55 elevation: 15.8414° to 32.4533°;
- DSS-55 minus DSS-25 receive-time offset: 3.925 ms to 13.229 ms;
- raw X-band differential span: 2,179.4057577 Hz.

Both stations are jointly visible over the complete frozen window.

| Frozen null | Held-out peak-to-peak | Held-out RMS |
|---|---:|---:|
| prefix affine continuation | 893.0071309 Hz | 429.7432537 Hz |
| Saturn-barycenter geometry destruction | **0.2991723488 Hz** | 0.1454710113 Hz |

Station swap was removed as a sign-redundant null under differential scoring.
The Saturn-center alternative is controlling. A direct trajectory envelope at
`t ± 1 µs` gives 0.0000187073 Hz for two streams, but this is only a planning
bound; exact ADC-to-UTC semantics remain a header blocker.

## Expanded causal-state audit

The requested “quantum-like” approximation is represented without invented
probabilities. Several physically admissible states remain live at once. A
claim is allowed only if the orbital/null separation survives their correlated
interval envelope.

The frozen states are `OBSERVABLE`, `MODELED`, `BOUNDED`, and
`UNRESOLVED`. An unresolved term is never zero. Bounds are combined as
correlated unless independence is documented; root-sum-square aggregation and
post-outcome bound selection are prohibited.

Important conditions now made explicit include:

- first-order plasma at both roots: observable in principle from simultaneous
  X/Ka, but exact carrier coordinates and band alignment are unknown;
- higher-order plasma and scintillation-like residual structure: unresolved;
- differential troposphere: unresolved;
- receiver proper-time/gravity differential: central model is not its
  uncertainty; uncertainty remains unresolved;
- relativistic propagation remainder and solar-system constants: model and
  uncertainty must be separated;
- Cassini USO retarded-time coupling: the two roots sample different receive
  epochs and therefore potentially different transmit states;
- station phase-center/cable delay and X/Ka differential hardware: unresolved;
- EOP/station coordinates: outcome-independent modeled controls whose
  uncertainties still need propagation;
- PREDICT-SPK orbit error: independent of target RF, but no frozen covariance
  has yet been admitted;
- NCO/DDC transitions, sample rate, filtering, decimation, polarization,
  frequency-reference changes, RSN gaps and X/Ka time alignment: unknown until
  an amplitude-blind header audit;
- finite-integration spectral smearing, leakage, ambiguity, clipping and SNR:
  unknown until a later model-blind detector freeze;
- open-term correlation: no independence is presumed.

## Outcome

`ONE_MEDIA_CLEAR_DUAL_ROOT_CANDIDATE_GEOMETRY_SCREEN_POSITIVE`

This authorizes only the statement that one bounded, metadata-qualified
candidate has positive central geometry against the two frozen null families.
It does **not** authorize measurement validity, a plasma-corrected observable,
physical-envelope closure, orbital-model preference, identity evidence,
detector development, or IQ access.

The selection manifest SHA-256 is
`9f0f409e2067820578ad8c586213ee8fee1288465c99065f2453c1742053ce69`.

## Exact next blocker

The smallest next physical step is an amplitude-blind, header-only
qualification of the four frozen DSS-25/DSS-55 X/Ka products on the 2005
post-media window. It must establish:

1. sample-zero UTC binding and continuity for all four streams;
2. actual carrier, LO, NCO and frequency/phase-polynomial coordinates;
3. absence of DDC/reference transitions in calibration and holdout;
4. sample mode, resolution, filter and decimation;
5. common-grid X/Ka alignment and polarization/channel lineage;
6. a predeclared first-order plasma composite at each root;
7. an outcome-independent correlated envelope for every non-dispersive and
   higher-order open term.

The candidate must close without IQ access if any of these conditions fails,
or if the admitted physical envelope can absorb 0.2991723488 Hz. The forward
experiment is not frozen.
