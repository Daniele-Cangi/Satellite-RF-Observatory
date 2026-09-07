# DRAO DOY232 qualification outcome audit

**DRAO_DOY232_IDENTITY_CLAUSE_UNRESOLVED_BY_RECEIPT**

The one authorized DOY232 execution is consumed and will not be retried. Its
historical runtime record remains byte-for-byte unchanged:

```text
QUALIFICATION_TOPOLOGY_REJECTED
MARKER_NAME_MISMATCH
```

That record does not, however, support the stronger persisted
`MEASUREMENT_PATH_REJECTED` claim. The failure occurred before any observation
field was parsed, and the receipt omitted the observed marker, marker number
and header summary needed to distinguish a real station-identity mismatch from
a naming representation mismatch.

## Failure attribution

The contract bound the station identity as `DRAO00CAN / 40105M002`. The frozen
executor translated that relationship into the narrower predicate:

```text
normalize(MARKER NAME) == "DRAO"
```

It tested that predicate before checking or retaining `MARKER NUMBER`. The
runtime record therefore proves only that the parsed marker was not the exact
literal `DRAO`. It does not reveal the actual value and cannot establish
whether the header identified another station, used the nine-character IGS
site identifier, or used another legitimate representation. The possible
four-character/nine-character alias explanation is a hypothesis, not an
inferred cause.

This failure belongs to the bridge:

```text
station identity contract
-> header predicate
-> receipt representation
```

It is not evidence about phase continuity, same-path code, receiver health or
the orbital hypothesis.

## What the execution did establish

The sealed source can reach this marker check only after the exact compressed
byte count and SHA-256 have matched, the payload has been decoded ephemerally
in RAM and the RINEX header has been parsed. Therefore artifact identity was
satisfied as a control-flow invariant. The process then stopped during header
identity validation:

- observation fields parsed: `0`;
- structural coverage evaluated: `0`;
- phase/code witness evaluated: `0`;
- orbital model used: `false`;
- orbital scores produced: `0`;
- retained compressed or decoded artifact: `0`;
- DOY233 access: `0`.

The admissible physical interpretation is consequently `NOT_EVALUATED`, not
measurement-path rejection.

## Irreversibility and next boundary

DOY232 is now `CONSUMED_CLOSED_NO_RETRY`. The runtime outcome and authority
marker are preserved; neither is rewritten to make the experiment appear to
have succeeded. A code repair would not recreate the missing evidence and
does not authorize another access to the same artifact.

DOY233 remains unselected, unfrozen and unauthorized. No fallback date,
station or artifact is selected by this audit. The next step requires a
change-of-abstraction review: either construct a new independent
qualification/primary role pair whose identity receipt is sufficient before
access, or abandon this staged DRAO route in favor of a shorter physical path.
It must not be an automatic retry or another parser gate.

