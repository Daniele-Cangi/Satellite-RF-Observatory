# Bounded GNSS cross-receiver-family screen

## Outcome

```text
NO_CROSS_FAMILY_GEOMETRY_SHORTLISTED
```

The exact blocker is:

```text
NO_NON_REJECTED_CROSS_FAMILY_ROOT_HAS_COMPLETE_139_EPOCH_JOINT_VISIBILITY
```

This is a metadata/orbit-only terminal result. It does not select a
qualification artifact or primary, does not freeze a prospective plan and
authorizes no observation access or orbital measurement.

## Physical question

Does the frozen G22-minus-G30 orbital-versus-null distinction survive at one
observer whose receiver family is different from the consumed Septentrio
POLARX5 paths?

## New information produced

The final bounded traditional-GNSS replication route fails before observation
access. The three non-rejected cross-family roots do not supply the complete
139-epoch joint visibility required by the already frozen coordinate, null
families and direct event-time envelope on DOY221--223.

The existing experiment could not answer this because AMC and PIE exercised
Septentrio receiver paths, while WES had already been refused for ambiguous
RINEX 2 signal-product semantics. This screen tests only whether a distinct
receiver family offers an admissible geometry before any new product is opened.

## Frozen bounded metadata set

The set was declared before any observation-product access and contains exactly
five hardware roots. Full official IGS site logs were read as metadata, hashed
and not treated as evidence that an observation product contains the required
signals.

| Root | Receiver family | Current receiver | Clock declaration | Site-log SHA-256 | Metadata disposition |
|---|---|---|---|---|---|
| WES200USA | Trimble Alloy | 6026R40020 / 6.50 | external H-maser, 10 MHz | `3afc9bfe...f2115d76` | prior signal-product refusal preserved |
| WTZR00DEU | Leica GR50 | 1831551 / 4.50/7.710 | external H-maser EFOS 18, 5 MHz | `56e0fcfc...3565ca7` | metadata admitted, geometry only |
| ZIMM00CHE | Leica GR50 | 1873172 / 4.90/7.905 | internal | `d016f9dc...553080f` | metadata admitted, geometry only |
| TSKB00JPN | Trimble Alloy | 6032R40037 / 6.15 | external cesium, 10 MHz | `0aefc240...92781e` | metadata admitted, geometry only |
| HOB200AUS | Septentrio POLARX5 | 3012296 / 5.7.0 | external H-maser, 10 MHz | `bc5d67bc...496760` | rejected: does not test cross-family transfer |

Authorities:

- [WES200USA official IGS site log](https://network.igs.org/api/public/download/WES200USA.log?lower_case=1)
- [WTZR00DEU official IGS site log](https://network.igs.org/api/public/download/WTZR00DEU.log?lower_case=1)
- [ZIMM00CHE official IGS site log](https://network.igs.org/api/public/download/ZIMM00CHE.log?lower_case=1)
- [TSKB00JPN official IGS site log](https://network.igs.org/api/public/download/TSKB00JPN.log?lower_case=1)
- [HOB200AUS official IGS site log](https://network.igs.org/api/public/download/HOB200AUS.log?lower_case=1)

No global station inventory was built. GOLD, NLIB, ALGO and MDO were excluded
before the screen because their paths were already consumed. HOB2 was retained
as a typed bounded-set refusal and not silently replaced by a sixth candidate.

## Frozen orbital comparison

The compiler re-materialized only the three already hash-frozen NOAA broadcast
navigation products for DOY221--223, verified their byte counts and SHA-256
values, evaluated them in RAM and destroyed them. It inherited without change:

- target G22 and reference G30;
- wrong-orbit nulls G01, G14 and G17;
- the prediction-only frozen affine null;
- 139 epochs at 30 s cadence;
- 79 prefix epochs and 60 held-out epochs;
- 15 degree visibility for every model satellite on nominal and direct
  `t +/- 15 s` trajectory grids;
- the same troposphere, quantization, hardware and event-time envelope.

No observation locator, product, header, decoder or value is accepted by the
screen.

## Root-by-root failure topology

| Root | Maximum jointly visible epochs | Required consecutive epochs | Geometry result | Admission result |
|---|---:|---:|---|---|
| WES200USA | 337 | 139 | positive | rejected signal-product semantics remains controlling |
| WTZR00DEU | 0 | 139 | no admissible window | no observation query authorized |
| ZIMM00CHE | 0 | 139 | no admissible window | no observation query authorized |
| TSKB00JPN | 113 | 139 | partial visibility only; no gap bridging or shortening | no observation query authorized |
| HOB200AUS | not evaluated | 139 | not evaluated | rejected receiver family |

WTZR and ZIMM never have all five target/reference/null satellites above the
frozen elevation threshold together on the direct time-shift grids. TSKB comes
closest, but its maximum of 113 jointly visible epochs is 26 epochs short of
the immutable 139-epoch window. The screen does not shorten the window, remove
a null or lower the elevation rule to make a candidate pass.

## Preserved WES control result

WES remains strongly geometry-positive on DOY223:

| Window GPS | Held-out start GPS | Controlling null | Separation m p-p | Pairwise envelope m | Margin m | Minimum shifted elevation deg |
|---|---|---|---:|---:|---:|---:|
| 05:29:00--06:38:00 | 06:08:30 | wrong orbit G17 | 161,836.830 | 1,674.939 | 160,161.891 | 33.330 |

This is a control on the geometry computation, not a capability admission.
The prior typed refusal remains authoritative: the known RINEX 2 feed does not
establish explicit `L1C/L2W` identity. Metadata about a Trimble receiver cannot
repair that missing product-level distinction.

## Interpretation and stop

The negative result is not evidence that cross-family observer transfer is
physically impossible. It says that this predeclared set, these three frozen
dates and the existing G22/G30/null contract do not jointly yield an admissible
new root.

The minimum experiment therefore terminates before qualification discovery.
There is no justification to:

- search a sixth station;
- query observation locators until one passes;
- weaken the 139-epoch window;
- remove a geometry-destroying null;
- reopen WES under an implicit signal mapping;
- reuse HOB2 as though another POLARX5 were a receiver-family replication.

The next maximum action is:

```text
STOP_TRADITIONAL_GNSS_REPLICATION
```

Per the frozen post-AMC review, any subsequent physical vertical should change
the information mechanism: blind satellite assignment or a raw-RF receiver
path, not another bounded station search disguised as continuation.

## Frozen receipt

`GNSS_CROSS_FAMILY_BOUNDED_SCREEN_RECEIPT.json` is `48,183` bytes with SHA-256
`59125fedbe1afbfa40255681f82d575a516589ca0f7d40186f601a23495e88f0`.
It binds source commit
`f67e0d7e9c74a97eb4cbc211871d60140087a40a`, source SHA-256
`77c2db54fa199101185c5eaefe1599e2d35fd196b827ce48a2a5ba942e6da7ed`
and manifest SHA-256
`14c2ef01dc382dab6aaed4b3d60c2b24b549bd59cd68859708e7767d7595e0bd`.

All observation-access counters are zero.
