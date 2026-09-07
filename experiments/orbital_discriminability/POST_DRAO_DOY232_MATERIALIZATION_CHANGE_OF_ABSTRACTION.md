# DRAO DOY232 materialization change-of-abstraction

## Decision

The historical result remains immutable:

```text
QUALIFICATION_DESCRIPTION_ERROR
physical decision = NOT_EVALUATED
```

The complete compressed response was downloaded and hashed, but the process
lost the digest and actual byte count while constructing its descriptive
receipt. The cause was an invalid assumption that the GET response always
contains `Content-Length`. No decompression, RINEX header, observation value or
DOY233 primary access occurred.

This repair does not create a gate and changes no orbit, station, date, signal,
window, threshold, witness, margin or outcome rule.

## Information-value review

```text
BLOCK:
The descriptive receipt depended on nullable GET transport metadata after the
artifact's authoritative byte count and digest had already been computed.

INFORMATION VALUE:
The failed attempt produced no physical information. Its only useful result is
identification of an avoidable receipt-construction defect.

CURRENT ABSTRACTION:
The frozen contract treated completion of a content-blind hash as if it were
the beginning of a scientific trial. That boundary is too early. Hashing does
not inspect the measurement and cannot select or adapt a physical outcome.

ALTERNATIVES:
A. Close DRAO: rejects a positive model-side margin for a descriptive bug.
B. Trust HEAD metadata: cannot establish content integrity.
C. Replay the exact artifact once, content-blind, and preserve its digest in a
   two-phase receipt before cleanup: selected.
D. Change archive, station or date: would change the frozen experiment.

BEST PHYSICAL PATH:
One exact-artifact receipt replay, followed only after separate review by the
already frozen model-blind qualification.

ACTION:
Freeze this narrow authority and a deterministic DRAO-specific materializer.
Do not execute the replay in the same change.
```

## Correct irreversibility boundary

A `RECEIPT_REPLAY` is an operational, content-blind reconstruction of artifact
identity. It is not a scientific retry. Scientific irreversibility begins when
the compressed artifact is first decompressed or any RINEX header or
observation value is exposed to the qualification process. From that point,
the frozen zero-retry rule applies to the qualification outcome.

The replay is limited to one transport attempt against the exact frozen URL.
There is no fallback, date/station change or response-driven adaptation. A
missing GET `Content-Length` is recorded as `ABSENT`; it is not an error. If the
field is present it must equal the frozen descriptive length. The streamed byte
count is authoritative and must equal `2,904,457` bytes.

## Two-phase receipt invariant

Before the payload can be destroyed, an atomic `PREPARED` receipt must contain
the full-file SHA-256 and actual byte count. Cleanup then unlinks only the exact
frozen filename. A second atomic write records the final cleanup state. If the
process fails between those writes, the conservative `PREPARED` receipt keeps
the integrity evidence and reports cleanup as pending; it never regresses to a
receipt without the digest.

No network replay, decompression, RINEX parsing or observation access was
performed while freezing this repair.
