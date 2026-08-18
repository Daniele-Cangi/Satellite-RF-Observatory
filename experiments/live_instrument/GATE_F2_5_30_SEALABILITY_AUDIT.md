# Gate F2.5.30 — post-commit sealability audit

Gate F2.5.30 is an exclusively offline post-commit audit of F2.5.29. Its
terminal result is:

`LIVE_SURFACE_NOT_SEALABLE`

This is not a source-seal failure. Commit, source, envelope and integration
surface all match exactly. The failure concerns the lifetime of the two branch
control handles required by the intended A1→B→A2 experiment.

No network connection, acquisition, receipt file or public execution surface
was created.

## Frozen lineage

The audit binds:

- F2.5.29 commit `c59a2f9bb6a6b72ea34d42dee936184bef5358fe`;
- canonical F2.5.29 source SHA-256
  `2defe3b394bc10ee2b238e4dc20022d1af697884785cfb39c156695c9c79bc22`;
- F2.5.29 envelope hash
  `da82ce3fa6f0608d8cc1bddce02cf4928f09795cd159ca8d421f5792a848b50d`;
- F2.5.29 integration surface hash
  `8421c14c66d965451d63ecb78b6e3b513a7884a3ac609ec4809984dbc7cb940d`;
- F2.5.30 audit surface hash
  `d7739727eddd2ae1f6bd35237bbbd085b26c50205771e0140fbb7c273dd47832`;
- F2.5.30 audit envelope hash
  `1f2fc9e84aa582d11aa841efba7400942a9305f6135025a25f086b7c9fea5e15`.

The expected outcome is valid only when those seals match. A lineage mismatch
instead produces `POST_COMMIT_SEAL_MISMATCH`.

## The causal lifetime mismatch

F2.5.29 performs the following order:

```text
reference collector ─┐
                     ├─ both collectors return ─ sockets already closed
perturbed collector ─┘                         ↓
                                      relative-time gate
                                               ↓
                                           discovery
                                               ↓
                                            retune
```

Each collector closes its socket in its own `finally`. The outer wrapper waits
for both futures to return before calling F2.5.28. Consequently, the discovery
and retune callbacks receive only an ephemeral read-only IQ view after both
control paths have ended.

This is sufficient to test:

- exact auth/metadata/setup ordering;
- simultaneous initial dual-SND collection;
- artifact ownership and destruction;
- relative sample-time admission;
- downstream callback gating with injected boundary receipts.

It is insufficient to execute or witness:

- an actual A1→B command on the perturbed live channel;
- the corresponding fixed-reference witness;
- an actual B→A2 command;
- continuity of the same two channel roots through discovery and retune.

The callback cannot repair the problem: its argument is an
`_EphemeralDualIQView`, with no socket, connection, send operation or command
ledger. Adding a caller-supplied connection would also violate the reviewed
no-override boundary.

## Clause results

`post_commit_lineage_exact`
: `SATISFIED`.

`relative_dual_snd_boundary_reusable`
: `SATISFIED`. The temporal and ownership work is retained.

`channels_open_through_discovery`
: `UNSATISFIED`.

`channels_open_through_a1_b_a2`
: `UNSATISFIED`.

`retune_callback_has_control_handle`
: `UNSATISFIED`.

`public_authority_surface_sealable`
: `NOT_EVALUATED`. A nominal authority bit is deliberately not created.

## Dynamic proof

The test suite supplies two complete injected transcripts and records socket
state inside both callbacks. The observed sequence is exactly:

```text
discovery: reference closed, perturbed closed
retune:    reference closed, perturbed closed
```

The nested synthetic result is `INTERVENTION_NOT_QUALIFIED`, and the physical
hypothesis remains `NOT_EVALUATED`. This prevents a source-inspection mistake
from becoming the only basis of the finding.

## Minimum successor change

A successor should change only the ownership boundary:

1. initial dual-SND admission returns two owned branch control handles;
2. an outer one-shot owner keeps them open through discovery;
3. only an internal frozen command executor may retune the perturbed branch;
4. both A1→B and B→A2 receive samples and command-boundary receipts from the
   same open channel roots;
5. both handles, transient bytes and IQ arrays are closed or zeroized in one
   outer `finally` after the terminal outcome;
6. only then may a post-commit module expose
   `run_reviewed_once(live_authorised=False)`.

Endpoint, frequency, timing, thresholds, callbacks and receipt path must still
have no public override. Retry remains zero.

## Authorized claims

The audit authorizes the claims that F2.5.29 is exact, its relative-time gate
is reusable, and its current channel lifetime cannot support a live retune.

It does not authorize claims that the endpoint is reachable, the receiver
lacks the capability, any RF feature is present or absent, or either physical
DDC-location hypothesis has been evaluated.

## SHOCK

The missing primitive is not another sensor or a broader contract. It is
ownership of a causal path across time. A pair of valid measurements is not an
experimental instrument if the control handles that define the intervention
have already disappeared.

F2.5.29 therefore remains valuable as an injected admission boundary, but it
must not be promoted unchanged into the live runtime.
