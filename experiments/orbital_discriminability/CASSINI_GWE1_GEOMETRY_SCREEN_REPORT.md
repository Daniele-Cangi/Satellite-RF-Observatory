# Cassini GWE1 single-station geometry-route screen

Outcome: **`CASSINI_GWE1_GEOMETRY_ROUTE_POSITIVE`**

This is a metadata-only physical route screen. No RSR header, RSR payload,
path-delay table, IQ, amplitude, signal diagnostic or detector input was read.
It does not admit an experiment.

## Block review

**BLOCK.** The pre-transition SAGR3 DSS-25/DSS-65 geometry was real, but the
held-out 72.3 mHz separation could not be compared with a defensible temporal
troposphere uncertainty for DSS-65. The term remained `UNRESOLVED`, not zero.

**INFORMATION VALUE.** A complete metadata scan of the bounded SAGR RSR
collection found no second cross-complex simultaneous SAGR topology. Repairing
the same distributed path would therefore require the missing DSS-65 physical
witness rather than more geometry code.

**CHANGE OF ABSTRACTION.** GWE1 offers a narrower claim with a better nuisance
topology: one DSS-25 receive root, three simultaneous coherent links (X/X,
X/Ka and Ka/Ka), and two boresighted Advanced Water Vapor Radiometer products.
It gives up distributed confirmation but may observe both dispersive plasma
and same-path troposphere instead of bounding them only from generic models.

## Physical question

Does a pre-pass Cassini trajectory preserve nonlinear two-way link structure
in an independent suffix better than both:

1. a constant-plus-linear frequency continuation fitted only on the prefix;
2. a geometry-destroying spacecraft that continues inertially from the
   position and velocity at the end of that prefix?

The second null retains the same DSS-25 motion, two-way light-time solver and
prefix-only affine nuisance. It removes Cassini orbital acceleration and is
the controlling comparison.

## Bounded products and candidate roles

The common interval for each day is the label-level intersection of all three
RSR products and both AWVR products. These are candidate roles, not a frozen
prospective plan.

| Candidate role | Date / common UTC | Simultaneous RSR products | Same-path products |
|---|---|---|---|
| development | 2001-11-27 04:40:03–15:13:48 | `c29eagw2001_331_0434x25x25rd`, `...0435x25k25rd`, `...0440k25k25rd` | AWVR1/2 `c29eagw2001_331_0250_151525` |
| reserve | 2001-12-08 03:52:58–14:34:00 | `c29eagw2001_342_0346x25x25rd`, `...0346x25k25rd`, `...0352k25k25rd` | AWVR1/2 `c29eagw2001_342_0155_143525` |
| primary | 2001-12-13 03:24:50–14:04:00 | `c29eagw2001_347_0321x25x25rd`, `...0321x25k25rd`, `...0324k25k25rd` | AWVR1/2 `c29eagw2001_347_0135_140525` |

All label hashes, published payload MD5 values, byte counts, record counts and
coverage are bound by the screen manifest. The AWVR labels identify distinct
AWVR1 and AWVR2 tables, but their values, flags, continuity and residual
uncertainty have not been inspected. They are not counted as independent
orbital measurement roots.

## Independent trajectory

The exact-hash trajectory is
`010222A_SK_JP054_JP458.bsp` (SHA-256
`63c10d2ca02fae980a7932bac0e8b6e1731ba1eaa8c86fd58738cfe31d5a020d`).
Its official label says:

- creation: 2001-02-22 15:14:02;
- propagated arc through 2002-04-02;
- reconstructed arc: N/A;
- based on OD solution JP30D.

It therefore predates all three November/December GWE1 sessions and cannot
have assimilated their target RF outcome. The planetary, station,
Earth-orientation and time kernels are exact-hash inputs recorded in the
receipt.

## Frozen screen

For each RSR receive epoch the metadata-only central value is:

```text
DSS-25 uplink station state
  -> solve uplink light time
  -> Cassini PREDICT state at coherent turnaround
  -> solve downlink light time
  -> DSS-25 receive station state
  -> special-relativistic two-way kinematic factor
```

The grid cadence is 10 s and the first 20% is the calibration prefix. No
suffix parameter is fitted. The nominal 8.4 GHz and 32 GHz multipliers below
are screening coordinates only: exact ramps, turnaround ratios, header
polynomials and RSR NCO transforms have not been applied.

| Role | Visibility | Ka orbital vs affine p-p | Ka orbital vs rectilinear p-p | Ka rectilinear RMS | X orbital vs rectilinear p-p |
|---|---:|---:|---:|---:|---:|
| development | 11.36°–77.58° | 55,765.77 Hz | 0.1722106 Hz | 0.0822241 Hz | 0.0452053 Hz |
| reserve | 9.51°–77.53° | 53,841.79 Hz | 0.2113485 Hz | 0.1009236 Hz | 0.0554790 Hz |
| primary | 10.93°–77.51° | 57,467.77 Hz | **0.2284093 Hz** | 0.1090529 Hz | 0.0599574 Hz |

The large affine separation is not the controlling claim: station/link
curvature makes that null easy to reject. The rectilinear-spacecraft
alternative is the relevant geometry discriminator.

For the primary candidate, the Ka result at 20 s, 10 s and 5 s grid cadence is
0.2286601, 0.2284093 and 0.2283833 Hz respectively. The 10 s screen is stable
to this numerical refinement; this says nothing yet about measurement
resolution.

## Why the route is only positive, not admitted

The screen proves that a useful orbital-versus-null coordinate exists before
RF inspection. It does not prove that the archive preserves it. In particular:

- the exact station ramp, coherent turnaround ratios and three real RSR NCO
  transforms are not compiled;
- RSR sequence/time continuity and simultaneous receiver configuration are
  not qualified;
- the AWVR tables have not been read, so same-path coverage, quality flags and
  residual temporal uncertainty are unknown;
- separate X/Ka receiver hardware can create non-common instrumental terms;
- no detector resolution can be derived until the recorded-baseband curves
  and the remaining physical envelope exist.

The maximum future claim, if all of those clauses pass, is:

```text
single-station two-way orbital model predictively preferred to frozen nulls
```

It is not distributed confirmation and not Cassini identity evidence.

## Exact next physical blocker

Before any IQ access, one bounded metadata/header step would have to establish:

1. continuous, simultaneous X/X, X/Ka and Ka/Ka header coordinates;
2. exact uplink ramps, turnaround ratios and reversible NCO/baseband transforms;
3. AWVR1/AWVR2 continuity, flags and an outcome-independent temporal
   uncertainty family;
4. a finite band-specific receiver-hardware differential envelope;
5. the same recorded-baseband transform for the orbital model and every null.

If any item cannot be established, the correct outcome is to close GWE1
without detector or IQ access.

## SHOCK

The second geographic hardware root was essential for the SAGR3 distributed
claim, but it also introduced the exact nuisance that blocked it. For the
narrower orbital-versus-null question, one station with same-path atmospheric
and multi-frequency witnesses can be more falsifiable than two geographically
independent stations with an unobserved differential atmosphere.

The unexpected cost is common-mode ambiguity: the shared antenna, station
clock and parts of the receiver/control chain can make three link tracks agree
for instrumental reasons. Triple-link agreement therefore closes plasma; it
does not create three independent orbital roots. That is why the claim scope
must remain single-station and why exact per-band receiver lineage is still a
blocking clause.

## Sources

- [Cassini RSS PDS4 bundle index](https://atmos.nmsu.edu/data_and_services/atmospheres_data/Cassini/inst-rss_curr.html)
- [Cassini Radio Science User's Guide](https://pds.nasa.gov/data/pds4/misc/document_cassini/Cassini_Radio_Science_Users_Guide_30Sep2018.pdf)
- [GWE PDS4 bundle](https://atmos.nmsu.edu/PDS/data/PDS4/cassini-rss-raw-gwe/)
- [GWE RSR collection](https://atmos.nmsu.edu/PDS/data/PDS4/cassini-rss-raw-gwe/data-rsr01/)
- [GWE AWVR1 path-delay collection](https://atmos.nmsu.edu/PDS/data/PDS4/cassini-rss-raw-gwe/data-pd1/)
- [GWE AWVR2 path-delay collection](https://atmos.nmsu.edu/PDS/data/PDS4/cassini-rss-raw-gwe/data-pd2/)
- [Cassini PREDICT SPK directory](https://naif.jpl.nasa.gov/pub/naif/CASSINI/kernels/spk/)
- [JPL Advanced Media Calibration System](https://ntrs.nasa.gov/citations/20000074258)

The temporary labels and kernels used for verification were destroyed after
hashing. No RF or path-delay measurement table was persisted.
