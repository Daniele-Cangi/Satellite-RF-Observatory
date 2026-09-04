# Satellite RF Observatory

An experimental laboratory for testing whether a predicted satellite orbit
leaves an observer-dependent RF structure that survives measurement nuisance
and predicts an independent time interval better than non-orbital alternatives.

The project now follows one satellite-first causal order:

```text
candidate orbit + observer geometry + event time
  -> distributed fractional-Doppler prediction
  -> pass-specific detectability requirement
  -> qualified Internet measurement capability
  -> prospective held-out observation
  -> comparison with frozen non-orbital nulls
```

The orbit determines what an instrument must preserve before an endpoint,
frequency or acquisition window is selected. A connected receiver, a visible
spectral feature or a good fit on calibration data is not by itself evidence
of orbital origin.

This is research software. It is not an operational monitoring platform, a
signal-identification service or evidence that any transmitter has been
identified.

## Current direction

The primary scientific surface is
[`experiments/orbital_discriminability`](experiments/orbital_discriminability/G0_SCOPE.md).
Gate G0 asks offline whether multi-observer orbital geometry is discriminative
at all, before searching for a receiver. Its synthetic map and limits are in
[`G0_IDENTIFIABILITY_REPORT.md`](experiments/orbital_discriminability/G0_IDENTIFIABILITY_REPORT.md).

[`experiments/live_instrument`](experiments/live_instrument/README.md) is a
frozen measurement-integrity layer inherited from Gates B–F2.5. It established
useful controls but no longer chooses the scientific question. Its SatNOGS and
Kiwi branches remain separate historical experiments.

The primitives that survived those branches remain available to the orbital
experiment:

- evaluation by contract clause, not one global health label;
- atomic receipts;
- event time and TTL;
- transform ledger;
- causal lineage;
- separation of physical decisions from descriptive/software errors;
- artifact hashing with zero RF persistence.

They are not promoted to a general framework. Gate G1 must justify each one
against the pass-specific orbital prediction.

## Latest checkpoint

Gate G1 is complete offline. It takes one immutable orbital pass and evaluates
caller-supplied receiver descriptions in two stages: individual observability
qualification, then independent-pair differential detectability. It contains
no discovery or network client and cannot acquire RF.

The reference vertical selects a synthetic Berlin–Eindhoven pair with a
`2807.799 Hz` conservative margin. A fully available local pair is correctly
refused at `-243.201 Hz`; availability therefore cannot masquerade as
falsification power. See
[`G1_ADMISSION_REPORT.md`](experiments/orbital_discriminability/G1_ADMISSION_REPORT.md).

Gate G0 remains the underlying physical result. It samples the existing
stateless orbital kernel for multiple observers, separates fractional geometry
from carrier scaling, fits only station offset and affine drift on a
calibration prefix, and scores the untouched suffix only on jointly visible
station differences. Four non-redundant frozen null families use the same
split, and clock uncertainty is propagated through direct `t ± delta_t`
trajectories rather than a local slope approximation.

The 128-case synthetic sweep contains both detectable and undetectable regions:
81 cases are `ORBITAL_MODEL_PREDICTIVELY_PREFERRED` and 47 are
`ORBITAL_SIGNATURE_BELOW_DETECTABILITY`. This is a mechanism result, not a
claim about a live signal or a satellite identity. G1 turns that envelope into
an admission procedure; later GNSS experiments have now advanced beyond this
offline baseline, as summarized below.

The G1.1–G1.3 inventory/search work is a concluded side investigation, not the
critical path. No global receiver catalog is required.

## Current physical outcome

The project has reached real held-out orbital evidence. The frozen
GOLD00USA/NLIB00USA G22/G30 DOY 220 primary was measurement-valid and
preferred the orbital prediction: its held-out residual was `2.313 m`
peak-to-peak, against `8,858.964 m` for the closest frozen alternative. A
distinct DOY 219 pass repeated the result with `2.269 m` orbital residual
against `8,988.225 m` for the closest null.

The authorized claim is therefore
`REPEATED_PASS_CONSISTENCY_FOR_TWO_GOLD_NLIB_G22_G30_PASSES`. It is not
catalog-wide identity, unconstrained orbit reconstruction or confirmation on
observer roots independent of GOLD/NLIB. Later PIE and AMC held-out results
transferred the same orbit-signal family across independent observers and
passes, but retained the common POLARX5 receiver family as an explicit
upstream limitation. The bounded attempt to cut that implementation family is
now closed below; another traditional GNSS station search is not the current
direction.

Several other bounded routes remain useful closed exclusions rather than
orbital scores:

- Berlin–Utrecht OpenWebRX was closed `MEASUREMENT_PATH_INSUFFICIENT` because
  Berlin did not deliver the target profile and Utrecht exposed neither
  server-side frame time nor sample sequence;
- RSP-03 was closed by absolute sample-time provenance;
- MAVEN DSS-45 produced a model-blind development carrier tracker, but only a
  reconstructed date-covering spacecraft SPK is available;
- Cassini produced positive distributed geometry, independent DSN receive
  roots and an X/Ka control at DSS-25, but the tested paths were closed by
  unresolved physical/hardware envelopes or a missing symmetric Ka root;
- the GOLD00USA–NLIB00USA G11/G21 GNSS plan retained a `1420.626 Hz`
  premeasurement physical margin, but its one authorized run stopped
  `MEASUREMENT_INVALID` at `TRUNCATED_REQUIRED_OBSERVATION_RECORD` before any
  calibration or held-out score. A later value-blind forensic repair explained
  the boundary as NLIB G21 `C2W` at `10:06:00 GPS`: header index 5 followed
  only three serialized fields, a RINEX `TRAILING_FIELD_OMITTED` state. The
  historical outcome and closure are unchanged.
- the distinct-root ALGO00CAN–MDO100USA G22/G30 DOY223 primary retained a
  `51,848.538 m` modeled physical margin, but its single authorized run stopped
  `MEASUREMENT_INVALID` at `HATANAKA_DECODE_FAILED:ALGO00CAN`. Both frozen byte
  streams were fully hashed before decode; no measurement clause or held-out
  hypothesis was evaluated, and zero observation values were persisted.

The ALGO/MDO outcomes close two exact primary paths, not the independent-root
physical hypothesis. Repairing their transport or decoder in place would add
no orbital information and is not the next research step. A bounded
post-DOY223 review instead recommends testing whether the already demonstrated
continuous-phase mechanism can make a frozen prediction for one held-out
observer, before selecting any new artifact. See
[`POST_DOY223_INDEPENDENT_OBSERVER_REVIEW.md`](experiments/orbital_discriminability/POST_DOY223_INDEPENDENT_OBSERVER_REVIEW.md).

That offline observer-transfer spike is now complete. A one-anchor
target-minus-reference coordinate at a synthetic unseen observer preserves
`1,703.225 m` peak-to-peak separation from the closest frozen affine null.
The full conservative pairwise envelope is `286.883 m`, leaving
`1,416.342 m`. A wrong-orbit truth stress selects the wrong-orbit family rather
than automatically preferring the target. The outcome is
`OBSERVER_TRANSFER_MECHANISM_DISCRIMINATIVE`, but it is only a synthetic
mechanism result: no observer, station, date, product or measurement is
selected or authorized. See
[`GNSS_OBSERVER_TRANSFER_SPIKE_REPORT.md`](experiments/orbital_discriminability/GNSS_OBSERVER_TRANSFER_SPIKE_REPORT.md).

The corresponding bounded real-geometry screen is also complete, still with
zero observation access. Across four unused observers and three frozen
post-A/B NAV days, all 12 station/date cases retain positive margin. The
distinct-observer shortlist is PIE100USA/DOY223, WES200USA/DOY223 and
AMC400USA/DOY221. PIE controls with `190,232.341 m` separation from the affine
null against a `2,907.821 m` pairwise envelope, leaving `187,324.520 m`.
This is `OBSERVER_TRANSFER_GEOMETRY_SHORTLISTED`, not capability admission:
the next maximum work is a PIE-only field/timing/configuration check before
any qualification or primary artifact is selected. See
[`GNSS_OBSERVER_TRANSFER_GEOMETRY_REPORT.md`](experiments/orbital_discriminability/GNSS_OBSERVER_TRANSFER_GEOMETRY_REPORT.md).

A PIE-only metadata characterization has now confirmed that exact RINEX 3
compact `01D/30S` products exist for the DOY221 qualification candidate and
the still-unopened DOY223 primary candidate. The frozen station log places
both dates under receiver serial `4100427`, firmware `5.7.0`, antenna serial
`CR520022114` and the documented H-maser/10 MHz/PPS architecture. This is
`PIE_METADATA_PATH_AVAILABLE`, not signal-field qualification: L1C/L2W, LLI,
C1C/C2W, actual epoch coverage and continuity remain unknown until a separately
authorized DOY221-only structural pass. See
[`PIE_OBSERVER_CAPABILITY_METADATA_REPORT.md`](experiments/orbital_discriminability/PIE_OBSERVER_CAPABILITY_METADATA_REPORT.md).

The separately authorized DOY221 value-blind structural qualification has now
passed. The exact 3,111,600-byte product was SHA-256 hashed before decode; all
1,668 retained structural states are `PRESENT`, G22/G30 each span the complete
139-epoch window, and C1C/C2W witnesses have 100 percent coverage. No numerical
observation value, orbital prediction or score entered the qualifier, and no
observation bytes were persisted. DOY223 remains completely unopened. The next
maximum action is review of one prospective PIE/DOY223 contract, not primary
access. See
[`PIE_OBSERVER_QUALIFICATION_REPORT.md`](experiments/orbital_discriminability/PIE_OBSERVER_QUALIFICATION_REPORT.md).

The PIE/DOY223 prospective contract is now frozen offline while the primary
remains unopened. It fixes one sample-zero anchor, a 79-epoch witness prefix,
a 60-epoch held-out suffix, zero fitted nuisance parameters, the affine and
G01/G14/G17 nulls, and explicit measurement-validity outcomes. The earlier
unwitnessed 4 m hardware term is replaced by a predeclared ionosphere-free
code-phase witness capped at 1,250 m p-p per satellite. The resulting pairwise
guard is 7,899.821 m against 190,232.341 m affine separation, leaving
182,332.520 m. This is `PIE_OBSERVER_PRIMARY_PLAN_FROZEN`, not an observation
authority. The next maximum work is an offline exact-hash prediction seal. See
[`PIE_OBSERVER_PRIMARY_PLAN.md`](experiments/orbital_discriminability/PIE_OBSERVER_PRIMARY_PLAN.md).

That exact-hash prediction seal is now complete. The frozen NOAA DOY223 NAV
reproduces the 190,232.341 m affine-controlling separation, the direct
`t +/- 15 s` envelope is 1,418.146 m, and every modeled trajectory remains
above 17.802 degrees. The unchanged pairwise guard leaves 182,332.520 m of
margin. The outcome is `PIE_OBSERVER_PRIMARY_PREDICTION_FROZEN`: zero PIE
headers, payload bytes, observation values or orbital scores were accessed.
The seal grants neither executor nor primary authority. See
[`PIE_OBSERVER_PRIMARY_PREDICTION_REPORT.md`](experiments/orbital_discriminability/PIE_OBSERVER_PRIMARY_PREDICTION_REPORT.md).

The reviewed one-shot executor is now frozen offline as
`PIE_OBSERVER_PRIMARY_EXECUTOR_FROZEN_UNOPENED`. It binds one PIE DOY223
product, the exact plan and prediction seals, full-window measurement
admission, the 1,250 m same-path witness, zero fitted nuisance parameters and
the frozen held-out comparison. The executor seal SHA-256 is
`3b15c0c8...33e2b`; all observation access counters remain zero and the seal
grants no live authority. The next maximum action is separate review of
exactly one execution, not further executor work. See
[`PIE_OBSERVER_PRIMARY_EXECUTOR_REPORT.md`](experiments/orbital_discriminability/PIE_OBSERVER_PRIMARY_EXECUTOR_REPORT.md).

That single authorized execution is now terminally complete as
`PIE_HELD_OUT_ORBITAL_MODEL_PREFERRED`. All 139 PIE epochs, phase/LLI health,
event time and same-path code witnesses passed. The G22 held-out residual was
`2.279 m` p-p, while the closest frozen affine alternative left
`190,230.062 m`; the `190,227.783 m` preference margin exceeds the frozen
`7,899.821 m` guard with zero fitted nuisance parameters. The authorized claim
is `HELD_OUT_STATION_CONFIRMED_FOR_THIS_ORBIT_SIGNAL_WINDOW`, not satellite
identity or a general receiver claim. The primary is consumed and cannot be
retried or rescored. See
[`PIE_OBSERVER_PRIMARY_OUTCOME_REPORT.md`](experiments/orbital_discriminability/PIE_OBSERVER_PRIMARY_OUTCOME_REPORT.md).

The next independent-replication route is now bounded metadata-only, without
opening another observation. AMC400USA/DOY221 changes both receiver root and
pass while retaining `159,899.492 m` of modeled margin. The official site log
establishes receiver serial `3013929`, firmware `5.6.0`, antenna serial
`1364-10065` and an external USNO H-maser chain distinct from PIE; the shared
POLARX5TR family remains an explicit common-mode limitation. Exact GSSC files
exist for a DOY222 qualification candidate and the unopened DOY221 primary
candidate. The one authorized value-blind DOY222 execution is now consumed as
`AMC_OBSERVER_QUALIFICATION_PASSED`. All 1,668 retained structural states are
present, the G22/G30 core phase/LLI window spans all 139 epochs, and every
C1C/C2W witness has 100 percent coverage. No observation scalar or product
bytes persisted and no orbital score was produced.

The AMC/DOY221 prospective contract is now frozen offline while the primary
remains unopened. It fixes the 139-epoch grid, raw-index-zero anchor, 79-epoch
witness prefix, 60-epoch held-out suffix, zero fitted nuisance parameters and
the same affine/G01/G14/G17 alternatives used by the geometry screen. The
predeclared code-phase witness replaces the old unwitnessed 4 m hardware term:
the resulting pairwise guard is `7,339.701 m` against `162,247.193 m` affine
separation, leaving `154,907.492 m`. The shared POLARX5TR family with PIE
remains an explicit limit on hardware diversity. This is
`AMC_OBSERVER_PRIMARY_PLAN_FROZEN`, not primary access or an orbital outcome.
See
[`AMC_OBSERVER_REPLICATION_METADATA_REPORT.md`](experiments/orbital_discriminability/AMC_OBSERVER_REPLICATION_METADATA_REPORT.md)
and
[`AMC_OBSERVER_QUALIFICATION_EXECUTOR_REPORT.md`](experiments/orbital_discriminability/AMC_OBSERVER_QUALIFICATION_EXECUTOR_REPORT.md).
The terminal receipt is documented in
[`AMC_OBSERVER_QUALIFICATION_OUTCOME_REPORT.md`](experiments/orbital_discriminability/AMC_OBSERVER_QUALIFICATION_OUTCOME_REPORT.md),
and the proof design is
[`AMC_OBSERVER_PRIMARY_PLAN.md`](experiments/orbital_discriminability/AMC_OBSERVER_PRIMARY_PLAN.md).

The exact-hash DOY221 prediction seal is now complete. NOAA broadcast NAV
reproduces the `162,247.193 m` affine-controlling separation, the direct
`t +/- 15 s` envelope is `1,138.625 m`, and every modeled trajectory remains
above `25.726 deg`. The unchanged pairwise guard leaves `154,907.492 m` of
physical margin. This is `AMC_OBSERVER_PRIMARY_PREDICTION_FROZEN`: zero AMC
locator requests, headers, payload bytes, observation values or orbital scores
were accessed. The prediction grants no primary authority. See
[`AMC_OBSERVER_PRIMARY_PREDICTION_REPORT.md`](experiments/orbital_discriminability/AMC_OBSERVER_PRIMARY_PREDICTION_REPORT.md).

The minimal one-shot executor is now frozen offline as
`AMC_OBSERVER_PRIMARY_EXECUTOR_FROZEN_UNOPENED`. It binds exactly one DOY221
product, the plan and prediction hashes, AMC-qualified receiver transforms,
the complete 139-epoch admission contract, zero fitted nuisance parameters and
the frozen held-out comparison. Its seal SHA-256 is
`0b6ffe5a...f44893`; all access counters remain zero and no authority marker or
outcome exists. The next maximum action is separate review of exactly one live
execution; this seal alone cannot open the primary. See
[`AMC_OBSERVER_PRIMARY_EXECUTOR_REPORT.md`](experiments/orbital_discriminability/AMC_OBSERVER_PRIMARY_EXECUTOR_REPORT.md).

The separately authorized one-shot AMC execution is now terminally complete as
`AMC_HELD_OUT_ORBITAL_MODEL_PREFERRED`. All 139 epochs and every predeclared
measurement witness passed. G22 leaves `1.409 m` p-p on the frozen held-out
suffix, versus `162,245.831 m` for the affine runner-up; the
`162,244.422 m` preference margin exceeds the unchanged `7,339.701 m` guard
with zero fitted nuisance parameters. The direct receipt claim is limited to
held-out-station confirmation for this exact window. Combined prospectively
with PIE, it supports independent-observer-and-pass replication for this orbit
signal family, while the shared POLARX5TR receiver family remains an explicit
common-mode limitation. The consumed primary cannot be retried or rescored.
See
[`AMC_OBSERVER_PRIMARY_OUTCOME_REPORT.md`](experiments/orbital_discriminability/AMC_OBSERVER_PRIMARY_OUTCOME_REPORT.md).

The bounded post-AMC change-of-information review now selects exactly one
final cross-receiver-family observer transfer as the minimum next physical
experiment. It selects no station, date or product and opens no observation
data. A non-POLARX5TR implementation must be declared from a set of at most
five roots, ranked orbit-only before target-window access, qualified on a
separate date and used for one later primary with no fallback. The maximum
future claim is replication across the receiver families explicitly tested,
not universal hardware independence. After that one outcome, traditional GNSS
replication stops; bounded blind orbit assignment or independently timed RF
must change the information type. See
[`POST_AMC_NEXT_INFORMATION_REVIEW.md`](experiments/orbital_discriminability/POST_AMC_NEXT_INFORMATION_REVIEW.md).

That single bounded cross-family screen is now terminal as
`NO_CROSS_FAMILY_GEOMETRY_SHORTLISTED`. WTZR and ZIMM had no complete joint
visibility, TSKB reached only 113 of the immutable 139 epochs, WES retained a
large positive geometry but remained refused by product-level RINEX 2 signal
semantics, and HOB2 did not cut the POLARX5 family. No observation locator or
value was opened. The result freezes `STOP_TRADITIONAL_GNSS_REPLICATION`; it
does not justify a sixth station or a weakened window. See
[`GNSS_CROSS_FAMILY_BOUNDED_SCREEN_REPORT.md`](experiments/orbital_discriminability/GNSS_CROSS_FAMILY_BOUNDED_SCREEN_REPORT.md).

A subsequent five-family raw-RF metadata audit then tested the physically
distinct route without downloading IQ. It ended
`NO_TIME_AND_ORBIT_QUALIFIED_RAW_RF_VERTICAL`: DSLWP-B and the concrete Rosetta
volume do not contain the required open-loop complex samples; SLIM declares an
internal time source; Voyager/GBT and Artemis I expose serious disciplined
receiver chains but no product-applicable finite ADC-to-UTC bound, and their
remaining orbit/artifact uncertainty is not allowed to become zero. No
held-out curve was computed after time refusal. Repeating dataset inventory is
not the next experiment; the remaining minimum information-changing route is
a separately reviewed bounded blind orbit assignment. See
[`RAW_RF_TIME_ORBIT_METADATA_AUDIT_REPORT.md`](experiments/orbital_discriminability/RAW_RF_TIME_ORBIT_METADATA_AUDIT_REPORT.md).

That bounded orbit-only screen is now complete as
`BLIND_ASSIGNMENT_GEOMETRY_SHORTLISTED`. Without discovering or opening any
new observation product, it selected AMC DOY226, 06:14:30--07:23:30 GPS and a
nearest-four family `G22 / G06 / G14 / G17 / G19`. Every candidate receives
the same prefix-only constant/rate nuisance. The affine null is controlling at
`18763.717 m` peak-to-peak against the unchanged `7339.701 m` guard, leaving a
combined `11424.015 m` model-only margin. The minimum direct-time-shifted
elevation is only `15.010433 deg`, so complete-window coverage remains a hard
future admission clause. This is geometry selection, not a primary freeze or
measurement claim. See
[`GNSS_BLIND_ORBIT_ASSIGNMENT_SCREEN_REPORT.md`](experiments/orbital_discriminability/GNSS_BLIND_ORBIT_ASSIGNMENT_SCREEN_REPORT.md).

The corresponding prospective design is now frozen as
`BLIND_ORBIT_ASSIGNMENT_PLAN_FROZEN`. It predeclares exactly one still
unqueried logical AMC DOY226 product, the same 79-epoch prefix and 60-epoch
holdout, five orbital candidates plus one affine null, and a six-identifier
mapping outside the scorer interface. All six hypotheses receive exactly one
prefix constant and one prefix rate; the mapping may be revealed only after
the opaque score receipt has been hashed. This is interface blindness rather
than adversarial repository secrecy, and the receiver's upstream PRN
correlation remains outside the claim. The compiled receipt records zero
network requests, zero primary bytes and no execution authority. See
[`GNSS_BLIND_ORBIT_ASSIGNMENT_PRIMARY_PLAN.md`](experiments/orbital_discriminability/GNSS_BLIND_ORBIT_ASSIGNMENT_PRIMARY_PLAN.md).

The exact orbit-only arrays and identity-blind scorer are now frozen as
`BLIND_ORBIT_PREDICTION_AND_SCORER_SEALED`. The 20,849-byte scorer bundle
contains six opaque 139-point arrays and no PRN, observer, product or mapping
metadata. The scorer imports no project orbital module or observation decoder,
fits the same prefix constant/rate for every identifier, and requires the
unchanged `7339.701 m` pairwise guard. Synthetic seam tests demonstrate both a
preferred opaque trajectory and an ambiguous controlling midpoint. No AMC
DOY226 locator, header, payload byte or value was accessed. See
[`GNSS_BLIND_ORBIT_ASSIGNMENT_PREDICTION_SCORER_REPORT.md`](experiments/orbital_discriminability/GNSS_BLIND_ORBIT_ASSIGNMENT_PREDICTION_SCORER_REPORT.md).

The reviewed one-shot execution is now consumed as
`BOUNDED_TRUE_ORBIT_PREFERRED`. The exact 3,456,560-byte AMC DOY226 artifact
was hashed before decode; all 139 frozen epochs and physical witnesses passed,
and no observation value persisted. Before identity reveal, the best opaque
trajectory retained a `6.104475 m` held-out peak-to-peak residual versus
`18,768.100639 m` for the runner-up, a `18,761.996164 m` preference margin
against the unchanged `7,339.701235 m` guard. The persisted score-receipt hash
preceded reveal of the best identifier as `G22_RELATIVE_TO_G30`. This supports
only bounded orbit assignment within the frozen candidate set for this one
observer/pass; it is not unconstrained orbit recovery or independent signal
identity, and no retry or rescore is authorized. See
[`GNSS_BLIND_ORBIT_ASSIGNMENT_PRIMARY_OUTCOME_REPORT.md`](experiments/orbital_discriminability/GNSS_BLIND_ORBIT_ASSIGNMENT_PRIMARY_OUTCOME_REPORT.md).

The post-outcome information review now identifies the remaining causal
boundary: G22/G30 RINEX fields were selected before the scorer became blind.
Another labelled-RINEX station would add little after the existing
observer/pass evidence and the terminal cross-family screen. The recommended
next work is therefore only an offline mechanism spike in which raw-GNSS
tracks remain anonymous to the orbit scorer while code identity is sealed as
a separate same-sample witness and revealed after the orbital receipt. This
does not authorize data search or acquisition. See
[`POST_BLIND_ORBIT_INFORMATION_REVIEW.md`](experiments/orbital_discriminability/POST_BLIND_ORBIT_INFORMATION_REVIEW.md).

That synthetic spike is now complete as
`ANONYMOUS_TRACK_SEALED_WITNESS_MECHANISM_DISCRIMINATIVE`. Eleven opaque
hypotheses include all five track-order reversals. Correct, wrong-orbit,
code/orbit-discordant, reversed-order and below-detectability controls behave
as predeclared; the scorer never receives code identity. The exact synthetic
boundary is `18,763.716565 m`, but real timing, non-affine oscillator and
propagation terms remain `OPEN_TERM`, so no raw-GNSS capability is admitted
and no observation is authorized. See
[`GNSS_ANONYMOUS_TRACK_SPIKE_REPORT.md`](experiments/orbital_discriminability/GNSS_ANONYMOUS_TRACK_SPIKE_REPORT.md).

The bounded real-capability consideration now stops
`NO_FALSIFIABLE_RAW_TRACK_EXPERIMENT`. TEX-CUP has the correct long,
dual-frequency temporal topology, but its official data root is empty in the
current session and the formerly documented products return HTTP 404. LuGRE
is a reachable immutable dual-band raw-IQ family, but its products are
separated `0.3--2.0 s` snapshots; their finite ADC-to-GPST and sample-rate
accuracy bounds are not established by the inspected metadata. No sample byte
was accessed. The resulting SHOCK is an offline constellation-snapshot
observable: test the simultaneous multi-satellite Doppler pattern under
common-clock and permutation nulls before deciding whether any LuGRE IQ can be
opened. See
[`RAW_GNSS_CAPABILITY_CONSIDERATION_REPORT.md`](experiments/orbital_discriminability/RAW_GNSS_CAPABILITY_CONSIDERATION_REPORT.md).

The observation-blind LuGRE snapshot sweep is now complete as
`LUGRE_SNAPSHOT_GEOMETRY_DISCRIMINATIVE`. Historical broadcast GPS and
independently archived Blue Ghost geometry identify OP76 as the strongest
surface candidate: its four minimum-off-boresight GPS hypotheses retain an
`11.019310 Hz` controlling separation from the same-complexity wrong-subset,
Earth-center, static-observer and rank-affine alternatives after common offset
and scale projection. The complete unfiltered GPS codebook remains a
millihertz-level stress test and is not used to pretend that all geometrically
unocculted transmitters are RF-plausible.

This is not measurement admission. Exact IQS sample-zero binding, sample-rate
accuracy, four-signal presence, estimator error, differential media and
non-affine clock terms remain open. LuGRE headers, telemetry and IQ remain
unopened (`0` bytes), and no prospective role is frozen. See
[`LUGRE_SNAPSHOT_DISCRIMINABILITY_REPORT.md`](experiments/orbital_discriminability/LUGRE_SNAPSHOT_DISCRIMINABILITY_REPORT.md).

The bounded metadata-first follow-up now stops
`LUGRE_PROSPECTIVE_PLAN_BLOCKED_BY_ADC_TIME_PROVENANCE`. Six OP73/OP74/OP76
SDRX companions prove simultaneous L1/L5 products, complex 4-bit IQ, exact
nominal sample rates (`8/24 MHz`), baseband center coordinates and no spectrum
inversion. OP76's two-second native Fourier spacing is `0.5 Hz`, plausibly
inside the frozen `5.509655 Hz` symmetric envelope, but it is not a detector
error bound. The IQS members are DEFLATE-compressed, so their embedded headers
cannot be ranged without consuming sample payload; none was opened. More
importantly, public documentation gives capture-start semantics but no finite,
product-applicable ADC-to-true-GPST error. Millisecond representation and the
generic QN400 `50 ns` figure were not promoted to accuracy. Candidate roles and
the prospective plan remain unfrozen, with zero IQ and telemetry access. See
[`LUGRE_PROSPECTIVE_METADATA_AUDIT_REPORT.md`](experiments/orbital_discriminability/LUGRE_PROSPECTIVE_METADATA_AUDIT_REPORT.md).

The permitted outcome-independent provenance search is now complete and closes
the route as `LUGRE_ROUTE_CLOSED_BY_ABSOLUTE_TIME_PROVENANCE`. NASA's public
mission documentation establishes the command/GNSS/VCTCXO time mechanism, but
publishes neither the capture-specific synchronization state nor a numerical
ADC-latch-to-true-GPST error. The preflight Allan-deviation material describes
frequency stability, the qualification manuscript publishes no end-to-end
timing result, and the generic QN400-S `50 ns` remains inapplicable to the
custom LuGRE IQS sample zero. OP73, OP76 and OP74 are closed unopened; the
`11.019310 Hz` OP76 geometry remains valid but is not promoted to an executable
experiment. See
[`LUGRE_ADC_TIME_PROVENANCE_CLOSURE_REPORT.md`](experiments/orbital_discriminability/LUGRE_ADC_TIME_PROVENANCE_CLOSURE_REPORT.md).

The subsequent change-of-abstraction review did not resume raw-IQ inventory.
Instead, one bounded offline spike tested observer-specific visibility and
Earth-occulted absence as a coarser distributed orbital coordinate. On the
fixed G0 LEO fixture, Dublin–Rome geometry yields a robust 145 s / 240 s /
155 s sequence of left-only, both-visible and right-only states. After a
provisional 5 s per-root timing allowance, the controlling state remains
135 s, 105 s above the frozen minimum dwell. A common transmitter schedule,
co-located geometry and observer permutation cannot reproduce that witnessed
ordering. A nearby plausible orbit differs by only 5 s against a 15 s
comparison bound, so the result supports the visibility mechanism but not
specific orbit identity. No receiver was selected and no RF value was opened.
See
[`DISTRIBUTED_VISIBILITY_EVENT_SPIKE_REPORT.md`](experiments/orbital_discriminability/DISTRIBUTED_VISIBILITY_EVENT_SPIKE_REPORT.md).

The orbit-first follow-up has now selected the current METEOR-M N2-4 / NORAD
59051 candidate and evaluated only three explicitly bounded public station
descriptions. Two Doncaster-envelope/YO3BN geometries retain positive margins
across three adjacent element sets and nine Doncaster position/height members:
90 s on 2026-08-30 and 80 s on 2026-08-31. The third ranked event is exactly
on the 30 s boundary and is not admitted. YO3BN publishes exact GPS
coordinates and a 2.4 MHz OpenWebRX+ profile covering 137.9 MHz, but its event
time, sequence continuity, directional mask and same-path absence witness are
unknown. AwareSignal does not publish an exact antenna coordinate, immutable
IQ path or first-sample timing, and YO8TNB was unreachable in the bounded
status check. The honest terminal is therefore
`NO_FALSIFIABLE_VISIBILITY_EXPERIMENT_AVAILABLE`: geometry is positive, but no
pair of measurement capabilities is admitted and no RF was accessed. See
[`METEOR_M2_4_VISIBILITY_SHORTLIST_REPORT.md`](experiments/orbital_discriminability/METEOR_M2_4_VISIBILITY_SHORTLIST_REPORT.md).

The bounded Alkmaar–Bucharest OpenWebRX follow-up is now closed as
`MEASUREMENT_PATH_INSUFFICIENT`. Two sessions exposed descriptive profile
handling failures, but repairing them would not add a server-bound FFT event
time, sequence number or same-path absence witness. The endpoint capability
state remains unresolved; no receiver is declared broken. A metadata-only
SatNOGS reconnaissance for the same NORAD ID, transmitter and carrier found a
distinct two-root development fixture and a later unopened primary candidate
set. No waterfall or audio product has been opened and no primary pair is yet
selected. See
[`METEOR_OPENWEBRX_PATH_CLOSURE.md`](experiments/orbital_discriminability/METEOR_OPENWEBRX_PATH_CLOSURE.md).

The bounded SatNOGS follow-up has now ranked exactly those four sealed primary
roots. EA3AGB–hyperlink is the strongest geometry-only pair: its jointly
visible held-out differential has a 4,506.364 Hz affine-residual span and a
1,017.905 Hz best-null ceiling. This is not yet an instrumental margin. The
official flowgraphs place the waterfall after model-driven Doppler
compensation, while the observation metadata does not expose the exact
applied control trace or deployed flowgraph commit. Native FFT dimensions and
row event times also remain inside unopened development artifacts. The honest
state is therefore
`SATNOGS_GEOMETRY_SHORTLISTED_MEASUREMENT_TRANSFORM_UNRESOLVED`: geometry is
positive, no primary pair is frozen and zero RF bytes were accessed. See
[`METEOR_SATNOGS_FORWARD_SELECTION_REPORT.md`](experiments/orbital_discriminability/METEOR_SATNOGS_FORWARD_SELECTION_REPORT.md).

The authorized development-only characterization has now closed that SatNOGS
route as `SATNOGS_DEVELOPMENT_METADATA_PATH_BLOCKED`. OE9BKJ preserves an HDF5
native grid at 156.25 Hz spacing and a client-clock row sequence, but exposes
no bounded ADC-to-UTC accuracy or applied Doppler-control trace. SA1CKW
publishes only a PNG with native header configuration: it does not preserve
the native row timestamp sequence or a reversible pixel-to-bin mapping. A
model-blind detector was therefore not built, the four primary artifacts
remain sealed and all three development products were destroyed after
hash-first structural parsing. See
[`METEOR_SATNOGS_DEVELOPMENT_METADATA_REPORT.md`](experiments/orbital_discriminability/METEOR_SATNOGS_DEVELOPMENT_METADATA_REPORT.md).

One independent GOLD/NLIB qualification product on DOY 214 was then scanned
structurally without persisting observation values. It failed because NLIB-G21
was absent for the first 27 frozen epochs and reacquired with nonzero LLI; the
longest joint segment contained 358 epochs. A subsequent broadcast-only screen
of DOY 216--220 found no 386-epoch G11/G21 window with the frozen 15-degree
guard and a 30-minute pre-acquisition guard. No new observation artifact or
primary was selected. The unchanged GOLD/NLIB-G11/G21 386-epoch route is now
closed rather than shortened after failure.

Any next GNSS proposal must return to orbit-first comparison and justify a
different geometry or duration from physical discriminability before another
qualification artifact is opened. The smallest demonstrated field family
remains `L1C + L2W` phase with their LLI and epoch continuity, plus same-path
`C1C + C2W`; `S1C/S2W` remain optional diagnostics.

That orbit-first comparison is now complete for the unchanged GOLD/NLIB
stations, 386-epoch duration and DOY 216--220 set. Twenty pair/date cases
survived the 30-minute, four-link 15-degree guard and a meaningful wrong-orbit
null. Exactly one geometry is retained: G14/G17 on DOY 220, 05:07:00--08:19:30
GPS. Its controlling held-out separation is `403.375 Hz` against G22 and its
complete guarded minimum elevation is `23.620 degrees`. No observation product
was discovered or opened.

The candidate-specific envelope is now complete and closes this geometry
before plan freeze. The one-model bound is `366.877 Hz`; the frozen pairwise
comparison bound is `733.754 Hz`, leaving `-330.379 Hz` against G22. Even a
zero broadcast-orbit contribution alone would not make the margin positive.
This is `GNSS_ORBIT_PAIR_PHYSICAL_ENVELOPE_DOMINATES`, not a negative orbital
measurement. No qualification or observation access is authorized.

A bounded structure audit then checked the strongest plausible objection. The
official GPS `0.006 m/s` URRE statistic and `0.02 m/s` 6-sigma design value
would reduce the pairwise total to 416.782 Hz and 433.806 Hz respectively, but
both remain above G22. The two in-window ephemeris cutovers contribute only
millihertz and do not control the separation. The result is
`GNSS_ORBIT_CLOCK_STRUCTURE_INSUFFICIENT`: further orbit-only refinement is not
the next path.

A bounded SHOCK review has now compared five causally distinct routes. Merely
adding a third GNSS station does not shrink station-local worst-case intervals,
and another raw-separation screen risks repeating the same abstraction
failure. The recommended next mechanism is instead a continuous,
multi-frequency carrier-phase double difference with predeclared LLI,
geometry-free phase and same-path code witnesses. It preserves integrated
orbital structure while avoiding premature finite-difference amplification.

This is not a new candidate or authorization. G14/G17 remains closed and may
serve only as a historical development fixture. The next bounded work is an
offline mechanism spike; only after it survives may a new orbit/station/signal
set be declared and ranked by complete remaining physical margin. See
[`POST_G14_G17_SHOCK_REVIEW.md`](experiments/orbital_discriminability/POST_G14_G17_SHOCK_REVIEW.md).

That spike is now complete. On the closed fixture, G22 remains controlling at
742,458.297 m peak-to-peak while the unchanged conservative pairwise physical
envelope is 23,037.025 m, leaving a 719,421.272 m mechanism margin. The result
is `PHASE_QUOTIENT_MECHANISM_DISCRIMINATIVE`. It demonstrates that preserving
continuous phase avoids the former finite-difference loss; it does not reopen
G14/G17 or authorize observations. The next step is a newly predeclared
phase-coordinate geometry set, screened by full remaining margin before any
observation-product discovery. See
[`GNSS_PHASE_QUOTIENT_SPIKE_REPORT.md`](experiments/orbital_discriminability/GNSS_PHASE_QUOTIENT_SPIKE_REPORT.md).

The bounded phase-coordinate screen is now complete. After excluding G14 and
G17 from candidate roles and the closed G11/G21 pair, all five remaining
pair/date windows are G22/G30 and have positive physical margin. The distinct-
pair rule retains DOY 220, 04:30:30--07:43:00 GPS: G14 is the controlling
wrong-orbit null at 824,736.025 m, the pairwise envelope is 19,767.924 m and
the remaining margin is 804,968.101 m. This is
`GNSS_PHASE_GEOMETRY_SELECTED`, still with zero observation-product
discovery or access. See
[`GNSS_PHASE_GEOMETRY_SCREEN_REPORT.md`](experiments/orbital_discriminability/GNSS_PHASE_GEOMETRY_SCREEN_REPORT.md).

The following structural-only contract is now frozen before any observation
product discovery. It predeclares G22/G30 DOY 216 as the independent
qualification geometry and keeps the DOY 220 primary candidate sealed. The
contract can test RINEX field topology, LLI and exact epoch continuity without
retaining values, but explicitly refuses to equate those facts with
geometry-free physical phase health. A structural pass can authorize only a
later health review, never measurement admission or an orbital score. See
[`GNSS_PHASE_STRUCTURAL_CONTRACT.md`](experiments/orbital_discriminability/GNSS_PHASE_STRUCTURAL_CONTRACT.md).

The authorized DOY 216 value-blind qualification has now returned
`GNSS_PHASE_STRUCTURE_REJECTED`. GOLD preserved the complete G22/G30 phase and
code topology, but NLIB did not: the longest four-link joint segment contains
282 rather than the frozen 386 epochs, and three NLIB code-witness links fail
the predeclared coverage/boundary rule. No phase scalar was parsed and the DOY
220 primary remains sealed. See
[`GNSS_PHASE_STRUCTURE_REPORT.md`](experiments/orbital_discriminability/GNSS_PHASE_STRUCTURE_REPORT.md).

The subsequent offline change-of-abstraction calculation did not reopen that
artifact. Using only exact-hash broadcast navigation on four other unopened
dates, it found `PHASE_SHORTER_WINDOW_PHYSICALLY_AVAILABLE`: all four dates
retain positive complete phase margin with a 60-epoch (30-minute) held-out
suffix and a 139-epoch raw interval. The worst remaining margin is
6,473.198 m, while the maximum four-link elevation guard rises from 15.616 deg
at the old duration to 39.467 deg. No RINEX product was discovered or opened,
and no new roles were assigned. See
[`GNSS_PHASE_DURATION_SENSITIVITY_REPORT.md`](experiments/orbital_discriminability/GNSS_PHASE_DURATION_SENSITIVITY_REPORT.md).

The distinct roles are now frozen before product discovery. DOY 217,
05:54:00--07:03:00 GPS is the sole qualification date; DOY 220,
05:42:00--06:51:00 GPS is the sealed held-out primary. The 139-epoch plan
keeps the ionosphere-free continuous-phase coordinate, 77/60 prefix/holdout
split, the prefix-affine null and G01/G14/G17 alternative orbits. A
qualification failure authorizes no substitute date, and primary access still
requires a separate review. See
[`GNSS_PHASE_SHORT_WINDOW_PLAN.md`](experiments/orbital_discriminability/GNSS_PHASE_SHORT_WINDOW_PLAN.md).

The sole DOY 217 qualification has now passed. Both exact station artifacts
were fully hashed before in-memory decode; all 3,336 relevant fields are
present across the 139-epoch window, C1C/C2W coverage is 100%, and all four
geometry-free phase links remain below the frozen continuity limit. The worst
aggregate second difference is 0.019274 m against a 0.095147 m limit. No
orbital model or score was available to this run, no observation value was
persisted and DOY 220 remains unopened. See
[`GNSS_PHASE_SHORT_WINDOW_QUALIFICATION_REPORT.md`](experiments/orbital_discriminability/GNSS_PHASE_SHORT_WINDOW_QUALIFICATION_REPORT.md).

The primary decoder/scorer is now frozen offline at source commit 548b7a2.
Exact-hash broadcast navigation produced the immutable DOY 220 orbital,
prefix-affine and G01/G14/G17 model coordinates, reproducing the controlling
8,857.432 m separation. The seal binds code, dependencies, plan,
qualification receipts and prediction artifact; it permits one transport
attempt per predeclared product, no suffix refit and no observation-value
persistence. The primary is still completely unopened and the seal grants no
live authority. See
[GNSS_PHASE_SHORT_WINDOW_PRIMARY_SEAL_REPORT.md](experiments/orbital_discriminability/GNSS_PHASE_SHORT_WINDOW_PRIMARY_SEAL_REPORT.md).

The single DOY 220 execution has now returned
ORBITAL_MODEL_PREDICTIVELY_PREFERRED. Both complete products were hashed
before in-memory decoding, the four phase links and all code witnesses passed,
and the orbital calibration residual was 0.367 m peak-to-peak. On the
untouched 60-epoch suffix, the orbital residual was 2.313 m versus
8,858.964 m for runner-up G01, leaving an 8,856.652 m preference margin
against the frozen 2,384.234 m guard. No observation value was persisted and
there is no retry. The authorized claim is a held-out orbital-model preference
for this fixed experiment, not satellite identity. See
[GNSS_PHASE_SHORT_WINDOW_PRIMARY_REPORT.md](experiments/orbital_discriminability/GNSS_PHASE_SHORT_WINDOW_PRIMARY_REPORT.md).

The next experiment is now frozen offline and asks a genuinely new question:
whether that preference repeats on a distinct pass. The outcome-blind
guard-first ranking selects DOY 219; DOY 218 remains sealed and cannot act as
a retry. Exact-hash broadcast NAV predicts a controlling 8,986.714 m G01
separation against the unchanged conservative 2,377.703 m guard. The
prediction and seal bind the same coordinate, nulls, measurement clauses and
prefix-only nuisance with zero DOY 219/218 product discovery or value access.
See
[GNSS_PHASE_REPEATED_PASS_SEAL_REPORT.md](experiments/orbital_discriminability/GNSS_PHASE_REPEATED_PASS_SEAL_REPORT.md).

The corresponding one-shot DOY 219 executor is also frozen offline. It does
not modify the consumed primary and reuses only an exact-hash model-blind
measurement kernel. The executor seal binds the DOY 219 grid, prediction,
thresholds, two predeclared locators, zero persistence and no-fallback rule;
it grants no live authority. See
[GNSS_PHASE_REPEATED_PASS_EXECUTOR_REPORT.md](experiments/orbital_discriminability/GNSS_PHASE_REPEATED_PASS_EXECUTOR_REPORT.md).

The authorized one-shot DOY 219 execution is now terminal with
`ORBITAL_MODEL_REPEATED_PASS_PREFERRED`. The orbital model left only
2.269 m peak-to-peak on the held-out suffix; the closest frozen null left
8,988.225 m, producing an 8,985.956 m preference above the 2,377.703 m guard.
This establishes repeated-pass consistency only for the exact GOLD/NLIB
G22/G30 DOY 220 and DOY 219 experiments. Both observation artifacts were
hashed before in-memory decode, no values were persisted, no retry occurred
and DOY 218 remains sealed. See
[GNSS_PHASE_REPEATED_PASS_OUTCOME_REPORT.md](experiments/orbital_discriminability/GNSS_PHASE_REPEATED_PASS_OUTCOME_REPORT.md).

The next physical challenge is now geometry-screened without observation
discovery: can the same G22/G30 coordinate survive on two sites wholly
disjoint from GOLD/NLIB? Six predeclared official IGS sites produced 15
four-link candidates on the frozen DOY 219 grid; all retain positive complete
margin. DRAO00CAN + WES200USA ranks first against G01 with a
`96588.530 m` separation, `3939.458 m` pairwise envelope and
`92649.071 m` remaining margin. These are candidate site roots, not yet
qualified historical hardware roots. No RINEX observation locator, header or
value was accessed and no prospective plan is frozen. The next maximum step
is one bounded value-blind capability qualification of DRAO/WES. See
[GNSS_PHASE_INDEPENDENT_PAIR_SCREEN_REPORT.md](experiments/orbital_discriminability/GNSS_PHASE_INDEPENDENT_PAIR_SCREEN_REPORT.md).

The subsequent metadata-only admission found that WES exposes a RINEX v2
primary feed, so its products cannot provide the frozen explicit `L1C/L2W`
identity without a post-hoc signal mapping. DRAO/WES is therefore rejected
before payload access. From the already frozen shortlist, ALGO00CAN +
MDO100USA is selected for one model-blind DOY217 qualification: it retains
`47828.042 m` of complete margin and supplies distinct DOMES, hardware
serials, agencies and primary data centers. The qualification plan contains
only two DOY217 locators; no DOY219 product has been named or opened. See
[GNSS_INDEPENDENT_PAIR_QUALIFICATION_PLAN.md](experiments/orbital_discriminability/GNSS_INDEPENDENT_PAIR_QUALIFICATION_PLAN.md).

That one qualification execution is now complete with
`GNSS_INDEPENDENT_PAIR_QUALIFICATION_PASSED`. Both products were hash-complete
before decode; the complete 139-epoch joint window, L1C/L2W plus LLI,
C1C/C2W witnesses and geometry-free health all passed. Compressed and decoded
RINEX persisted zero bytes, and no orbit or DOY219 product entered the
executor. This authorizes only a separate primary-selection review. See
[GNSS_INDEPENDENT_PAIR_QUALIFICATION_REPORT.md](experiments/orbital_discriminability/GNSS_INDEPENDENT_PAIR_QUALIFICATION_REPORT.md).

That review has now frozen one distinct DOY219 ALGO/MDO primary and all five
model curves. Only two descriptive HEAD requests were made; no observation
header, payload byte or value was accessed. The controlling wrong-orbit G14
separation remains `51370.299 m` against a `3542.257 m` pairwise physical
guard, leaving `47828.042 m`. The seal binds the exact broadcast NAV,
compiler, partition, nuisance and nulls but grants no primary authority. See
[GNSS_INDEPENDENT_PAIR_PRIMARY_PLAN.md](experiments/orbital_discriminability/GNSS_INDEPENDENT_PAIR_PRIMARY_PLAN.md).

The corresponding one-shot executor is now source-frozen and seal-bound. It
reuses the exact model-blind qualification parser and phase kernel, requires
both a separate authority token and the exact executor-seal hash, allows one
materialization attempt per frozen locator, and persists only an aggregate
strict-JSON receipt. Its seal records zero observation access and grants no
live authority. See
[GNSS_INDEPENDENT_PAIR_PRIMARY_EXECUTOR_REPORT.md](experiments/orbital_discriminability/GNSS_INDEPENDENT_PAIR_PRIMARY_EXECUTOR_REPORT.md).

The one authorized primary execution stopped before measurement admission with
`PRIMARY_ARTIFACT_MATERIALIZATION_FAILED`: the first ALGO materialization
timed out, no complete artifact was admitted, MDO was not attempted, and the
held-out comparison remains `NOT_EVALUATED`. The frozen zero-retry rule closes
this exact execution without an orbital claim. See
[GNSS_INDEPENDENT_PAIR_PRIMARY_OUTCOME_REPORT.md](experiments/orbital_discriminability/GNSS_INDEPENDENT_PAIR_PRIMARY_OUTCOME_REPORT.md).

The subsequent observation-blind screen fixes ALGO/MDO, G22/G30, the existing
nulls and partition, and compares only three new broadcast-navigation dates.
All are geometrically admissible; DOY223 ranks first with a 54,990.702 m
wrong-orbit G14 separation and 51,848.538 m remaining physical margin. No new
observation locator, header, payload byte or value was accessed, and no plan is
yet frozen. See
[GNSS_INDEPENDENT_PAIR_NEXT_PRIMARY_SCREEN_REPORT.md](experiments/orbital_discriminability/GNSS_INDEPENDENT_PAIR_NEXT_PRIMARY_SCREEN_REPORT.md).

The DOY223 ALGO/MDO primary contract is now frozen offline. It preserves the
selected window, coordinate, physical envelope and nulls while correcting the
DOY219 transport mistake: bounded retry/resume is allowed only before a
complete artifact hash and before decoding; after both hashes, network retry
is zero and measurement/scoring remain single-shot. No observation request was
made and the contract grants no execution authority. See
[GNSS_INDEPENDENT_PAIR_DOY223_PRIMARY_PLAN.md](experiments/orbital_discriminability/GNSS_INDEPENDENT_PAIR_DOY223_PRIMARY_PLAN.md).

The corresponding exact-hash DOY223 prediction set is also frozen. The NOAA
broadcast NAV compiler reproduces the G14-controlling 54,990.702 m held-out
separation, the 3,142.164 m pairwise guard and the 51,848.538 m remaining
margin on the exact 137-epoch feature grid. All observation access counters
remain zero, and the seal grants no authority to request ALGO or MDO. See
[GNSS_INDEPENDENT_PAIR_DOY223_PREDICTION_REPORT.md](experiments/orbital_discriminability/GNSS_INDEPENDENT_PAIR_DOY223_PREDICTION_REPORT.md).

The one-off DOY223 executor is now frozen as well, still with zero observation
access. It requires both complete product hashes before decoding, permits only
bounded pre-hash transport retry/resume, and has no post-decode retry or
scientific fallback. Its seal grants no live authority. See
[GNSS_INDEPENDENT_PAIR_DOY223_EXECUTOR_REPORT.md](experiments/orbital_discriminability/GNSS_INDEPENDENT_PAIR_DOY223_EXECUTOR_REPORT.md).

## Preserved Gate F2.5 experimental history

Gate F2.5 removed server waterfall (`W/F`) and `ext_api` from the causal gate
for same-Kiwi multichannel qualification. Its intended path is:

```text
frozen affordances
  -> direct simultaneous SND reference + perturbed attempt
  -> two IQ streams
  -> local in-memory STFT/PSD
  -> targetless feature + witness
  -> per-channel retune qualification
  -> immutable plan
  -> one prospective A1/B/A2 confirmation
  -> one outcome
```

The first and only live F2.5 execution ended correctly as
`QUALIFICATION_INCOMPLETE`: all six `/status` requests succeeded, but the
frozen center policy expected a `bandwidth` field that the responses did not
contain. No SND channel was attempted, no IQ was acquired and
`NO_MULTI_CHANNEL_CAPABILITY` was therefore forbidden. See
[`GATE_F2_5_OUTCOME_1.md`](experiments/live_instrument/GATE_F2_5_OUTCOME_1.md).

Gate F2.5.1 now removes that last pre-SND dependency offline. It freezes a
conservative Kiwi-family tuning interval and derives a qualification-only
coordinate without reading `status.bandwidth`; W/F remains absent and
`ext_api` remains a hint. The original outcome is unchanged, and no live
connection was made while preparing that offline checkpoint. See
[`GATE_F2_5_1_OFFLINE.md`](experiments/live_instrument/GATE_F2_5_1_OFFLINE.md).

The single authorised F2.5.1 live session then reached real dual-SND attempts
on every frozen candidate. One endpoint explicitly rejected public SND access;
the others remained indeterminate after WebSocket timeout/closure errors. The
terminal result is `QUALIFICATION_INCOMPLETE`, not a claim that multichannel
capability is absent. No topology, feature, plan or DDC hypothesis was
admitted. See
[`GATE_F2_5_1_OUTCOME_1.md`](experiments/live_instrument/GATE_F2_5_1_OUTCOME_1.md).

Gate F2.5.2 addresses that outcome strictly offline. It records reference and
perturbed opening as separate atomic receipts, hashes every ephemeral SND
frame before decode, and preserves any single-branch readiness witness even
when the peer fails. It does not change the candidates, tuning policy,
thresholds or DDC question, and no new live connection has been made. See
[`GATE_F2_5_2_OFFLINE.md`](experiments/live_instrument/GATE_F2_5_2_OFFLINE.md).

The single F2.5.2 live session ended as `QUALIFICATION_INCOMPLETE`, but its
atomic boundary exposed a real asymmetric result: one KFS reference branch
reached GNSS IQ readiness with two pre-decode-hashed frames while its perturbed
peer was explicitly rejected. No pair or DDC hypothesis was admitted. The run
also exposed two descriptive-control failures: retry eligibility still
depended on aggregate prose, and stdout-only receipts were not fully retained.
See
[`GATE_F2_5_2_OUTCOME_1.md`](experiments/live_instrument/GATE_F2_5_2_OUTCOME_1.md).

Gate F2.5.3 corrects those two control failures offline. Retry eligibility now
comes only from atomic branch state and typed transport errors; aggregate prose
cannot enable or disable it. A future session writes one bounded,
exclusive-create, strict-JSONL artifact containing descriptive receipts and
hashes while rejecting RF arrays and raw/derived sample fields. Sink or
serialization failure is descriptive and cannot alter the physical result.
No live connection was made. See
[`GATE_F2_5_3_OFFLINE.md`](experiments/live_instrument/GATE_F2_5_3_OFFLINE.md).

The pre-execution review found that F2.5.3's final artifact hash and emission
errors were returned in memory but discarded by its command-line entry point.
Gate F2.5.3.1 closes that final audit gap offline: the same JSONL ends with a
reserved terminal manifest containing a byte-exact prefix hash and retention
state, while the CLI exposes the closed file's overall hash. Runtime,
serialization and mirror failures remain descriptive. No network activity was
performed. See
[`GATE_F2_5_3_1_OFFLINE.md`](experiments/live_instrument/GATE_F2_5_3_1_OFFLINE.md).

The single authorised F2.5.3.1 session then exercised all six frozen
candidates and exactly the two allowed structured retries. No branch delivered
an IQ frame: explicit branch rejections coexisted with transport closures or a
timeout, so the correct outcome is `QUALIFICATION_INCOMPLETE`, not absence of
multichannel capability. No topology, feature, plan or DDC hypothesis was
evaluated. The 53-line receipt artifact closed `COMPLETE`, with matching prefix
and whole-file hashes and zero RF persistence. See
[`GATE_F2_5_3_1_OUTCOME_1.md`](experiments/live_instrument/GATE_F2_5_3_1_OUTCOME_1.md).

Gate F2.5.4 audits that frozen outcome without network activity. Four branch
receipts are explicit server-reported rejections, one is a timeout before any
server MSG, and eleven are not causally diagnosable from the retained fields.
In particular, `configuration_sent` records a local action, not remote
acceptance. Because all endpoints share one client implementation root and the
official frozen source revisions are not present locally, the correct exit is
`STOP_PENDING_CONTROL_DISCRIMINATORS`, not a protocol fix or another run. See
[`GATE_F2_5_4_PROTOCOL_AUDIT.md`](experiments/live_instrument/GATE_F2_5_4_PROTOCOL_AUDIT.md).

Gate F2.5.5 now specifies the missing control boundary offline. It keeps an
official-source clause separate from the ordered receipt clause, distinguishes
local command result, remote server field, WebSocket close, TCP loss and first
IQ, and forbids credentials or RF persistence. Because the pinned official
source artifacts and exact kiwiclient control path are not retained locally,
it fails closed as `SOURCE_BASIS_INCOMPLETE`; no implementation or live run is
authorised. See
[`GATE_F2_5_5_OFFLINE.md`](experiments/live_instrument/GATE_F2_5_5_OFFLINE.md).

Gate F2.5.6 then retrieved only the two official repositories at their frozen
commits; it made no Kiwi connection and acquired no RF. The minimal server
source is now retained and verified byte-for-byte. The exact kiwiclient paths
are resolved and hash-audited, but its source is not copied because no license
grant was found at the pinned revision. The correct fail-closed result is
`SOURCE_RETENTION_BLOCKED_BY_LICENSE`: protocol semantics are narrower and
better grounded, while the complete source basis is still not locally
reproducible. See
[`GATE_F2_5_6_SOURCE_REPRODUCTION.md`](experiments/live_instrument/GATE_F2_5_6_SOURCE_REPRODUCTION.md).

Gate F2.5.7 audits whether that client-retention limit actually blocks the
physical question. It does not: server semantics, ordered local sends and a
later hashed IQ witness are sufficient, while the reference client cannot
manufacture a configuration ACK the protocol does not expose. Synthetic
transcripts now distinguish auth, channel allocation, local `mod_iq`, IQ,
clean close and transport loss. The offline result is
`SERVER_WIRE_CONTRACT_SUFFICIENT`; receipt implementation may be prepared in a
separate gate, but no live execution is authorised. See
[`GATE_F2_5_7_SERVER_WIRE_AUDIT.md`](experiments/live_instrument/GATE_F2_5_7_SERVER_WIRE_AUDIT.md).

Gate F2.5.8 now integrates that contract in a new local successor path. It
preserves ordered allowlisted MSG fields, reads the real channel number from
`is_local`, delays `mod_iq` until auth/channel/rate are all witnessed, and
hashes the first qualifying IQ frame before decode. Local send errors,
control timeouts, close frames and transport loss remain distinct. All tests
use synthetic WebSocket frames; no endpoint was contacted. The result is
`ORDERED_WIRE_RECEIPT_IMPLEMENTED`, still with no live authorization. See
[`GATE_F2_5_8_ORDERED_RECEIPT.md`](experiments/live_instrument/GATE_F2_5_8_ORDERED_RECEIPT.md).

Gate F2.5.9 completes the offline pre-live composition review. The disposable
one-shot wrapper now injects only the ordered F2.5.8 opener, maps atomic receipt
states without parsing aggregate exception prose, retains typed pre-freeze
retry and terminal JSONL closure, and preserves the first-outcome stop. Calls
without a separate live authority fail before artifact creation or network
entry. No live execution occurred. See
[`GATE_F2_5_9_PRELIVE_RUNNER.md`](experiments/live_instrument/GATE_F2_5_9_PRELIVE_RUNNER.md).

Gate F2.5.10 freezes the exact execution envelope around that runner. A narrow
authority shim removes caller overrides for plan, receipt path and runtime
commit, verifies the reviewed causal sources and numerical environment, writes
the envelope as the first terminal-artifact receipt, and then invokes only the
F2.5.9 qualifier/retry path. Candidate order, targetless centers, timing, retry
and the first-outcome stop are explicit. The offline exit is
`REVIEWED_ONE_SHOT_READY_FOR_SEPARATE_AUTHORITY`; no Kiwi network activity was
performed or authorised. See
[`GATE_F2_5_10_EXECUTION_REVIEW.md`](experiments/live_instrument/GATE_F2_5_10_EXECUTION_REVIEW.md).

The single separately authorised Gate F2.5.10 run has now materialised that
envelope and stopped `QUALIFICATION_INCOMPLETE`. All six candidates received a
simultaneous dual-SND attempt; four branches returned explicit `badp`
rejections and eight reached channel allocation plus local `mod_iq` before an
observed close without a qualifying IQ-readiness event. No retry, discovery,
plan freeze or confirmation occurred. The 46-line terminal artifact is
complete and contains no persisted RF. See
[`GATE_F2_5_10_OUTCOME_1.md`](experiments/live_instrument/GATE_F2_5_10_OUTCOME_1.md).

## What can be claimed

Receipts may support narrow statements such as:

- a measurement satisfied a named clause before its TTL expired;
- two SND streams were simultaneous and independently sequenced;
- a feature behaved consistently with being upstream of a per-channel DDC;
- an observation was unavailable, unresolved, not detectable or not evaluated.

They do **not** automatically support:

- transmitter or satellite identity;
- external-RF origin;
- common physical cause;
- geolocation or TDoA;
- absence of a phenomenon when detectability was not established;
- multichannel unavailability when a second channel was never attempted.

## Quick start: offline verification

Python 3.11 or 3.12 is recommended.

```bash
python -m venv .venv

# Linux/macOS
source .venv/bin/activate

# Windows PowerShell
# .venv\Scripts\Activate.ps1

python -m pip install -r requirements-live-instrument.txt
python -m pytest experiments/live_instrument/tests experiments/orbital_discriminability/tests -q
```

The test suite is offline. It uses deterministic fixtures and synthetic IQ;
it does not contact SatNOGS, KiwiSDR or any other remote service.

Machine-readable experiment evidence is byte-bound. Repository
`.gitattributes` therefore disables platform line-ending conversion for every
experiment JSON/JSONL artifact. On a Windows host where the default pytest
temporary root has inherited unusable ACLs, use a fresh user-owned
`--basetemp` path before treating `PermissionError` as a repository failure;
do not alter evidence files or relax hashes to make such an environmental
failure pass.

## Live execution policy

Live runners are disposable experiment materializations, not daemons.

- Never run them as part of installation, import, tests or CI.
- Freeze candidates, order, transforms, thresholds, retry budget and stop
  condition before network access.
- Use only public capabilities and respect receiver-owner access limits.
- Retry only pre-freeze software/transport failures allowed by the frozen plan.
- After plan freeze: zero retry, endpoint change, frequency change, threshold
  change or second confirmation window.
- Hash ephemeral RF artifacts before analysis and destruction; persist only
  strict JSON receipts and hashes.

Every new live session requires explicit authorization. The repository's
documented outcomes must remain unchanged after the fact; fixes belong to a
new gate and a new commit.

The latest offline materialization is Gate F2.5.14: two injected semantic SND
branches are composed concurrently, evaluated by explicit topology clauses and
fed through the frozen candidate order to one terminal receipt. Its envelope
still requires post-commit causal-source review; it is not live authority.

Gate F2.5.15 now supplies that offline post-commit seal and a boolean-only
authority surface. It is ready to be reviewed for a separate exact live
authorization, but importing, assessing, testing or committing it performs no
network activity.

The single F2.5.15 authority has since been consumed. Its frozen outcome is
`QUALIFICATION_INCOMPLETE`: all candidates were attempted without retry, four
branches were explicitly rejected, eight closed after allocation without any
SND frame, and no dual-IQ pair was admitted. No cause is assigned to the empty
peer closes.

Gate F2.5.16 attributes that outcome offline. Ordered command hashes show that
all eight allocated branches emitted 15 or 16 keepalives before `AR OK`; the
pinned server source increments that count and contains an incomplete-setup
removal predicate above four. This falsifies the local assumption that
keepalive was neutral during setup, but it does not identify the live peer's
close cause: remote revision, command receipt, setup mask and close reason were
not observed. Physical dual-SND capability remains `NOT_EVALUATED`.

Gate F2.5.17 closes the missing source definition and repairs only that local
control defect. The pinned `CMD_SND_ALL` mask requires frequency, mode,
passband, AGC and `AR OK`. The successor waits for every required metadata
field, emits the complete setup exactly once, and permits a time-paced
keepalive only afterwards. Its receipt distinguishes local emission from the
still-unobservable remote setup state. The implementation is synthetic-only,
has no live connector and grants no acquisition authority.

Gate F2.5.18 composes two corrected branches concurrently, preserves the
same-Kiwi channel/connection/sequence/event-time topology clauses and runs the
unchanged candidate order into one terminal receipt. Both retry budgets remain
zero; status and waterfall remain outside the direct-SND admission path. The
module still requires injected connectors and post-commit review, so it cannot
contact a receiver or claim live authority.

Gate F2.5.19 seals the resulting commit, 21-file causal allowlist, numerical
environment and exact dual execution surface. Its only public control is
`run_reviewed_once(live_authorised=False)`; default refusal occurs before
receipt or connector access. The maximum future scope is one corrected
dual-SND qualification, stopping before discovery, retune or observation. The
seal is ready for a separate commit-specific authority but does not imply one.

That separate authority has now been consumed exactly once. The first frozen
candidate supplied two simultaneous semantic SND/IQ streams on distinct server
channels with distinct receipts and overlapping GNSS event time, yielding
`DUAL_SEMANTIC_PAIR_READY`. The run stopped immediately, persisted no RF and
did not perform feature discovery, retune or A1/B/A2. This qualifies the
same-Kiwi multichannel topology only; it does not yet support a physical-signal
or upstream/downstream claim. See
[`GATE_F2_5_19_OUTCOME_1.md`](experiments/live_instrument/GATE_F2_5_19_OUTCOME_1.md).

Gate F2.5.20 now composes that exact qualified endpoint with the already tested
prospective vertical, still entirely offline. The old readiness frames select
the capability but cannot satisfy future admission: corrected dual SND must be
requalified in the same session, followed by a new ephemeral discovery,
witness-only retune qualification, immutable freeze and exactly one independent
A1/B/A2. Thresholds are unchanged, both retry budgets are zero and the module
has no live surface pending a separate post-commit seal. See
[`GATE_F2_5_20_PROSPECTIVE_VERTICAL.md`](experiments/live_instrument/GATE_F2_5_20_PROSPECTIVE_VERTICAL.md).

Gate F2.5.21 supplies the required post-commit seal. It binds the reviewed
F2.5.20 commit, 22 causal files including the retained protocol artifacts, the
numerical environment, prospective control surface and live-wrapper source.
The sole control was `run_reviewed_once(live_authorised=False)` and its default
refusal occurred before receipt or connector access. See
[`GATE_F2_5_21_POST_COMMIT_SEAL.md`](experiments/live_instrument/GATE_F2_5_21_POST_COMMIT_SEAL.md).

That authority has now been consumed exactly once. Same-session direct SND
again admitted two simultaneous IQ channels, but the independent four-second
local discovery produced fewer than two distinct stable structures. The
terminal outcome is `NO_FALSIFIABLE_INTERVENTION`: no retune occurred, no plan
was frozen, no A1/B/A2 was run and neither DDC-boundary hypothesis was
evaluated. The strict receipt is complete with zero RF persistence. This is a
valid refusal to synthesize an experiment, not evidence that the passband
contained no signal. See
[`GATE_F2_5_21_OUTCOME_1.md`](experiments/live_instrument/GATE_F2_5_21_OUTCOME_1.md).

Gate F2.5.22 audits that failure without new data. The frozen discovery receipt
contains only the error-description hash, not the two ephemeral input hashes,
candidate counts or threshold margins, so the underlying reason for “fewer
than two structures” is not attributable. The audit also finds that legacy
peak widths can be inflated by the admission mask sentinel. A synthetic-only
alternative keeps the orthogonal-witness requirement but removes the needless
assumption that it must be a second narrowband peak: a target-excluded
distributed spectral fingerprint, fixed reference branch, unique perturbed
translation and A2 return can qualify the DDC coordinate transform. No live
capability or target physics is thereby qualified. See
[`GATE_F2_5_22_DISCOVERABILITY_AUDIT.md`](experiments/live_instrument/GATE_F2_5_22_DISCOVERABILITY_AUDIT.md).

Gate F2.5.23 integrates that result into an offline successor. Injected
phase-aware sockets establish the dual-channel topology; one stable target is
then sufficient because a target-excluded distributed fingerprint separately
qualifies the retune. Deterministic tests prove that changing the target at all
predeclared control positions cannot change witness state, orientation or
scores. The successor freezes distinct upstream/channel-fixed predictions,
negative controls, one future confirmation and zero retry. It still has no
connector or authority. See
[`GATE_F2_5_23_ONE_TARGET_SUCCESSOR.md`](experiments/live_instrument/GATE_F2_5_23_ONE_TARGET_SUCCESSOR.md).

Gate F2.5.24 now implements the missing confirmation evaluator offline. Before
examining the target it requires six distinct post-freeze artifacts, an exact
channel/tune ledger, continuous event-time streams and a uniquely translating
target-excluded distributed witness. Deterministic fixtures reach all five
frozen outcomes without changing the plan and prove that invalid intervention
clauses block target evaluation, while lost target detectability remains a
separate `NOT_DETECTABLE` result. The evaluator has no connector, live runner
or execution authority and persists no RF. See
[`GATE_F2_5_24_CONFIRMATION_EVALUATOR.md`](experiments/live_instrument/GATE_F2_5_24_CONFIRMATION_EVALUATOR.md).

Gate F2.5.25 supplies the post-commit seal and the only authority-facing
composition. It binds F2.5.24, all causal source hashes, the numerical
environment and the complete live surface. The composition keeps the same two
SND channels open from requalification through the only confirmation, closes
the diagnostic command ledger before confirmation, and always attempts channel
closure afterward. Its sole public argument is a default-false authority bit.
The seal was built and tested offline; it grants and consumes no live
authority. See
[`GATE_F2_5_25_POST_COMMIT_SEAL.md`](experiments/live_instrument/GATE_F2_5_25_POST_COMMIT_SEAL.md).

That authority has now been consumed once. The endpoint allocated two channels
and delivered hundreds of decodable IQ/SND frames, but none supplied an
admissible event-time witness: GPS solution age was 92–103 seconds against the
frozen 30-second maximum. The terminal outcome is
`QUALIFICATION_INCOMPLETE`; discovery, retune, plan freeze and confirmation are
all `NOT_EVALUATED`. This is not evidence that no signal or multichannel
capability existed. It demonstrates that data availability and measurement
admissibility are separate clauses. See
[`GATE_F2_5_25_OUTCOME_1.md`](experiments/live_instrument/GATE_F2_5_25_OUTCOME_1.md).

Gate F2.5.26 attributes that failure offline. The pinned server source confirms
that the recorded field is elapsed seconds since the latest GPS position
solution, while the receipt proves both transports and decoders remained
active. The timeout was a consequence of the frozen temporal clause, not the
absence of SND/IQ. Absolute fresh GNSS was not explicitly derived from the
same-ADC DDC hypothesis, but the receipt lacks the arrival, sample-clock and
command-boundary statistics needed to test a relative-time alternative. The
old outcome therefore remains unchanged and the alternative is
`NOT_FALSIFIABLE_WITH_THIS_RECEIPT`. See
[`GATE_F2_5_26_TEMPORAL_FAILURE_ATTRIBUTION.md`](experiments/live_instrument/GATE_F2_5_26_TEMPORAL_FAILURE_ATTRIBUTION.md).

Gate F2.5.27 now materialises that new temporal contract offline. It does not
relax the consumed run: the new causal cut requires actual server timestamps,
sample counts and monotonic arrivals that the old receipt did not preserve.
For a future same-ADC trial, timestamp steps must close against sample geometry
within one sample, channel sequences must remain contiguous, reserved server
clock states are refused, and the two streams must overlap for at least two
existing STFT windows. Absolute GNSS freshness is explicitly `NOT_REQUIRED`
for this cut, while command boundaries receive independent scalar witnesses.
No connector or authority has been added. See
[`GATE_F2_5_27_RELATIVE_TIME_ADMISSION.md`](experiments/live_instrument/GATE_F2_5_27_RELATIVE_TIME_ADMISSION.md).

Gate F2.5.28 integrates that contract into an injected one-shot path. Every SND
artifact is hashed before decode, the temporal receipt controls whether
read-only in-RAM IQ can reach discovery, discovery controls retune access, and
retune qualification requires both A1→B and B→A2 boundary witnesses. All IQ
arrays are overwritten and verified in `finally`; the returned result contains
only strict scalar/hash receipts. Tests measure zero downstream callback calls
on temporal failure. The exact parser, one-shot surfaces, parent sources and
numerical environment are sealed, but no connector or live authority is
present. See
[`GATE_F2_5_28_INJECTED_ONE_SHOT.md`](experiments/live_instrument/GATE_F2_5_28_INJECTED_ONE_SHOT.md).

Gate F2.5.29 now supplies the missing phase-aware transport boundary, still
entirely offline. Two injected SND branches execute the exact
auth → metadata → one-shot setup → SND order concurrently. Each transport
frame transfers through an explicit byte lease, its artifact is hashed, and
the lease is released before analysis; bounded SND copies are cleared after
the F2.5.28 call while decoded IQ is zeroized by that parent gate. The wrapper
does not reuse the obsolete absolute-age rejection: distinct channels,
same-clock continuity and relative overlap decide access. No connector, public
runtime override or live authority exists. See
[`GATE_F2_5_29_PHASE_AWARE_INJECTED_BRIDGE.md`](experiments/live_instrument/GATE_F2_5_29_PHASE_AWARE_INJECTED_BRIDGE.md).

Gate F2.5.30 audits whether that bridge can honestly receive a live authority
bit. It cannot yet: both collectors close their channel sockets before the
F2.5.28 discovery and retune callbacks run, and those callbacks receive no
control handle. Commit, source and envelope seals all pass, so the terminal
result is `LIVE_SURFACE_NOT_SEALABLE`, not a qualification or capability
failure. The relative-time work remains reusable, but no nominal live runner
was created. See
[`GATE_F2_5_30_SEALABILITY_AUDIT.md`](experiments/live_instrument/GATE_F2_5_30_SEALABILITY_AUDIT.md).

Gate F2.5.31 repairs that lifetime exclusively with injected sockets. One
outer owner keeps the two admitted handles open through local A1 discovery and
both A1→B→A2 command boundaries; only a private executor can tune the
perturbed branch. Settling frames remain in the full sequence-continuity
ledger, while all IQ and both handles are released in the outer `finally`.
The result still leaves RF response and DDC-location hypotheses
`NOT_EVALUATED`: command topology is now valid, but it is not a substitute for
the distributed RF-structure witness. See
[`GATE_F2_5_31_OPEN_HANDLE_SUCCESSOR.md`](experiments/live_instrument/GATE_F2_5_31_OPEN_HANDLE_SUCCESSOR.md).

Gate F2.5.32 closes the remaining offline RF-response integration cut. The
existing distributed witness first excludes every target/control position and
must show a fixed reference, one unique perturbed translation and an A2 return.
Only then are target predictions hashed and B/A2 target matching allowed. The
synthetic suite distinguishes `INTERVENTION_INVALID`, `NOT_DETECTABLE`, both
directional DDC hypotheses and `AMBIGUOUS` without changing thresholds. All IQ
is still ephemeral and no live authority exists. See
[`GATE_F2_5_32_RF_RESPONSE_INTEGRATION.md`](experiments/live_instrument/GATE_F2_5_32_RF_RESPONSE_INTEGRATION.md).

Gate F2.5.33 now seals that exact commit and execution surface. The only
live-capable signature contains one keyword-only `live_authorised=False` bit;
default refusal occurs before assessment, receipt creation or connector
access. The endpoint, dual-channel topology, control geometry, thresholds,
receipt path, zero-retry rule and one-outcome stop are not caller parameters.
The assessment is offline and no authority has been consumed. See
[`GATE_F2_5_33_POST_COMMIT_SEAL.md`](experiments/live_instrument/GATE_F2_5_33_POST_COMMIT_SEAL.md).

The single Gate F2.5.33 authority has now been consumed. Two simultaneous
same-clock SND/IQ channels and relative temporal admission succeeded, but the
unchanged A1 discovery admitted no common feature. The run therefore stopped
`NO_FALSIFIABLE_INTERVENTION` before retune, plan freeze or physical-hypothesis
evaluation. This is not evidence that the passband contained no signals. See
[`GATE_F2_5_33_OUTCOME_1.md`](experiments/live_instrument/GATE_F2_5_33_OUTCOME_1.md).

Gate F2.5.34 attributes that negative using only the committed receipt and
source seals. The dual-channel measurement and spectral transform were
operational, and the complete frozen feature rule was unsatisfied. The
receipt does not retain peak counts, per-stage rejection counts or threshold
margins, so contrast, patch validity, correlation and half-window stability
remain indistinguishable. The physical DDC hypothesis is still
`NOT_FALSIFIABLE_WITH_THIS_RECEIPT`. A prior scalar audit already contains the
needed descriptive shape, so no new framework or selector change is proposed.
See
[`GATE_F2_5_34_DISCOVERY_FAILURE_ATTRIBUTION.md`](experiments/live_instrument/GATE_F2_5_34_DISCOVERY_FAILURE_ATTRIBUTION.md).

Gate F2.5.35 integrates the minimum future repair offline without touching the
frozen runtime. The unchanged one-feature selector first emits its
authoritative `DiscoveryReceipt`; a sibling scalar audit then records stage
counts and finite threshold margins against the same 16 pre-analysis frame
hashes. Audit construction failure becomes `DESCRIPTION_ERROR` and cannot
change selection, retune control flow or physical outcome. Synthetic negative
and positive full-vertical tests preserve the F2.5.32 decisions, while no IQ,
STFT, spectrum or candidate patch persists. See
[`GATE_F2_5_35_SCALAR_AUDIT_INTEGRATION.md`](experiments/live_instrument/GATE_F2_5_35_SCALAR_AUDIT_INTEGRATION.md).

Gate F2.5.36 seals that exact committed successor offline. The F2.5.35 source,
inherited plan, decision/audit and full integration surfaces, reviewed dual-SND
connector, numerical environment, endpoint, zero-retry policy and strict
receipt shape are hash-bound. The sole public execution signature exposes
only `live_authorised=False`, and default refusal precedes assessment, receipt
creation and connector access. No authority is granted or consumed. See
[`GATE_F2_5_36_POST_COMMIT_SEAL.md`](experiments/live_instrument/GATE_F2_5_36_POST_COMMIT_SEAL.md).

The single Gate F2.5.36 authority has now been consumed. Two simultaneous SND
channels passed relative-time admission and the unchanged selector admitted a
common feature with positive contrast, correlation and half-stability margins.
Both retune boundaries were witnessed, but the final session-continuity check
stopped `INTERVENTION_INVALID`, leaving both physical hypotheses
`NOT_EVALUATED`. Receipt-only reconstruction exactly attributes its one
violation per branch to a software evaluator that included the already counted
leading-zero timestamp. The frozen live outcome is not evidence of a remote
clock jump or of either DDC-location hypothesis. See
[`GATE_F2_5_36_OUTCOME_1.md`](experiments/live_instrument/GATE_F2_5_36_OUTCOME_1.md).

Gate F2.5.37 repairs only that duplicated timestamp semantics offline. The
full-session evaluator reuses the existing F2.5.27 leading-zero and GPS-week
normalization, retains every prior sequence/tolerance/receipt rule and leaves
the frozen F2.5.31–36 sources untouched. Deterministic tests reproduce the
exact live residual, reject interior zeros, preserve rollover and show the
corrected synthetic vertical passing beyond the former false block. No live
claim, connector or authority is added. See
[`GATE_F2_5_37_CONTINUITY_NORMALIZATION.md`](experiments/live_instrument/GATE_F2_5_37_CONTINUITY_NORMALIZATION.md).

Gate F2.5.38 now seals that corrected vertical offline. The F2.5.37 commit,
source, plan, continuity evaluator, temporary installation scope, integration,
reviewed dual-SND connector, numerical environment, strict receipt and full
live surface are hash-bound. The sole public execution signature contains only
`live_authorised=False`, and its default refusal precedes every side effect.
No network activity or authority consumption occurs. See
[`GATE_F2_5_38_POST_COMMIT_SEAL.md`](experiments/live_instrument/GATE_F2_5_38_POST_COMMIT_SEAL.md).

The separately authorised Gate F2.5.38 execution has now consumed that surface
once, with zero retry. Two simultaneous SND/IQ channels and the corrected
relative-time clauses passed. Local discovery then stopped
`NO_FALSIFIABLE_INTERVENTION`: five complete candidates were evaluated, four
passed the frozen correlation threshold, and none passed the unchanged
minimum contrast in both temporal halves. No retune was emitted and both DDC
hypotheses remain `NOT_EVALUATED`. The receipt contains scalar decisions and
hashes only; RF persistence is zero. See
[`GATE_F2_5_38_OUTCOME_1.md`](experiments/live_instrument/GATE_F2_5_38_OUTCOME_1.md).

## Closed post-METEOR route: DORIS transmitter geometry

The METEOR OpenWebRX and SatNOGS measurement paths are closed. The bounded
change-of-observable review now selects DORIS for an orbit-only geometry spike:
independent ground beacons transmit to one simultaneous dual-frequency
spaceborne receiver. For Sentinel-3A on 2026-09-02, three predeclared beacon
pairs retain positive preliminary held-out geometry margins of 34.856 kHz,
21.466 kHz and 18.145 kHz against the controlling affine/along-track
alternatives after the prior-forecast envelope.

The terminal is deliberately
`DORIS_FORWARD_GEOMETRY_SHORTLISTED_MEASUREMENT_UNADMITTED`. The calculation
opened only exact-hash CNES extrapolated SP3 products; DORIS RINEX access and
observation-value access were both zero. Exact beacon coordinates, the
one-way phase model, atmosphere, header frequency factors, receiver-clock
semantics, phase continuity and candidate-window coverage remain unresolved.
The next maximum action, after review, is one development-only structural and
metadata qualification—not a primary score or another receiver search. See
[`DORIS_FORWARD_GEOMETRY_SPIKE_REPORT.md`](experiments/orbital_discriminability/DORIS_FORWARD_GEOMETRY_SPIKE_REPORT.md).

That header-only development qualification is now complete and stops
`DORIS_DEVELOPMENT_HEADER_REJECTED`. The exact Sentinel-3A DGXX-S product
declares L1/L2 phase, C1/C2 same-path code, the receiver/antenna identity, the
L2/L1 date offset, 56 station references and two complete shortlist pairs.
However, the predeclared `INTERVAL`, `TIME OF LAST OBS` and `MARKER TYPE`
records are absent. Cadence, final coverage, simultaneous pair epochs and
phase flags therefore remain unproved. Zero observation records and zero
candidate-day bytes were accessed. The smallest next physical test would be a
separately authorised value-blind structural scan of this same development
product, not another header search. See
[`DORIS_DEVELOPMENT_HEADER_REPORT.md`](experiments/orbital_discriminability/DORIS_DEVELOPMENT_HEADER_REPORT.md).

The separately authorised value-blind structural scan is also complete and
stops `DORIS_DEVELOPMENT_STRUCTURE_INSUFFICIENT`. It scanned all 16,704 epochs
and 39,024 station records while decoding and persisting zero observation
magnitudes. PAUB–RIMC has 633 s of joint L1/L2 core phase coverage against a
480 s requirement; TLSB–WEUC reaches 393 s against 430 s. Neither pair has a
continuous C1/C2 witness admitted by the frozen time-reference-validity rule,
so measurement admission and orbital scoring remain `NOT_EVALUATED`.
Candidate DOY245 access remains zero. The result now requires an offline
change-of-observable review, not a primary download or a weaker threshold. See
[`DORIS_DEVELOPMENT_STRUCTURAL_REPORT.md`](experiments/orbital_discriminability/DORIS_DEVELOPMENT_STRUCTURAL_REPORT.md).

That offline role audit now stops
`DORIS_DUAL_PHASE_DIFFERENTIAL_REQUIRES_COEPOCH_REQUALIFICATION`. Exact rational
L1/L2 combination cancels first-order ionosphere, and an exact-coepoch
left-minus-right beacon difference cancels the shared receiver clock and
receiver proper-time terms. The existing 633 s PAUB–RIMC result is only an
intersection of independent station grids, however, so it does not establish
that topology. Per-target C1/C2 time-reference validity is no longer treated as
a universal witness, but an independently bounded absolute event-time bridge
and every surviving physical term remain mandatory. Measurement admission and
orbital scoring are still `NOT_EVALUATED`; candidate-day and observation-value
access remain zero. See
[`DORIS_OBSERVABLE_ROLE_AUDIT_REPORT.md`](experiments/orbital_discriminability/DORIS_OBSERVABLE_ROLE_AUDIT_REPORT.md).

The separately authorised value-blind requalification now establishes
`DORIS_EXACT_COEPOCH_TOPOLOGY_QUALIFIED`. PAUB–RIMC has 128 valid paired L1/L2
epochs carrying identical receiver timestamps across 633 s, with no
interpolation or nearest-neighbor matching, against the frozen 480 s
requirement. This closes the shared receiver clock/proper-time topology cut;
it does not close absolute event time or the remaining propagation, antenna,
oscillator and receiver-noncommon terms. One exact development artifact was
hash-verified, streamed once and destroyed; observation magnitudes, C1/C2
values/flags and candidate DOY245 access remained zero. Measurement and
orbital scoring remain `NOT_EVALUATED`. See
[`DORIS_EXACT_COEPOCH_REQUALIFICATION_REPORT.md`](experiments/orbital_discriminability/DORIS_EXACT_COEPOCH_REQUALIFICATION_REPORT.md).

The bounded follow-on physical audit stops
`DORIS_PHYSICAL_ENVELOPE_BOUND_UNAVAILABLE`. It preserves the exact
first-order-ionosphere and shared-receiver clock/proper-time cancellations,
but finds no finite outcome-independent uncertainty family for all eight
surviving event-time, propagation, antenna, ground-USO and receiver-noncommon
terms. It also prevents a subtle cross-date error: the 633 s topology proof is
from the 2026-08-30 development file, while the 18.145 kHz orbit-only ceiling
belongs to the unopened 2026-09-02 candidate geometry. No combined physical
margin or detector requirement can yet be computed, and candidate access
remains unauthorized. See
[`DORIS_PHYSICAL_ENVELOPE_AUDIT_REPORT.md`](experiments/orbital_discriminability/DORIS_PHYSICAL_ENVELOPE_AUDIT_REPORT.md).

The resulting offline change-of-abstraction review selects
`DORIS_TIME_REFERENCE_PAIR_SELECTED_GEOMETRY_UNEVALUATED`. Exact symbolic
coefficients disprove a tempting shortcut: a two-satellite/four-link double
difference cancels receiver clocks only by leaving each beacon clock sampled
at two different retarded emission epochs. Aligning emission epochs restores
receiver-clock differences instead. The minimum candidate topology is now one
satellite plus two header-declared time-reference beacons at exact common
receive epochs. This replaces uncharacterized standard-beacon USOs with an
external calibration path, but does not yet admit that path or cancel
receiver-noncommon channel behavior. The next maximum action is an orbit-only
screen of the six frozen pairs from ADHC, HBMB, PAUB and TLSB; no observation
access is authorized. See
[`DORIS_OBSERVABLE_TOPOLOGY_REVIEW_REPORT.md`](experiments/orbital_discriminability/DORIS_OBSERVABLE_TOPOLOGY_REVIEW_REPORT.md).

That orbit-only screen is now complete as
`DORIS_TIME_REFERENCE_TOPOLOGY_NO_JOINT_VISIBILITY`. All six frozen pairs are
continuously outside the simultaneous Sentinel-3A visibility caps at the
unchanged 10 degree elevation threshold. The closest pair, ADHC-PAUB, still
exceeds the conservative joint cap by 27.541 degrees; every direct 10 s-grid
check has zero joint samples. With no 360 s common window there can be no
calibration prefix or held-out suffix, so every frozen null is correctly
`NOT_EVALUATED_NO_ADMISSIBLE_JOINT_WINDOW`. No RINEX or observation value was
opened, and all exact-hash SP3 artifacts were destroyed after analysis. This
time-reference-pair topology is closed for the frozen Sentinel-3A geometry;
the next work must change the observable abstraction, not search for a more
convenient file or weaken visibility. See
[`DORIS_TIME_REFERENCE_GEOMETRY_SCREEN_REPORT.md`](experiments/orbital_discriminability/DORIS_TIME_REFERENCE_GEOMETRY_SCREEN_REPORT.md).

The follow-on offline contact-topology spike now stops
`DORIS_STRUCTURAL_VISIBILITY_NOT_FALSIFIABLE_FROM_RETAINED_RECEIPT`. Beacon
contact order and duration could in principle preserve orbital visibility
while avoiding the impossible simultaneous time-reference pair, but the
frozen structural evidence cannot test that observable. The header declares
56 stations while the receipt summarizes only four preselected stations and
only their five longest phase-continuity segments. Those boundaries are
LLI/discontinuity or gap events, not geometric rise/set; receiver scheduling,
tracking allocation, acquisition/dropout and telemetry-retention semantics
are also unresolved. A positive record is therefore evidence of receiver
output, while an absent record cannot be interpreted as physical
nonvisibility. Every contact-topology null remains
`NOT_EVALUATED_INSUFFICIENT_EVENT_TOPOLOGY`; no new artifact, orbit product,
measurement value or primary was accessed. See
[`DORIS_CONTACT_TOPOLOGY_SPIKE_REPORT.md`](experiments/orbital_discriminability/DORIS_CONTACT_TOPOLOGY_SPIKE_REPORT.md).

The official 2026 IDS receiver-designation description now closes the missing
causal edge rather than rescuing it. DGXX/DGXX-S has seven processing units,
but more beacons can be physically co-visible. Selection may depend on
frequency, power, random DAS-T choice or DIODE; Sentinel-3 assigns channels
1--5 through DIODE and 6--7 through DAS-T, and configurations can change in
flight. A missing RINEX station record therefore cannot be identified with
geometric nonvisibility even if a future scanner retained every station.
Reconstructing historical receiver designation is not the next experiment.

## Current route: identity-blind all-track GNSS assignment

An offline mechanism spike now returns
`ALL_TRACK_BLIND_ASSIGNMENT_MECHANISM_DISCRIMINATIVE`. It removes the earlier
experiment-side G22/G30 selection: all six synthetic tracks enter as opaque
identifiers and are compared against all 720 orbit-to-track bijections plus a
prefix-affine null. Common-mode ensemble centering avoids a privileged
reference, every hypothesis receives the same ten effective prefix-affine
parameters, and no suffix refit or free time phase exists.

The exact correct fixture retains an `8,432.443650 m` assignment margin above
a numerical-zero residual. Correct and permuted-track controls are concordant
after reveal; swapped code labels remain discordant; affine data select the
null; an out-of-family curvature fails the absolute-fit guard; and the closest
assignment midpoint remains ambiguous. The receiver's upstream code
correlation remains an explicit non-independent witness, so this is not
code-free identity evidence. See
[`GNSS_ALL_TRACK_ASSIGNMENT_SPIKE_REPORT.md`](experiments/orbital_discriminability/GNSS_ALL_TRACK_ASSIGNMENT_SPIKE_REPORT.md).

The bounded orbit-only screen now advances the mechanism to
`ALL_TRACK_GEOMETRY_SHORTLISTED_MEASUREMENT_UNADMITTED`. Across three
predeclared stations and five predeclared broadcast-navigation days, 3,403 of
13,465 exactly-six-track windows pass the conservative three-guard decision
condition. The top three are ALGO00CAN on DOY230, DOY229 and DOY231 with the
same G05/G15/G18/G20/G21/G29 codebook and `48.749--49.100 km` robust lower
margins. No observation product was searched or opened; all ephemeral
navigation files were deleted. The next maximum action, only after review, is
selection of one independent structural qualification artifact. A future
seventh complete track is a refusal, not permission to select a PRN subset.
See
[`GNSS_ALL_TRACK_GEOMETRY_SCREEN_REPORT.md`](experiments/orbital_discriminability/GNSS_ALL_TRACK_GEOMETRY_SCREEN_REPORT.md).

The next bounded selection is now frozen as
`QUALIFICATION_ARTIFACT_SELECTED_PAYLOAD_UNOPENED`. The single qualification
artifact is ALGO00CAN DOY229,
`ALGO00CAN_R_20262290000_01D_30S_MO.crx.gz`, verified by metadata-only BKG
directory and HEAD requests. Its body remains unopened. The future scanner is
limited to all-track structural presence, L1C/L2W LLI and exact 30 s
continuity; it may retain no measurement magnitude and must fail unless
exactly six complete GPS tracks exist. DOY230 and DOY231 retain no measurement
role. Separate authorization is required before materialization. See
[`GNSS_ALL_TRACK_QUALIFICATION_PLAN.md`](experiments/orbital_discriminability/GNSS_ALL_TRACK_QUALIFICATION_PLAN.md).

The authorized ALGO DOY229 qualification then terminated before record
traversal as `QUALIFICATION_DESCRIPTION_ERROR / ANTENNA_TYPE_CHANGED`. The
complete artifact was hashed in RAM (`4,317,738` bytes, SHA-256
`88aa876b787cac583345d512b2f705ec19062a5f71c38c3a4ae0da45f8095f24`)
before decompression; no observation scalar or artifact byte was persisted.
The error is descriptive: the scanner reused a `3A20` receiver-field split for
the RINEX `ANT # / TYPE` record, which the specification defines as `2A20`.
Consequently, the exact-six-track topology, measurement admission and orbital
score all remain `NOT_EVALUATED`; this is not evidence that ALGO lacks the
required tracks. The product will not be reopened without new authority. See
[`GNSS_ALL_TRACK_QUALIFICATION_DESCRIPTION_ERROR.md`](experiments/orbital_discriminability/GNSS_ALL_TRACK_QUALIFICATION_DESCRIPTION_ERROR.md).

The bounded offline repair now parses the antenna record as RINEX `2A20` and
the IGS type field as A16 model plus A4 radome. It changes no geometry, window,
observable role, LLI rule or six-track criterion. The historical description
error remains immutable and the runner still refuses a repeat before network
access; a distinct retry receipt and new explicit materialization authority
would be required to resume the same physical qualification.

That distinct retry is now frozen offline, not executed. It binds the old
terminal, the repair, both parser hashes, the unchanged scientific contract
and the already observed exact artifact identity. A future authorized run may
write only `*_RETRY_*` receipts and must leave the historical outcome intact.
There is one parser-repair execution, at most two transport attempts before a
complete hash, and zero retry after hashing. No ALGO bytes were accessed while
building this contract. See
[`GNSS_ALL_TRACK_QUALIFICATION_RETRY_PLAN.md`](experiments/orbital_discriminability/GNSS_ALL_TRACK_QUALIFICATION_RETRY_PLAN.md).

The single retry is now consumed as
`GNSS_ALL_TRACK_STRUCTURAL_QUALIFICATION_FAILED`. Header admission and all 139
epochs passed, but the value-blind scan found 7 complete L1C/L2W tracks among
11 seen, not the required 6. The post-decision reveal shows that all six
orbit-codebook PRNs are complete and G11 is an additional complete track.
Removing G11 would be post-hoc codebook selection, so the exact-six ALGO path
is closed. No observation value, measurement admission, orbital score or
primary selection occurred. See
[`GNSS_ALL_TRACK_QUALIFICATION_RETRY_OUTCOME_REPORT.md`](experiments/orbital_discriminability/GNSS_ALL_TRACK_QUALIFICATION_RETRY_OUTCOME_REPORT.md).

The bounded offline change-of-abstraction spike now returns
`ALL_TRACK_ONE_CLUTTER_MECHANISM_DISCRIMINATIVE`. It enumerates all 5,040 ways
to inject six orbital curves into seven opaque tracks, plus equally bounded
time-reversed and affine null families. Positive and permutation controls
clear both assignment and null guards. The hardened controls also admit an
independently compiled orbital-shaped extra track, refuse a codebook with one
expected member missing and two structured nonmembers, and let a post-score
code witness veto an otherwise preferred anonymous assignment. Affine and
reversed data select nulls; excess clutter is inadmissible; an exact duplicate
and a non-identical 1.5 s local time-shift remain ambiguous. This shows that
exact track-count equality is not essential without turning the clutter budget
into a rescue mechanism. It does not retroactively admit ALGO because the
model was designed after that outcome, and it is not a novelty claim without a
separate systematic literature review. See
[`GNSS_ALL_TRACK_CLUTTER_SPIKE_REPORT.md`](experiments/orbital_discriminability/GNSS_ALL_TRACK_CLUTTER_SPIKE_REPORT.md).

The current boundary is therefore procedural as well as numerical: no new
parser, decoder or artifact access is justified merely by this synthetic
result. The next possible physical step is one separately reviewed prospective
seven-track/one-clutter experiment whose complete topology, witness and null
surface are frozen before selecting or opening its qualification artifact.

That prospective proof is now frozen around DRAO00CAN without selecting an
observation product. It excludes consumed ALGO and the already rejected WES
signal path, assigns DOY230 to structural qualification and DOY231 to a later
held-out primary geometry, and fixes exactly seven opaque tracks, one symmetric
exclusion, all 10,087 orbital/null hypotheses and post-hash code-witness
semantics. DOY231 retains `49,319.268 m` exact separation from the closest
wrong assignment and a `27,300.164 m` three-guard lower margin.

This is `DRAO_ONE_CLUTTER_PROSPECTIVE_PLAN_FROZEN`, not product selection or
measurement authority. Before any locator is chosen, a DRAO-specific physical
envelope must bound every declared timing, propagation, orbit/clock, antenna
and receiver term inside the frozen `7,339.701 m` ceiling. Failure ends the
route without observation access. See
[`GNSS_DRAO_ONE_CLUTTER_PROSPECTIVE_PLAN.md`](experiments/orbital_discriminability/GNSS_DRAO_ONE_CLUTTER_PROSPECTIVE_PLAN.md).

## Repository map

```text
experiments/orbital_discriminability/
  trajectory.py             synchronized orbital observables and envelopes
  nuisance.py               calibration-only nuisance projection
  null_models.py            frozen non-orbital and geometry-breaking nulls
  heldout.py                immutable plan and outcome semantics
  synthetic.py              deterministic discriminability sweep
  g1_admission.py            pass-specific receiver-pair admission
  g1_synthetic.py            offline admission/refusal verticals
  G0_*.md, G1_*.md           scope, evidence, limits and next boundaries
  tests/                    offline orbital-mechanism test suite

experiments/live_instrument/
  models.py                 strict receipts, clause and JSON boundary
  orbital_kernel.py         stateless Skyfield geometry/Doppler kernel
  satnogs_probe.py          model-conditioned published artifacts
  satnogs_failover.py       clause-driven continuity/corroboration failover
  kiwi_probe.py             targetless dual-Kiwi capture and in-session nulls
  kiwi_prospective.py       discovery/prediction/confirmation separation
  kiwi_gate_e.py            detectability and qualification experiments
  kiwi_gate_f2*.py          capability-first and same-Kiwi DDC interventions
  tests/                     offline deterministic test suite
  CHECKPOINT_*.md            checkpoint evidence
  GATE_*.md                  frozen plans, outcomes and postmortems

analysis/, collectors/, processors/, trackers/
  original offline satellite prototype, retained for reference

api/, workers/, core/, receivers/
  legacy architecture retained for reference; not the supported path
```

For mechanisms and state semantics, read
[`README_TECHNICAL.md`](README_TECHNICAL.md). For the next bounded work, read
[`ROADMAP.md`](ROADMAP.md).

## Original proof of concept

![Early map-based interface proof of concept](docs/images/sis-proof-of-concept.webp)

The image records the original product exploration. Its labels, confidence,
locations and events are demonstration output, not validated telemetry or
satellite identifications. No supported frontend is currently included.

## Legacy offline prototype

The original SDR-to-disk and satellite-candidate code remains available through
`gray_system_main.py`. It is exploratory and is not the validated output of
the live-instrument gates. In particular:

- encryption and secure export are not implemented;
- metadata-scrubbed captures are incompatible with the current reader;
- Doppler proximity is candidate ranking, not identification;
- old API, Redis, PostgreSQL and frontend documents are historical.

## Legal and ethical use

Use this repository only for lawful education, amateur-radio experimentation,
spectrum research and signals you are authorized to receive and process. It
does not transmit, jam, decrypt or bypass access controls. Public receiver
availability is not a blanket license to record or redistribute content.
Operators are responsible for applicable radio, privacy and data-retention law.

## License

Apache License 2.0. See [`LICENSE`](LICENSE).
