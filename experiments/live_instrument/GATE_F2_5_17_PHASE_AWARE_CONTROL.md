# Gate F2.5.17 — phase-aware SND control

## Scope and stop

Gate F2.5.17 repairs only the local SND setup mechanism falsified by the
F2.5.15 outcome and F2.5.16 attribution. It performs no KiwiSDR connection, RF
acquisition, endpoint retry, feature discovery, threshold change or observation
window.

The only network access was a read-only GitHub source retrieval of
`rx/rx_sound_cmd.h` from the already pinned KiwiSDR server commit
`c40ecb471dced33689e335689f8ffd35a54f47fa`. The file is retained with its
file-level GNU Library GPL 2-or-later notice, Git blob and SHA-256. No receiver
was contacted.

## Source gap closed

The newly retained header defines:

```text
CMD_FREQ       0x01
CMD_MODE       0x02
CMD_PASSBAND   0x04
CMD_AGC        0x08
CMD_AR_OK      0x10
CMD_SND_ALL    0x1f
```

`CMD_SND_ALL` is exactly the union of frequency, mode, passband, AGC and the
rate-dependent `AR OK` acknowledgement. Combined with the previously retained
server loop, this closes the F2.5.16 source-retention gap: the pinned model can
withhold SND while any one of these bits is missing and can classify the
connection as hung after more than four keepalives during that incomplete
state.

This does not retroactively bind the versions run by the live F2.5.15 peers.
Its remote close cause remains `INCONCLUSIVE`.

## Corrected local control sequence

The successor opener implements one immutable sequence:

```text
WebSocket open
→ local auth send
→ observe badp OK + channel + sample rate + audio rate
→ emit AR OK exactly once
→ emit channel configuration exactly once
→ mark REQUIRED_SETUP_EMITTED_LOCAL
→ permit elapsed-time keepalive cadence
→ observe first semantic SND/IQ readiness
```

The channel configuration contains no keepalive. Repeated metadata cannot emit
the setup again. Reordering, duplication or mutation of the setup tuple is
rejected before use. The frozen keepalive interval is 1.0 s and starts only
after all required setup commands have been locally emitted.

## What the receipt says—and does not say

The new phase receipt records separately:

- local auth emission;
- required remote metadata observation;
- one local required-setup emission with ordered command hashes;
- each post-setup time-paced keepalive;
- the first SND readiness witness or termination before readiness.

`local_setup_emission_clause` can become `SATISFIED` because local sends are
observable. `remote_setup_acknowledgement_clause` is always `NOT_EVALUATED`:
the retained protocol exposes no acknowledgement proving the server's internal
`cmd_recv` mask. A successful semantic SND remains the first downstream witness
that the complete path became usable.

## Offline falsification check

A narrow simulator contains only the retained setup-mask and keepalive-guard
semantics.

- Frozen failed schedule: fifteen keepalives can occur before late `AR OK`; the
  guard predicate becomes true before setup completion.
- Corrected schedule: `CMD_SND_ALL` is complete before the first keepalive;
  arbitrary later keepalives do not enter the incomplete-setup guard.

Synthetic socket tests also establish:

- full and piecemeal metadata produce exactly one setup;
- no keepalive occurs before setup;
- repeated metadata cannot duplicate `AR OK`, tune or AGC;
- keepalive spacing cannot be faster than the frozen interval;
- explicit `badp` refusal remains a capability rejection, not a physical
  absence;
- strict receipts contain no RF payload;
- connector and WebSocket framing remain mandatory injections;
- the module exposes no autonomous or live entry point.

## Outcome

`PHASE_AWARE_SND_CONTROL_MATERIALIZED_OFFLINE`

The local control defect is repaired relative to the pinned source model. This
is not a multichannel qualification and not an RF observation. The corrected
branch opener must still be composed into the two simultaneous branches,
sealed after commit and granted a separate exact authority before any receiver
may be contacted.

Gate F2.5.17 stops here.
