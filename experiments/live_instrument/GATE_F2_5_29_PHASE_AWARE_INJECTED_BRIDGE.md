# Gate F2.5.29 — phase-aware injected dual-SND bridge

Gate F2.5.29 is exclusively offline. It joins two pieces that were previously
separate:

1. the reviewed Kiwi control order from F2.5.17; and
2. the same-ADC relative-time and one-shot boundary from F2.5.27/F2.5.28.

No endpoint is contacted. Both already-open branch transports and all of their
frames are synthetic, injected test objects. The module has no connector,
network import, command-line runner, authority bit or public execution
function.

## Frozen boundary

The envelope binds:

- the reviewed F2.5.28 commit `d6c2ae756f58dca6a8fc5b2039d4879c5ecfaccb`;
- canonical hashes of the F2.5.17, F2.5.20, F2.5.27 and F2.5.28 causal files;
- the F2.5.28 envelope hash;
- the exact private integration function source;
- the previously qualified endpoint identity and bootstrap coordinate;
- the pinned F2.5.17 control-plan hash;
- eight SND frames per branch;
- zero retry and zero RF persistence.

The endpoint and bootstrap coordinate are lineage, not caller choices. The
bootstrap remains `CONTROL_BOOTSTRAP_NOT_FEATURE`: it is not a discovered
target and does not authorize a physical claim.

## Exact control order

Each injected branch is processed independently and concurrently:

```text
already-open injected SND branch
        ↓
SET auth t=kiwi p=
        ↓
badp=0 + channel + sample_rate + audio_rate observed
        ↓
exact F2.5.17 setup emitted once
        ↓
eight SND frames transferred to the relative gate
```

The required setup is the pinned `CMD_SND_ALL` command set without a
keepalive. An SND frame before complete metadata and local setup is a
`QUALIFICATION_ERROR`. A non-zero `badp` or `too_busy` is an explicit
`CAPABILITY_REJECTED`. These are not interchangeable.

After two ready control transcripts, the pair must report distinct server
channel IDs and compatible sample rates. Only then may the F2.5.28 one-shot
decode and evaluate the relative-time receipt. The wrapper does not apply the
old absolute GPS-age threshold. Reserved clock-state bytes and relative sample
continuity remain the responsibility of the F2.5.27 contract.

## Byte and IQ ownership

Every injected WebSocket frame is represented by a one-owner lease. Taking a
frame:

1. copies its bytes into the bounded wrapper scope;
2. clears mutable injected storage when possible;
3. sets the transport lease payload to `None` before parsing;
4. hashes the bounded copy before protocol or SND analysis.

MSG copies leave scope after their frame. SND copies are held only until the
single synchronous F2.5.28 call returns. In `finally`, every transient input is
replaced by empty bytes and both branch lists are cleared. F2.5.28 separately
zeroizes and verifies all decoded NumPy IQ arrays before returning.

The receipt therefore proves that the wrapper retains zero payload references.
It does not claim to erase unrelated copies that an injected test caller may
have made before transferring the lease.

The returned object contains only scalar metadata and hashes:

- control state and ordered phase names;
- channel and rate metadata;
- local command hashes;
- pre-analysis frame hashes;
- socket-lease and transient-input release counts;
- the strict F2.5.28 result, when admitted.

No RF, waterfall, IQ array or raw frame is returned or written.

## Outcome semantics

`CAPABILITY_REJECTED`
: At least one branch emitted an explicit server refusal in the injected
  transcript. No downstream phase is called.

`QUALIFICATION_ERROR`
: Control order, transport description or frame ownership prevented a valid
  pair receipt. This is not a physical capability claim.

`TOPOLOGY_NOT_ADMITTED`
: Two branch transcripts completed, but they did not preserve the required
  distinct-channel/same-rate representation. The relative one-shot is not
  entered.

`INJECTED_ONE_SHOT_COMPLETED`
: The control pair admitted the frozen F2.5.28 one-shot. Its nested outcome
  still decides whether timing, discovery and retune witnesses passed. This
  wrapper outcome alone is not a physical result.

## Offline verification

The deterministic tests cover:

- exact auth → metadata → setup → SND ordering on both branches;
- one setup emission with no pre-setup keepalive;
- distinct server channel IDs;
- release of every consumed transport-frame lease;
- clearing of all transient SND byte references;
- F2.5.28 IQ zeroization;
- absolute age not acting as freshness admission;
- reserved clock state still blocking discovery and retune;
- early SND, explicit rejection, same-channel and unequal-rate failures;
- hash-preserving malformed-frame qualification errors;
- strict finite JSON receipts without RF keys;
- absence of network imports and public runtime overrides.

## Authorized claims

Gate F2.5.29 demonstrates that an injected dual-SND transcript can obey the
reviewed phase-aware control sequence and enter the topology-specific temporal
gate without reintroducing absolute GNSS freshness. It also demonstrates that
frame-byte ownership and downstream callback access are explicitly closed on
every path.

It does not demonstrate that:

- the selected Kiwi is currently reachable;
- two live channel slots are currently available;
- the server accepted or applied a live setup or retune;
- an RF feature exists;
- the physical feature lies upstream or downstream of the channel DDC.

## SHOCK

The old opener coupled two different questions: “did a usable SND stream
arrive?” and “is its GPS solution fresh in absolute time?” The DDC intervention
needs the first plus relative continuity across two same-clock branches. It
does not need the second.

Removing that unrelated clause makes the control transcript smaller and the
failure semantics sharper. The next gate, if authorized, should be a separate
post-commit seal for a default-refusing live-facing surface with no caller
endpoint, frequency, timing, threshold, callback or receipt-path overrides.
It must not execute a network operation during that audit.
