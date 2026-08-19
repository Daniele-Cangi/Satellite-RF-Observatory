# Satellite-RF-Observatory — Agent Operating Instructions

## 1. Project North Star

Satellite-RF-Observatory is a **satellite-first physical inference project**.

Its central scientific question is:

> Can a candidate orbital geometry predict observer-coupled RF structure in a future held-out interval better than predeclared non-orbital alternatives?

The causal order is:

```text
candidate orbit + observer geometry + event time
    ↓
distributed orbital prediction
    ↓
pass-specific detectability requirement
    ↓
minimum qualified measurement capability
    ↓
prospective observation
    ↓
held-out orbital-versus-null comparison
    ↓
physical inference
```

The **orbit is the causal center**.

Receivers, APIs, inventories, search engines, SDR protocols, receipts, metadata, storage and orchestration are subordinate tools.

They must never become the scientific target by themselves.

---

# 2. Priority hierarchy

When goals conflict, use this order:

1. **Scientific North Star**
2. **Physical information gain**
3. **SHOCK: alternative physical routes**
4. **Minimum viable experiment**
5. **Measurement integrity**
6. **Evidence provenance**
7. **Infrastructure quality**
8. **Documentation completeness**

Lower levels must not block higher levels unless they are genuinely required to make the physical result interpretable.

In particular:

> Provenance is not the experiment.

> Infrastructure is not the scientific result.

> A perfectly receipted path that never reaches the satellite question is a failure of direction.

---

# 3. Information-gain test

Before creating any substantial new work item, successor gate, subsystem or abstraction, explicitly answer:

```text
What new information about the satellite/orbital hypothesis can this work produce?
```

Valid answers include:

* whether the orbital signature is detectable;
* whether observer geometry is discriminative;
* whether a real measurement path preserves the predicted structure;
* whether a held-out observation agrees with the orbital prediction;
* whether a frozen non-orbital null explains the data better;
* whether one orbit is distinguishable from alternative orbital hypotheses.

Invalid answers, by themselves, include:

* improving a search result format;
* formalizing API discovery;
* creating a better endpoint inventory;
* improving serialization;
* strengthening metadata receipts;
* designing a generic adapter;
* proving that a web directory is complete;
* reproducing browser selection behavior;
* expanding orchestration infrastructure.

If the answer is:

> “No new physical information; this only improves plumbing.”

then **do not create a research gate for it** unless that plumbing is strictly necessary for the next physical observation.

---

# 4. A failure does not automatically justify a successor gate

This is a hard rule.

```text
FAILURE ≠ NEW GATE
```

A failure should first trigger a change-of-abstraction review.

Ask:

1. Is the failed mechanism actually necessary?
2. Can the claim scope be narrowed instead?
3. Can a different physical route bypass the failure?
4. Can the experiment use a fixed, predeclared capability instead of global discovery?
5. Can published observations or another sensor family answer the same physical question?
6. Is the project learning about satellites, or merely learning about its own tooling?

Only create a successor gate when it closes or tests a **physically meaningful edge** of the satellite-first causal chain.

---

# 5. Prefer narrower claims over larger infrastructure

Do not build global infrastructure merely to support a stronger claim than the experiment needs.

For example:

Bad requirement:

> prove that no suitable Internet RF receiver exists.

Often sufficient:

> these two predeclared independent receivers were or were not qualified for this frozen pass.

Bad requirement:

> establish a complete neutral inventory of public SDR receivers.

Often sufficient:

> freeze a bounded, explicit receiver set before observing RF and restrict the claim to that set.

Bad requirement:

> discover the globally optimal station pair.

Often sufficient:

> show that one predeclared independent pair has positive predicted discriminability margin.

Use:

```text
narrow claim + real experiment
```

before:

```text
broad claim + large infrastructure
```

---

# 6. Shock → Spike → Proof → Harden

This project follows four distinct phases.

They must not be collapsed.

## SHOCK

Purpose:

> Find surprising physical routes to the satellite question.

During SHOCK:

* generate causally different approaches;
* allow unconventional sensor combinations;
* question current abstractions;
* discard failed mechanisms freely;
* search for shortcuts to physical information;
* compare forward and inverse formulations;
* consider SatNOGS, KiwiSDR, WebSDR, published measurements, fixed stations or mixed roots;
* maximize information gain.

Do **not** during SHOCK:

* freeze implementation details prematurely;
* create a gate for every uncertainty;
* insist on complete infrastructure;
* generalize abstractions;
* optimize provenance machinery;
* preserve failed mechanisms merely because work was invested in them.

A SHOCK failure should usually produce **alternative mechanisms**, not a more detailed version of the failed mechanism.

---

## SPIKE

Purpose:

> Build the smallest vertical path that can physically answer something.

Spike rules:

* use bounded pragmatic choices;
* fixed receiver lists are acceptable;
* manual or operator-selected scope is acceptable if declared before observation;
* no need for global discovery;
* no need for reusable adapters;
* no need for product architecture;
* no need for complete automation.

A spike should minimize:

```text
orbit prediction
→ instrument
→ observation
→ held-out comparison
```

Everything not required by that path is deferred.

---

## PROOF

Purpose:

> Freeze the scientific test before seeing the confirmation outcome.

Only here freeze:

* candidate orbit;
* observer set;
* carrier or carrier interval;
* calibration interval;
* confirmation interval;
* nuisance parameters;
* null families;
* detectability criteria;
* missing-data budget;
* transform rules;
* physical outcome semantics.

Proof protects against post-hoc adaptation.

Proof does not require turning every descriptive dependency into a research gate.

---

## HARDEN

Purpose:

> Prevent a valid experiment from producing an invalid claim.

Only here emphasize:

* immutable evidence;
* receipts;
* hashing;
* lineage;
* exact environment where necessary;
* zero-retry confirmation;
* frozen outcomes;
* strict serialization;
* cleanup guarantees;
* reproducibility.

HARDEN must not leak backwards and dominate SHOCK or SPIKE.

---

# 7. Historical F2.5 rule

`experiments/live_instrument/` is a **historical measurement-integrity layer**.

Its results are valuable.

Its sequencing style is **not a template for new orbital work**.

Do not imitate the historical pattern:

```text
failure
→ frozen failure artifact
→ exact successor
→ new gate
→ new execution
→ next failure
→ next gate
```

unless the sequence is still producing physical information about the satellite question.

F2.5 demonstrated useful controls:

* same-path witnesses;
* event-time reasoning;
* capability qualification;
* transform lineage;
* distinction between descriptive and physical failures;
* bounded RF persistence;
* causal receipts.

Reuse these primitives only when justified by the current orbital experiment.

Do not recreate the F2.5 gate treadmill in another subsystem.

---

# 8. Orbital-first requirement

Before selecting a receiver for a physical experiment:

1. freeze or declare the candidate orbital hypothesis;
2. propagate observer-specific trajectories;
3. compute pass-specific differential structure;
4. determine minimum time/frequency resolution;
5. determine the required joint visibility;
6. determine the acceptable timing uncertainty;
7. determine whether the planned sensor geometry has positive discriminability margin.

Only then evaluate whether a candidate instrument can preserve that structure.

Receiver convenience must not choose the satellite.

Band convenience must not choose the scientific question.

---

# 9. Current orbital observables

The preferred geometric primitive is:

```text
y_i(t) = -range_rate_i(t) / c
```

For independent observers:

```text
Δy_ij(t) = y_i(t) - y_j(t)
```

Important observables include:

* fractional Doppler;
* differential Doppler;
* Doppler slope;
* Doppler curvature;
* visibility interval;
* closest-approach timing;
* range-rate zero crossing;
* observer-dependent event ordering;
* held-out differential residual.

Carrier scaling should remain downstream of fractional orbital geometry whenever possible.

---

# 10. Nuisance discipline

Allowed nuisance parameters must be declared before confirmation.

Typical allowed nuisance:

* station-local constant frequency offset;
* bounded affine oscillator drift;
* bounded event-time error;
* carrier uncertainty;
* explicit orbital prediction envelope;
* declared dropout/quantization/noise behavior.

Do not allow nuisance terms to absorb the orbital signal.

Do not introduce:

* unconstrained splines;
* arbitrary time warps;
* per-sample corrections;
* post-outcome threshold changes;
* holdout-informed calibration;
* flexible models whose complexity is chosen after seeing the result.

---

# 11. Held-out evidence rule

A physical orbital claim requires genuinely independent evidence.

Calibration and confirmation must be disjoint.

The confirmation interval must not:

* fit nuisance parameters;
* choose a receiver;
* select a target feature;
* change the carrier;
* modify the null set;
* alter thresholds;
* redefine missing-data rules.

For inverse work, prefer a held-out observer where practical:

```text
A + B
→ infer candidate orbital family
→ freeze prediction for C
→ observe C
→ compare
```

For early forward work, a temporal held-out interval with two independent hardware roots is sufficient if declared in advance.

---

# 12. Null-model discipline

Nulls must be meaningful alternatives, not caricatures.

They must:

* be frozen before confirmation;
* use the same calibration data;
* use the same holdout;
* have declared complexity;
* avoid post-result tuning.

Separate two questions:

## Orbitality

Does orbital geometry outperform non-orbital explanations?

## Specific orbit identity

Does one specific orbit outperform alternative physical orbital hypotheses?

Alternative orbits are not generic nulls.

Do not jump from:

```text
orbital model preferred
```

to:

```text
satellite identity established
```

---

# 13. Claim ladder

Use progressively stronger claims.

```text
MEASUREMENT_VALID
        ↓
ORBITAL_SIGNATURE_DETECTABLE
        ↓
ORBITAL_MODEL_PREDICTIVELY_PREFERRED
        ↓
SPECIFIC_ORBIT_PREFERRED
        ↓
HELD_OUT_STATION_CONFIRMED
        ↓
REPEATED_PASS_CONSISTENCY
        ↓
IDENTITY_CANDIDATE_SUPPORTED
```

Never skip levels.

A receiver observation is not satellite identity.

A model-conditioned SatNOGS artifact is not independent confirmation of the same identity.

A good calibration fit is not a held-out prediction.

---

# 14. Capability discovery rules

Capability discovery is a supporting task, not a research program.

Permitted approaches for the first forward vertical include:

* a fixed predeclared pair of public receivers;
* a small operator-declared receiver set;
* known SatNOGS stations;
* published observation artifacts;
* a manually scoped instrument set frozen before RF inspection.

A global neutral inventory is **not required** unless the claim explicitly depends on global coverage.

Do not create additional research gates merely because:

* a search provider merges results;
* an API lacks a perfect schema;
* an inventory lacks global completeness;
* a directory requires interactive browsing;
* machine-readable discovery is inconvenient.

If discovery infrastructure becomes more complex than the physical experiment, reduce scope or change route.

---

# 15. Search-engine rule

General web search is reconnaissance only.

Search-engine ranking, query grouping, result partitioning and search-provider transport semantics are **not part of the physical measurement chain**.

Do not turn search-engine behavior into a sequence of research gates.

If web search cannot produce a clean machine-readable inventory:

* use another source;
* use a fixed receiver set;
* use operator-known stations;
* use SatNOGS;
* narrow the claim.

Never build an “epistemology of search” unless search itself is the scientific object, which it is not here.

---

# 16. SatNOGS role

SatNOGS may be used in two different ways.

## Model-conditioned forward validation

Acceptable:

```text
known candidate orbit
→ predicted station-specific Doppler
→ existing/published SatNOGS observations
→ held-out comparison
```

But selection by NORAD/transmitter means these observations are not targetless evidence of identity.

## Independent/inverse work

SatNOGS identity labels must not be treated as ground truth if the task is to infer identity from RF.

Whenever raster waterfalls are used, account for:

* time resolution;
* frequency-bin resolution;
* lossy rasterization;
* ridge extraction uncertainty.

---

# 17. Kiwi/WebSDR role

A KiwiSDR, WebSDR or similar receiver is a remote telescope.

It is not the project.

Use F2.5-derived integrity controls where necessary, but do not revisit DDC internals unless a concrete orbital observation is invalidated by receiver ambiguity.

Two channels from the same Kiwi are useful for receiver diagnostics.

They are **not equivalent to independent observer geometry**.

Distributed orbital evidence requires independent physical measurement roots when the claim depends on geography.

---

# 18. Gate creation criteria

A new gate is justified only if all are true:

1. it has a distinct physical question;
2. it can produce a new physical outcome;
3. the result changes what can be claimed about orbital geometry or measurement validity;
4. it cannot be handled as a normal implementation repair;
5. it does not merely formalize infrastructure.

Before creating one, write:

```text
Physical question:
New information produced:
Why existing gate cannot answer it:
Minimum experiment:
Stop condition:
```

If `New information produced` is empty or infrastructural, do not create the gate.

---

# 19. Repair versus new gate

Use a normal implementation repair for:

* test bugs;
* incorrect visibility masks;
* numerical-envelope implementation errors;
* parser corrections;
* CI environment fixes;
* duplicated logic;
* deterministic search-tool incompatibility;
* code organization;
* documentation errors.

A correction becomes a new scientific gate only when it changes the physical hypothesis, observational contract, frozen proof design or interpretable outcome set.

Not every code change needs a new gate number.

---

# 20. Anti-bureaucracy rule

Stop immediately if the project begins producing more machinery about:

* selection;
* authority;
* inventory;
* schema;
* search;
* orchestration;
* receipts;

than about:

* orbit;
* pass;
* observer geometry;
* Doppler;
* physical measurement;
* held-out prediction;
* null discrimination.

That imbalance is a signal of conceptual drift.

---

# 21. Anti-drift question

At every checkpoint ask:

> If the receiver implementation disappeared tomorrow, would this work still tell us something new about the satellite hypothesis?

If yes, it is likely central research.

If no, ask whether it is truly necessary for the next physical observation.

---

# 22. Current state

The current research state is:

## F2.5

Concluded.

Treat as:

```text
RF Measurement Integrity Layer
```

Do not continue F2.5 except for genuine maintenance defects.

## G0

Orbital discriminability mechanism established offline.

Useful results already exist:

* deterministic multi-observer trajectories;
* fractional and differential Doppler;
* held-out nuisance separation;
* null comparison;
* detectable and undetectable synthetic regions.

G0 may receive **one bounded hardening pass**, not a new gate family.

Required hardening:

* apply joint visibility consistently in G0 scoring;
* use direct time-shift trajectory envelopes for large clock uncertainty;
* remove/rework null redundancy;
* add at least one model-mismatch synthetic stress case.

Do not create G0.1, G0.2, etc. for these.

## G1

Pass-specific capability admission is conceptually valid offline.

Keep:

```text
orbit/pass
→ receiver geometry
→ detectability margin
→ fixed capability set
```

## G1.1–G1.3

Treat as a concluded side investigation into capability discovery.

Do not continue the inventory/search chain.

No G1.4 should be created merely to repair search-provider result partitioning.

---

# 23. Immediate next objective

The next meaningful objective is the first **forward satellite observation vertical**.

Preferred shape:

```text
known candidate orbit
        ↓
frozen pass + carrier
        ↓
2+ independent predeclared receiver roots
        ↓
pass-specific G1 detectability check
        ↓
measurement-path qualification
        ↓
calibration prefix
        ↓
held-out confirmation suffix
        ↓
orbital prediction versus frozen nulls
```

The receiver set may be small and explicitly scoped.

Do not require a global capability inventory.

---

# 24. Forward before inverse

Do not attempt unconstrained orbit reconstruction first.

First demonstrate:

```text
known orbit
→ predicts independent distributed RF dynamics
```

Then move to:

```text
targetless tracks A+B
→ infer candidate orbital family
→ freeze prediction for C
→ held-out confirmation
```

The inverse challenge should initially rank:

* candidate orbital families;
* catalog objects;
* controlled alternative orbits;

rather than claim full six-element orbit reconstruction from one sparse pass.

---

# 25. No premature productization

Until a genuine physical held-out result exists, do not prioritize:

* frontend;
* dashboard;
* database;
* scheduler;
* persistent receiver catalog;
* microservices;
* generic experiment DSL;
* source marketplace;
* universal adapter SDK;
* ML/LLM phenomenon selection;
* production deployment.

The project currently needs an experiment, not a platform.

---

# 26. Working style for agents

When asked to “continue”, do not blindly implement the next roadmap bullet.

First:

1. inspect the current physical question;
2. inspect the latest actual outcome;
3. identify whether the next planned step increases orbital information;
4. generate alternatives if blocked;
5. choose the shortest physically meaningful path;
6. only then implement.

If a roadmap instruction conflicts with the North Star, **the North Star wins**.

If old F2.5 patterns conflict with the current satellite-first direction, **the current satellite-first direction wins**.

---

# 27. Default response to a block

When blocked, produce this analysis before coding:

```text
BLOCK:
What physically failed?

INFORMATION VALUE:
What did we learn about the orbital hypothesis?

CURRENT ABSTRACTION:
Is the blocked mechanism actually necessary?

ALTERNATIVES:
A.
B.
C.
D.

BEST PHYSICAL PATH:
Which route reaches a held-out satellite observation fastest?

ACTION:
Implement, repair, bypass or abandon?
```

Do not automatically choose “repair”.

---

# 28. Final rule

The project exists to learn something about satellites through distributed RF observations.

It does not exist to prove that every intermediate software system is perfectly formalized.

Use rigor to protect physical claims.

Use freedom to reach them.
