# Blind-orbit assignment primary outcome

## Terminal state

```text
BOUNDED_TRUE_ORBIT_PREFERRED
```

The sole authorized AMC DOY226 primary execution is consumed. The result is a
bounded preference within the six predeclared hypotheses; it is not
unconstrained orbit recovery or independent transmitter identity.

## One-shot integrity

The authority marker was written before any network request. The executor then
materialized exactly
`AMC400USA_R_20262260000_01D_30S_MO.crx.gz` in one attempt, computed the
complete-file hashes before decompression or record decoding, admitted the
measurement, wrote and hashed the opaque score receipt, and only then revealed
the identifier mapping.

| Item | Frozen result |
| --- | --- |
| executor seal SHA-256 | `2d385f73a0e6a5a8038fe875262b10022f95c04b4e9116f3ab0ecc87b95cd1be` |
| complete artifact bytes | `3,456,560` |
| complete artifact SHA-256 | `19f5969959cd9a33ed7e811ff9e92ea4d34c2e36a9d51c2f1ebebbbc1596ec4f` |
| complete artifact MD5 | `68b45ded1cc3fc6e3fa1baea5ad05f8b` |
| opaque score receipt SHA-256 | `9614f9cfafaa817e492150d33aee9c262e08f90e9fe967b7ffc63cd9eda40f8a` |
| primary outcome receipt SHA-256 | `24eee7aa5990e3632b7d9bc44d6337a7fa2be0b91e75af1dada658d950a3cd74` |
| transport attempts | `1` |
| retry after complete hash or decode | `false` |
| persisted compressed/decoded observations | `0 / 0` |
| persisted observation values | `0` |

The directory response exposed `md5 = "1"`, not a usable 32-hex checksum.
That descriptive field is retained but is not presented as checksum
verification. Complete-file SHA-256 and MD5 were computed locally before
decode; the prospective identity remained the frozen directory and logical
product name.

## Measurement admission

All 139 frozen epochs were present. The L1C/L2W phase fields and LLI clauses
passed with zero blank or trailing-omitted retained fields. Event-time
deviation was `0.0 s` against the frozen `15.0 s` limit. The maximum absolute
geometry-free second differences were `0.002166 m` for G22 and `0.004332 m`
for G30, both below `0.095147 m`. Same-path code/phase variation was
`4.116730 m` and `4.983165 m`, below the frozen `1,250 m` bound.

## Opaque held-out comparison

Before reveal, the scorer received one unlabelled 139-point coordinate and the
six opaque frozen trajectories. It fit the same prefix constant and rate to
every hypothesis and performed no held-out refit or free time-phase fit.

| Quantity | Result |
| --- | ---: |
| best opaque hypothesis | `H_72E7F21DC8244653` |
| best held-out peak-to-peak residual | `6.104475 m` |
| best held-out RMS residual | `3.503826 m` |
| runner-up opaque hypothesis | `H_0F7B423DEE4445EB` |
| runner-up held-out peak-to-peak residual | `18,768.100639 m` |
| opaque preference margin | `18,761.996164 m` |
| frozen pairwise guard | `7,339.701235 m` |

Only after the opaque receipt hash was persisted did the mapping reveal
`H_72E7F21DC8244653` as the predeclared `G22_RELATIVE_TO_G30` orbital
candidate. The terminal claim is therefore:

```text
BOUNDED_ORBIT_ASSIGNMENT_PREFERRED_WITHIN_FROZEN_CANDIDATE_SET
```

## Claim boundary and stop

This result supports a specific candidate within the frozen five-orbit plus
affine-null family for one AMC station and one held-out pass. It does not show
catalog-wide identity, targetless RF identification, independence from the
receiver's upstream PRN correlation, or full orbit reconstruction. The
primary is consumed: no retry, rescore, alternate product, changed candidate
set or changed null is authorized.

No automatic successor experiment follows. The next scientific review may
ask whether the bounded blind preference should be tested on a genuinely
independent observer or measurement root, but it must select that route from
physical information gain rather than reopen traditional station inventory.
