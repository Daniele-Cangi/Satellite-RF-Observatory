# S2 role-specific five-root structural qualification

## Physical question

Can ALGO, BOGT, MKEA and PIE1 provide the code-plus-phase structure required by
the fit while GOLD independently provides the code-only held-out coordinate,
when each root is admitted only against transformations in its causal path?

## Bounded repair

The closed DOY242 result remains `FIVE_ROOT_STRUCTURE_NOT_QUALIFIED` and is
neither retried nor rescored. This qualification uses unopened DOY241
(2026-08-29), chosen as the immediately preceding complete day before any of
its five station products are accessed. There is no date, station, field or
receiver substitution and no retry.

The four fit roots retain unit C1C/C2W/L1C/L2W storage scales and reject legacy
wavelength factors, applied external GPS corrections and applied receiver-clock
corrections. A finite phase offset declared in the RINEX header is retained in
the receipt, including satellite-scoped overrides. Such an offset is static
metadata and cancels from a stable same-satellite endpoint difference; it is
not required to equal zero.

GOLD is admitted only on C1C/C2W. Its phase-shift and wavelength headers are not
interpreted because phase is outside the held-out observable's causal path.
Code scales, applied external GPS corrections and receiver-clock corrections
remain explicit admission clauses.

Every complete compressed artifact is SHA-256 bound before Hatanaka decoding.
The scanner reads only headers, epoch tags, GPS row identities, field presence
and fit-root L1C/L2W LLI characters. It never converts an observation substring
to a number. Candidate identities are used transiently to count common-window
capacity and are not persisted. Compressed and decoded payloads remain
ephemeral.

The frozen capacity rule is unchanged: eleven consecutive 30-second endpoints,
at least five stable rows per root, one unselected common identity, and at least
four remaining structural reference identities at every root after removing
that identity.

The one run will terminate with exactly one of:

- `FIVE_ROOT_ROLE_STRUCTURE_QUALIFIED`
- `FIVE_ROOT_ROLE_STRUCTURE_NOT_QUALIFIED`
- `FIVE_ROOT_ROLE_STRUCTURE_EXECUTION_INVALID`

A structural pass is not measurement admission. It authorizes only a separately
frozen, distinct-artifact physical-envelope qualification; it does not authorize
target selection, target-state access, numerical target observations or S3.

## Outcome

Not executed. The implementation and plan must be committed with a clean
working tree before the single source access.
