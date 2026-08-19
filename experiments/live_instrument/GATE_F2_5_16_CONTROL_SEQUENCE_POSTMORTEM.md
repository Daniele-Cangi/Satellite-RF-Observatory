# Gate F2.5.16 — offline control-sequence attribution

## Scope and stop

This gate uses only two artifacts already committed before the audit:

- the single F2.5.15 JSONL outcome, SHA-256
  `ba77314fa10ea5ebc6fa3c29f9b4a9ebfdcf0b815d94fe77182a939b63e77619`;
- the retained KiwiSDR server-source subset at commit
  `c40ecb471dced33689e335689f8ffd35a54f47fa`, archive SHA-256
  `d6a50adfce7f75133020de85635711dc6c2218e6f134d901ac13a450b57de7ea`.

No endpoint was contacted, no new observation window was opened, and no RF
artifact was created or persisted. F2.5.15 remains frozen.

## The observed control sequence

Four branches ended in explicit `badp` rejection and did not reach channel
allocation. The other eight allocated a channel and locally sent `mod=iq`, but
recorded no semantic SND frame before an empty peer close.

The command hashes in the receipt bind local emission order. They reveal the
following sequence on every allocated branch:

| Endpoint | Role | Duration (s) | Keepalive before `AR OK` | Total keepalive | SND |
|---|---:|---:|---:|---:|---:|
| `dl1bajkiwisdr.ddns.net:8074` | reference | 0.752269 | 16 | 18 | 0 |
| `dl1bajkiwisdr.ddns.net:8074` | perturbed | 0.725921 | 15 | 18 | 0 |
| `hill.n8ga.org:8073` | reference | 1.513015 | 15 | 17 | 0 |
| `hill.n8ga.org:8073` | perturbed | 1.440316 | 15 | 18 | 0 |
| `kiwisdr2blair.ddns.net:8073` | perturbed | 1.467465 | 15 | 17 | 0 |
| `kiwisdr.kfsdr.com:8074` | reference | 1.551520 | 15 | 17 | 0 |
| `va6ok.ddns.net:8073` | reference | 1.845174 | 15 | 17 | 0 |
| `va6ok.ddns.net:8073` | perturbed | 1.851129 | 15 | 18 | 0 |

`AR OK` was locally emitted only at command index 23 or 24. The frozen client
sent one keepalive in its initial setup list and another after every inbound
control-frame iteration. That behavior was not paced by elapsed time.

## The pinned server mechanism

The retained source proves four facts about the pinned server revision:

1. each accepted `SET keepalive` increments `conn->keepalive_count`;
2. the sound loop contains a removal predicate when the count is greater than
   four while `s->cmd_recv != CMD_SND_ALL`;
3. audio is withheld while that setup mask is incomplete;
4. a valid `SET AR OK ...` sets the `CMD_AR_OK` setup bit.

The retained archive does not contain `rx/rx_sound_cmd.h`, so it does not bind
the exact definition of `CMD_SND_ALL`. It is therefore not legitimate to say
that `AR OK` was the only missing bit.

## Clause-by-clause attribution

| Clause | State | What the frozen evidence supports |
|---|---|---|
| Frozen receipt integrity | `SATISFIED` | Full artifact and pre-terminal prefix hashes match. |
| Direct SND branch attempts | `SATISFIED` | Twelve attempts, eight allocations and four explicit rejections are recorded. |
| Zero semantic SND after allocation | `SATISFIED` | All eight allocated branches contain zero SND frames. |
| Local command order reconstructable | `SATISFIED` | Ordered hashes distinguish keepalive and `AR OK` without credentials. |
| Pre-AR keepalive exceeds pinned guard | `SATISFIED` | Every allocated branch emitted 15 or 16 before `AR OK`; the pinned predicate uses greater than four. |
| Pinned incomplete-setup removal path | `SATISFIED` | The counter increment and predicate exist in the retained source. |
| Exact `CMD_SND_ALL` definition retained | `NOT_SATISFIED` | Its defining header is absent. |
| Remote server revision bound | `NOT_EVALUATED` | The receipt carries no authenticated remote build identity. |
| Remote receipt/order of commands | `NOT_EVALUATED` | Local send order is not a remote acknowledgement ledger. |
| Remote `cmd_recv` at close | `NOT_EVALUATED` | The internal bitmask was not observed. |
| Peer close reason | `NOT_EVALUATED` | Close bodies were empty and status codes absent. |
| Physical dual-SND capability | `NOT_EVALUATED` | No SND crossed the admission boundary. |

## Failure attribution

### Local control plan — `FALSIFIED_BY_PINNED_CONTROL_INVARIANT`

The plan treated keepalive as a harmless liveness witness during setup. That
assumption is false for the pinned server semantics: keepalive count is also a
control-state input to the incomplete-setup guard. The frozen plan emitted far
more than the guard value before its late `AR OK` command on every allocated
branch. It is therefore unsafe under the source model retained by this
repository.

This is a code/control conclusion. It does not depend on RF content and does
not justify another live attempt.

### Remote close cause — `INCONCLUSIVE`

The observed sequence is consistent with the pinned incomplete-setup removal
path, but consistency is not causal identification. The receipt does not prove:

- that any live endpoint ran the pinned revision;
- which locally sent commands reached the server;
- the remote `cmd_recv` value at close;
- that the incomplete-setup predicate, rather than expiry, inactivity, kick,
  transport loss or another unobserved condition, ended the connection.

No remote cause is assigned.

### Physical multichannel capability — `NOT_EVALUATED`

The control path failed before even one semantic SND frame was admitted. The
outcome therefore says nothing decisive about simultaneous channel capability,
receiver RF operation, feature detectability, retune invariance or either F2
physical hypothesis.

## Claim boundary

Authorized:

- F2.5.15 recorded zero semantic SND frames after eight channel allocations;
- the local client emitted 15 or 16 keepalives before `AR OK` on each of them;
- the pinned source gives those keepalives non-neutral setup semantics;
- the frozen control plan is unsafe under that pinned model;
- the remote cause and physical capability remain unresolved.

Not authorized:

- the pinned guard caused the live closes;
- the endpoints ran the pinned revision;
- `AR OK` was the only missing setup command;
- the endpoints lack multichannel SND;
- a physical or RF hypothesis was tested.

## Minimum conceptual correction, not an execution plan

A future control plan would have to make setup phase explicit: finish the
required ordered commands, including the rate-dependent acknowledgement,
before starting a keepalive cadence based on elapsed time. Its receipt would
need to distinguish local send, remote acknowledgement where available, setup
completion and periodic liveness. This gate does not implement that correction
and grants no live authority.

## SHOCK

The supposed health witness was itself an intervention. `keepalive` did not
merely report that the channel was alive; in the pinned implementation its
count participates in deciding that an incompletely configured channel is
hung. The qualification mechanism could therefore destroy the capability it
was trying to witness. The surviving abstraction is not “keepalive”, but an
explicit transform/control ledger whose commands are treated as causal acts.

Gate F2.5.16 stops here.
