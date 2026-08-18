# Gate F2.5.31 — open-handle injected successor

Gate F2.5.31 repairs the channel-lifetime defect found by F2.5.30. It remains
exclusively offline: both SND sockets and every incoming frame are injected,
and the module contains no connector or public execution surface.

The terminal positive synthetic result is:

`OPEN_HANDLE_BOUNDARIES_WITNESSED_OFFLINE`

This result demonstrates lifecycle and control integration. It is not a live
RF or physical DDC-location outcome.

## Frozen plan

The successor binds:

- the F2.5.30 commit and source hash;
- the F2.5.30 audit-envelope hash;
- the F2.5.27 relative-time plan;
- the endpoint and bootstrap coordinate already present in the reviewed
  lineage;
- eight retained analysis frames per A1, B and A2 phase;
- the existing 0.8-second settling interval;
- the existing 750 Hz technical diagnostic delta;
- the unchanged `MotherPlan` contrast, half-stability and fingerprint
  correlation thresholds;
- zero retry, zero RF persistence and no public runtime overrides.

The bootstrap coordinate and technical delta are control geometry, not a
target identity or evidence that a feature is physically external.

## Corrected ownership

One outer owner now controls both branches:

```text
open and configure reference + perturbed
        ↓
collect simultaneous A1
        ↓
relative-time admission
        ↓
local one-feature discovery while both handles are open
        ↓
private perturbed-only executor sends A1→B
        ↓
consume settling frames + collect B on both branches
        ↓
evaluate scalar A1→B boundary
        ↓
private perturbed-only executor sends B→A2
        ↓
consume settling frames + collect A2 on both branches
        ↓
evaluate scalar B→A2 boundary + full-session continuity
        ↓
outer finally: zeroize IQ and close both handles
```

Unlike F2.5.29, no branch collector owns socket closure. Discovery and both
commands occur while the exact two admitted handles are still open.

## Internal discovery

Discovery is local and temporary. It concatenates only the A1 IQ already in
RAM, applies the existing 1024-point STFT geometry and robust spectral
baseline, then requires the unchanged:

- minimum joint contrast;
- minimum contrast in both time halves;
- cross-branch normalized-neighbourhood correlation.

The retained receipt contains only artifact hashes and finite feature scalars.
No spectrum, STFT or IQ survives. If no feature passes, the outcome is
`NO_FALSIFIABLE_INTERVENTION`; no retune command is emitted.

## Private retune executor

The runner signature accepts only two injected sockets. Endpoint, center,
delta, settling time, thresholds, callbacks and authority are not parameters.

The internal executor:

- holds both private handles;
- refuses commands after either handle closes;
- sends tuning commands only to the perturbed branch;
- records zero retune commands on the fixed reference branch;
- emits a scalar command receipt with issue and settling times;
- cannot escape through the result or public API.

The commands remain local-send witnesses. Gate F2.5.31 does not invent a
remote command acknowledgement.

## Boundary and continuity semantics

Each command boundary is evaluated with the existing F2.5.27 scalar contract:

- last pre-command perturbed frame;
- first post-settling perturbed frame;
- reference frames bracketing the same interval;
- distinct stable channel IDs;
- local command order;
- advancing server sample time.

Frames arriving during settling are still decoded, hashed and included in the
full-session continuity ledger. They are excluded only from the B/A2 analysis
window. Thus a sequence gap cannot be hidden by a valid endpoint boundary.

The positive result requires both boundary receipts plus zero sequence and
sample-clock step violations across every consumed frame on both branches.

## Outcome semantics

`CAPABILITY_REJECTED`
: An injected transcript contains an explicit `badp` or `too_busy` refusal.

`TOPOLOGY_NOT_ADMITTED`
: Two handles opened but did not preserve distinct same-rate channels.

`TEMPORAL_NOT_ADMITTED`
: Initial A1 scalar receipts fail the relative-time contract.

`NO_FALSIFIABLE_INTERVENTION`
: Timing passes, but unchanged discovery thresholds admit no common A1
  feature. No command is sent.

`INTERVENTION_INVALID`
: A boundary or full-session continuity fails. This does not support either
  physical hypothesis.

`QUALIFICATION_ERROR`
: An injected transport or transform error prevented evaluation.

`OPEN_HANDLE_BOUNDARIES_WITNESSED_OFFLINE`
: Synthetic handles remained open, one feature was admitted, only the
  perturbed branch received A1→B→A2, both scalar boundaries passed and session
  continuity remained intact.

Plan freeze and confirmation remain `NOT_EVALUATED` in every path.

## Cleanup

Every taken transport-frame lease is released before parsing. Raw SND copies
are cleared immediately after decode. All decoded arrays, including settling
frames, are overwritten in the outer `finally`; both sockets are then closed.
The returned value is strict finite JSON containing only scalar/hash receipts.

## Authorized claims

Gate F2.5.31 authorizes the claims that the F2.5.30 lifetime defect has an
offline successor, the two exact handles can span discovery and both command
boundaries, the fixed branch receives no retune command, and cleanup occurs at
the correct outer boundary.

It does not authorize claims that:

- a live Kiwi accepted either command;
- a physical RF feature translated or remained fixed;
- the feature lies upstream or downstream of the per-channel DDC;
- plan freeze or a prospective confirmation occurred.

## SHOCK

Keeping the sockets open is necessary but not sufficient. A valid
intervention has two different witnesses: command/time topology and RF
structure. Gate F2.5.31 now closes the first cut without pretending that it
also closes the second.

The next admissible work is offline integration of the existing distributed,
target-excluded RF witness over the A1/B/A2 arrays owned by this same outer
scope. It must keep thresholds unchanged and preserve the distinction between
`INTERVENTION_INVALID`, `NOT_DETECTABLE` and an actual hypothesis result. Only
after that integration and a separate post-commit audit may a live authority
surface be considered.
