# General verification workflow (local, experimental)

The user approved the general request-to-result objective on 2026-09-12.
See [the delivery plan](../docs/GENERAL_VERIFICATION_WORKFLOW.md). The new
`workflow.py` layer prepares requests for the existing GPS network profile and
reads already sealed worker results. Neither command downloads observations,
starts an estimator, submits a queue job or publishes anything.

```powershell
python -m service capabilities
python -m service prepare G15 2026-09-01 --prior-access "Planning example only; exposure not established." --plan-output request-plan.json
python -m service result experiments/positioning_g14_doy246_network
python -m service result experiments/positioning_g13_doy247_request
```

The example date/target is only an offline planning example, not an approved
campaign. `prepare` accepts a completed historical GPST day and GPS G01..G32.
It freezes the existing ten-candidate/seven-fit station policy with GOLD held
out into a standard `positioning` plan. It does not freeze the implementation
or establish source availability. Unknown request fields and unsupported
profiles are rejected. A known closed event returns `ARCHIVED_EVENT` and its
original evidence directory instead of creating another plan. The first three
older archive events use legacy formats; this reader currently supports the
sealed worker dossiers used by G13/G14, not those legacy dossiers.

Programmatic input to `prepare_request` contains exactly `target`, `date_gpst`,
`profile` and `prior_access`. `PLAN_PREPARED` means only that the request can be
represented by the existing profile. Its returned `plan` passes
`positioning.plans.validate_plan` and can be consumed by the existing local
worker once the run declaration and access history are settled. The optional
plan file is created exclusively: an existing declaration is never overwritten.

`result` verifies every artifact listed by `terminal_receipt.json` and parses
the dossier from the same bytes it hashed. It retains the original frame,
emission time, conditional uncertainty, comparison error and scientific status.
Missing values stay null. `COMPLETED` does not imply scientific success;
`UNCERTAINTY_TOO_LARGE` stays inconclusive even if orbit agreement is good.
Unknown outcomes, contradictory labels, changed or unsealed results are rejected.
Local seals detect modifications relative to a receipt, not malicious rewriting
of the receipt itself or scientific correctness. Read operations never reseal.

## Existing remote request foundation (P1, not deployed)

`requests.py` is a standard-library SQLite reference implementation for a
single-host persistent Python gateway. It does not expose HTTP routes, execute
the solver, access observations, provide authentication or establish remote
connectivity. It is intentionally outside the frozen scientific package.

Implemented and tested:

- server-supplied owner identity scopes read and cancellation;
- immutable canonical plan, explicit purpose and full implementation commit;
- per-owner idempotency, conflicts when the same key changes its declaration;
- bounded global and per-owner active requests;
- one live worker claim across competing database connections;
- hashed worker claim tokens, heartbeats and terminal result digests;
- expired workers enter `NEEDS_REVIEW` and block dispatch. They are never
  automatically retried, including after confirmation may have been revealed;
- queued cancellation and operational event history that survive reopening.

This is a control-plane building block, not a complete service. The trusted
worker must validate result seals before calling `finish`. `COMPLETED` is an
operational state; the referenced dossier carries the scientific outcome.
The store cannot stop a process or prevent it from reading an oracle. The
executor must enforce stage isolation and must stop on losing its lease.
An operator recovery path must inspect receipts and terminate stale processes
before clearing `NEEDS_REVIEW`; no reset/requeue operation is exposed here.

## Proposed HTTP adapter

These are contracts for the next implementation, not existing endpoints:

| Route | Behavior |
|---|---|
| `POST /api/requests` | Validate supported plan, purpose and pinned implementation; require idempotency key; return 202 plus request ID |
| `GET /api/requests/:id` | Authenticated owner view; same 404 for absent and other-owner records |
| `POST /api/requests/:id/cancel` | Cancel queued work; reject an already running attempt |
| `GET /api/requests/:id/dossier` | Authorize owner, verify stored digest and stream sealed evidence |

Never accept an owner ID as browser-controlled authorization. Resolve identity
in the authenticated Sites server and authenticate its HTTPS calls to the
gateway. Worker claims are server-only and must not be browser endpoints.
Limit body size, allow only registered execution versions, and apply quotas
before any data acquisition. Request purposes are `availability`,
`historical_replay` and `prospective_attempt`; a purpose label alone does not
prove blinding. New prospective runs still need the scientific declaration and
access-history checks, separately from these software tests.

## Deployment decision still open

Sites currently serves the private static archive. Choose and verify either
an authenticated gateway reachable by outbound HTTPS from Sites, or a supported
service-auth path to a central Sites control API. Do not assume browser identity
headers are available to a headless worker. Do not create two authoritative
queues. This SQLite implementation supports the gateway option; a D1 option
would need its own atomic repository adapter and concurrency tests.

Before a private request can ship, implement and verify the HTTP adapter,
durable artifact storage, worker bridge, phase receipts and recovery, actual
network isolation, Sites server-backed build and the browser request UI.
No external executor or paid resource has been provisioned. Hosting and budget
are awaiting the owner's input.

## Checks

From the repository root:

```text
python -m pytest service/tests -q
```

Tests use a previously declared plan as a technical fixture and never acquire
RF data, rerun G14 or open an oracle. SQLite state belongs on a private persistent
local disk, outside Git and outside public web assets. This is a single-host
pilot, not a multi-host queue backed by a shared network filesystem.
