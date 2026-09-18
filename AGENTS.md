# Satellite-RF-Observatory — operational constitution

**Freeze claims, not ordinary engineering.** Use the least machinery that
protects scientific validity and reproducibility. User instructions take
precedence. This replaces administrative defaults, not existing experiments'
scientific boundaries.

## Direction and where to read

Build a general verification workflow: satellite/day request -> qualified
estimation -> withheld checks -> result or explicit failure. Infer position from
Internet RF without target-state input to fitting. Answer new physical questions,
not administrative extensions of old gates. Reference-only exploration on
exposed data may proceed rapidly; prospective confirmation needs blind preparation.

Read only the documents relevant to the task:

- [Project status](docs/PROJECT_STATUS.md): current priorities, results and gaps.
- [General workflow](docs/GENERAL_VERIFICATION_WORKFLOW.md): product and worker
  behavior; [development workflow](docs/DEVELOPMENT_WORKFLOW.md): Git integration.
- [Scientific roadmap](docs/SCIENTIFIC_ROADMAP.md): research and validation;
  [cohort protocol](docs/VALIDATION_COHORT_PROTOCOL.md): campaign prerequisites,
  not acquisition permission.
- Reports in `research/exploratory/`, `research/kinematic/` and `experiments/`:
  evidence, access boundaries, manifests, retries and replay. Read the affected
  experiment's documents before operating it, not the whole history.
- [Original roadmap](ROADMAP.md) and Git history: historical forward-orbit work,
  not the active gate sequence.

Keep results, version histories and next-step detail there, not in this file.

## Three regimes

### 1. Exploratory / already-exposed data

Refactor, revise hypotheses, compare models and rerun analyses with reproducible
inputs, relevant tests/CI, honest versioning and complete reporting of variants,
failures and worsening cases. Label prior exposure and exploratory scope.

Preregistration, independent review, separate authority, freeze commits,
checked wrappers and experiment-specific seals are **not required by default**.
Require a concrete scientific reason not covered by existing mechanisms.
Ordinary PR review rules still apply. Distinguish new development results from
preserved evidence; exposed-case replay is not prospective confirmation.

### 2. Pre-confirmatory / observation-blind selection

Before opening the relevant observation, freeze candidates, selection rules and
measurement-access boundary. Distinguish allowed metadata/structure from
forbidden values, and qualification from primary confirmation. Preserve hashes,
provenance and prior-access records. No silent candidate replacement contrary
to the rule after inspecting availability or measurements.

Use the minimum sufficient authority: one manifest binding inputs, implementation
and rules rather than duplicate plan/scorer/executor seals. Repair engineering
with recorded changes/accesses while preserving selection and claim boundaries.
Changes to those boundaries require a new valid blind design.

### 3. Prospective one-shot confirmation

Before access, freeze the hypothesis, geometry/candidates, observables, nulls,
transforms, uncertainty assumptions, thresholds, selection/stopping rules,
implementation and evaluation order relevant to the claim. Retain hash-before-
decode where applicable. Ephemeral/value-blind handling is mandatory wherever
it protects an unopened prospective experiment; keep observation values out of
logs, caches and artifacts that its access contract forbids.

Fit only admitted inputs. Freeze the solution, uncertainty and predictions
before held-out evaluation and oracle reveal. Retain every attempt and terminal,
including missing data, invalid execution and rejected results. No post-reveal
tuning, silent fallback or search for a passing replacement. Declare retry
semantics in advance; a technical failure is not automatic permission to retry.
Preserve replay evidence. Record corrections/invalidation separately from the
original outcome. New confirmation claims need appropriately unexposed evidence.

## Scientific invariants in every regime

- Closed experimental outcomes remain immutable. Never change thresholds,
  windows, candidate sets, nulls or uncertainty floors after reveal to obtain a
  preferred outcome. Corrections and exploratory extensions remain separate.
- Where independence is claimed, target state must not influence selection,
  preprocessing, calibration, initialization, fitting, regularization or
  uncertainty tuning. This includes orbit/clock products, derived corrections,
  radius constraints and propagated prior solutions. Explicitly admitted
  non-target reference states and terrestrial coordinates are allowed.
- Exclude forbidden target records before numeric parsing; reject them again
  at the calibration boundary. Keep removal/poisoning invariance tests. Preserve
  admitted extracts or receipts as the experiment's retention contract permits.
- Never relabel exploratory, synthetic, qualification or replay evidence as
  prospective confirmation. Failures, unsupported cases and worsening results
  stay visible with their denominators. Claims cannot exceed the evidence.
- Residual RMS is not position accuracy; oracle error is not prospective
  uncertainty. Check observability, nuisance modes, degeneracies and branches.
  State units, frames, time scales, emission/reception, Earth rotation and
  interpolation/extrapolation conventions. Propagate correlations/systematics;
  declare uncertainty assumptions and numerical limits. Local covariance,
  finite simulations and shared products do not prove global bounds,
  independent truth or population coverage.
- Preserve each event's declared criteria and outcome labels in its plan/report;
  do not replace them with generic defaults. A historical position is not live
  tracking, a snapshot is not motion, and GPS support is not universal support.

## Engineering autonomy and restraint

Make normal implementation decisions within scope without repeated permission.
Refactor parsers/helpers/infrastructure, fix adjacent bugs, consolidate modules,
reuse qualification/replay primitives, remove dead or redundant
**non-authoritative** scaffolding, and improve tests, CI, typing, error handling,
performance and stale documentation.

Preserve reproducible evidence, historical source bytes and line endings bound
by manifests. Improve active code while retaining historical versions through
existing mechanisms. Never change expected hashes to conceal altered evidence
or weaken prospective boundaries for convenience.

**Do not create a new seal, authority, verifier, checked wrapper, replay layer
or experiment-specific executor when tests, CI, Git history, an existing
manifest or an existing replay mechanism already protects the same invariant.**
First identify the concrete failure mode uniquely prevented and why existing
protection is insufficient. This adds no approval gate or governance document.

Preserve Linux/Windows CI and relevant regression/fail-closed tests; prefer
reusable tests over per-experiment wrappers. Check proportionately: routine
documentation edits need no new scientific run or numerical test. Never weaken
tests or remove evidence for green CI. Reuse the worker/queue; inspect expired
claims and reconcile terminal results instead of blindly redispatching.

## Collaboration and integration

Commits, pushes and PR integration are authorized within agreed work. Inspect
diffs, pass applicable checks and respect repository protections. Preserve
scientific ancestry with merge commits where receipts/tests require it; no
force push or bypass. Deployment and messages to others need authorization.
Git integration is not scientific admission.

Use `gh` for GitHub; authenticated/network commands run outside the Windows
sandbox. Sandbox DNS/socket errors do not prove expired tokens: verify with
`gh auth status` outside it, never demand `gh auth login` from that error.
Do not spawn sub-agents merely because this file is named AGENTS.md.
Report what changed, relevant checks, physical findings and remaining limits.
