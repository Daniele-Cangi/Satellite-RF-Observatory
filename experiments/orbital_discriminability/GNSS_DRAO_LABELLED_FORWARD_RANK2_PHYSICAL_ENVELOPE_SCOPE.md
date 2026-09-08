# DRAO labelled-forward rank-2 physical-envelope scope

This is one bounded, observation-free continuation of the existing labelled
forward experiment. It is not a new gate and is not a retry or fallback inside
the consumed DOY237 authority.

## Physical question

Does the highest-ranked *unconsumed* geometry from the shortlist frozen before
any DRAO observation access retain positive held-out orbital-versus-null margin
after the same exact retarded-time physical envelope used for rank 1?

## Candidate selection

The rule is fixed before regenerating any model input:

```text
existing pre-observation shortlist
-> exclude the consumed DOY237 structural artifact
-> take the next already-ranked geometry
```

This selects only:

- station `DRAO00CAN`, DOMES `40105M002`;
- GPS DOY238 / 2026-08-26;
- raw window `04:50:00--05:59:00 GPS`;
- held-out start `05:29:30 GPS`;
- codebook `G14/G15/G17/G20/G24/G30`;
- prefix indices 0--78 and held-out indices 79--138.

The selection uses no DOY238 observation locator, header, field, value or
artifact-existence information. DOY237 remains closed and is not reopened.

## Exact model input

The sole transient input is the already hashed shortlist model product:

```text
brdc2380.26n.gz
bytes    71,505
SHA-256  456036b3e4f247c96d834476cb51cbd88d420e37a6abdae6e6d8b2f7d3526e26
raw SHA  a3481251cb013f84e12f0442f63d3190afa146b990550e59dafdd74149a26ee1
```

It is a broadcast-orbit model input, not receiver evidence. It is parsed in
RAM and destroyed after the receipt is produced.

## Frozen envelope

The audit applies exactly the rank-1 causal model:

- iterated one-way transmit time and Earth rotation;
- direct `t - 15 s` and `t + 15 s` trajectory envelopes;
- broadcast orbit accuracy and satellite-clock non-affinity;
- a conservative independent per-track/per-epoch troposphere box;
- station displacement/EOP/relativity interval;
- the unchanged conditional measurement reserve;
- ensemble centering and prefix-only constant/rate projection;
- prefix-affine and time-reversed nulls;
- zero held-out refit, interpolation or free time phase.

Admission requires the exact retarded controlling separation to be strictly
greater than three times the one-model bound `B`.

## Stop

Stop after one exact physical-envelope outcome and deletion of the navigation
payload. Do not query, select or access a DOY238 observation artifact. A
positive result permits only an offline integrated prospective-plan freeze.
