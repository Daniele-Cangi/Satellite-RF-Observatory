# GNSS all-track qualification retry outcome

## Terminal

```text
GNSS_ALL_TRACK_STRUCTURAL_QUALIFICATION_FAILED
```

The single authorized ALGO DOY229 parser-repair retry is consumed. The result
is a valid structural refusal, not a transport or description error.

## Artifact and execution integrity

| Property | Observed |
|---|---|
| product | `ALGO00CAN_R_20262290000_01D_30S_MO.crx.gz` |
| materialization attempts | 1 |
| complete bytes | 4,317,738 |
| complete SHA-256 | `88aa876b787cac583345d512b2f705ec19062a5f71c38c3a4ae0da45f8095f24` |
| identity checked before decompression | yes |
| execution commit | `c7ee1731f18243d3006b8054e8a1a90c87c1a755` |
| observation values parsed/persisted | 0 / 0 |
| compressed/decompressed artifact bytes persisted | 0 / 0 |

The previously frozen `QUALIFICATION_DESCRIPTION_ERROR /
ANTENNA_TYPE_CHANGED` receipt retains canonical SHA-256
`57f863b7047d8efe96e54111186cebb5d338a4d580045ef5a37b1847c5bf675b`.
The retry used four distinct output names and did not rewrite that history.

## Clause result

| Clause | State | Evidence |
|---|---|---|
| header description | `SATISFIED` | repaired RINEX 2A20 antenna description admitted |
| complete grid | `SATISFIED` | all 139 frozen 30 s epochs present |
| exactly six complete tracks | `UNSATISFIED` | 7 complete tracks among 11 tracks seen |
| same-path code | `DESCRIPTIVE_NOT_ADMISSION_CLAUSE` | retained without changing membership |
| measurement admission | `NOT_EVALUATED` | outside structural qualification |
| orbital score | `NOT_EVALUATED` | forbidden after structural refusal |
| primary selection | `NOT_EVALUATED` | no primary was selected |

There were no parser issues. The 6,116 structural coverage rows contain 4,690
`PRESENT`, 138 `BLANK` and 1,288 `FIELD_ABSENT` states and no observation
scalar.

## Opaque decision before reveal

The complete opaque tracks were:

```text
T001 T003 T004 T005 T006 T007 T009
```

That count of seven, by itself, failed the predeclared exactly-six clause. The
receipt was hashed before PRN reveal. No orbit code or receiver label selected
membership.

## Non-independent reveal

Only after the structural decision, the receiver labels revealed:

| Opaque track | Receiver PRN | Complete |
|---|---|---|
| T001 | G05 | yes |
| T002 | G07 | no |
| T003 | G11 | yes |
| T004 | G15 | yes |
| T005 | G18 | yes |
| T006 | G20 | yes |
| T007 | G21 | yes |
| T008 | G25 | no |
| T009 | G29 | yes |
| T010 | G30 | no |
| T011 | G23 | no |

The frozen orbit codebook was G05/G15/G18/G20/G21/G29. All six are complete,
but G11 is also complete. Therefore the reveal is `DISCORDANT`; it cannot
remove G11 or rescue qualification.

## Interpretation

This result does **not** falsify the candidate orbital geometry. No observation
magnitude was read and no orbital model was scored.

It does falsify the admissibility of this exact measurement formulation on
this artifact:

```text
all structurally complete GPS tracks
→ exactly six tracks
→ six-orbit bijection scorer
```

The failure is informative because the receiver delivered the full predicted
six-track family plus one indistinguishable complete track. Removing G11 after
reveal would turn the supposedly blind experiment into codebook-conditioned
selection and is forbidden.

## Change-of-abstraction review

Do not retry ALGO DOY229, search another date to obtain a convenient count, or
weaken the exactly-six clause. The consumed qualification path is closed.

The smallest scientifically meaningful alternative is offline and changes the
measurement model rather than the evidence: ask whether a predeclared
assignment can identify a six-orbit injection inside an `N >= 6` all-track set
while treating extra complete tracks as explicit clutter and giving the nulls
the same combinatorial freedom. That mechanism must be shown discriminative
synthetically before any new product or primary is selected. It is not
authorized or implemented by this outcome.

## Frozen receipt hashes

| Receipt | SHA-256 |
|---|---|
| retry outcome | `233e34084c0ffe86749919dd3f9b73ff243f9a51f530749328a7456dc7ad828e` |
| structure | `9eec2cbfc934c52b3ae592ff5570c83e82871d0f9ec87f29cb75bd5147b571cc` |
| reveal | `d071d9f75147d4247943d9f12d859f63a239b83e74ba2d7238becdc062493d00` |
| coverage JSON Lines | `abf28fdc011a8e37844914b4ba660994c184457119031efe5b8b02d21a67b791` |

## Stop

No new artifact, window, primary, score or geometry search is authorized.
