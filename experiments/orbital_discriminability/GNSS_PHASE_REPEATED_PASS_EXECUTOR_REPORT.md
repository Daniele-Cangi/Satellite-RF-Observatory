# G22/G30 DOY 219 repeated-pass executor

Terminal offline state:

    REPLICATION_EXECUTOR_FROZEN_OBSERVATION_UNOPENED

The executor is ready for review but grants no live authority. Neither the
DOY 219 replication products nor the DOY 218 reserve were discovered, opened
or decoded.

## Physical purpose

The future one-shot execution can answer whether the orbital-model preference
already observed on DOY 220 repeats on the distinct frozen DOY 219 pass. The
executor itself produces no new physical claim; it is the minimum plumbing
strictly required to reach that held-out comparison.

No new gate, receiver inventory, adapter or generic experiment framework was
created.

## Minimum reuse boundary

The consumed DOY 220 primary source was not modified. Its complete canonical
source hash is bound as a model-blind measurement kernel:

    bbacf8653a74198941a6380640d43b5e7ffc7d46767039e84604db0de61793fc

Only four invariant operations are reused:

- complete-file materialization and hash before decode;
- in-memory Hatanaka decode;
- ionosphere-free four-link coordinate composition and erase;
- constant-plus-rate fit on the calibration prefix.

The DOY 220 grid, locators, thresholds, seal and outcome are explicitly not
reused. DOY 219 has its own header grid, product locators, prediction seal,
one-model envelope, pairwise guard and repeated-pass outcome semantics.

## Frozen execution

- stations: GOLD00USA and NLIB00USA;
- date: DOY 219 / 2026-08-07;
- raw GPS interval: 05:46:00--06:55:00;
- target/reference: G22/G30;
- raw epochs: 139 at 30 seconds;
- calibration/held-out feature epochs: 77/60;
- one-model envelope: 1,188.851495144414 m;
- pairwise guard: 2,377.702990288828 m;
- no interpolation, gap bridging, free time phase or suffix refit;
- one attempt per locator;
- no endpoint/date substitution;
- no DOY 218 fallback;
- outcome path may not already exist.

The only positive future outcome is
ORBITAL_MODEL_REPEATED_PASS_PREFERRED. It authorizes repeated-pass consistency
only for these two GOLD/NLIB G22/G30 passes. It does not authorize general
GNSS identity, independence from shared station-pair systematics or
unconstrained orbit determination.

## Hash ledger

- executor source commit:
  d080bbb6b4db5d7328863e02d1df0baff6331658;
- executor source canonical SHA-256:
  a03e3daf685851afa067dccb6974f72ba64f468b3823f2607c90e81f75a403fb;
- executor manifest SHA-256:
  287a5470adbcd11bc98560562a58790a38e744cdbb140f82b6e659b923029113;
- plan manifest SHA-256:
  a9c7b00feb9b2fa277e5cd8d71ec22d6726cc4068bf932ef67560b07d68250ed;
- prediction canonical SHA-256:
  d408696d5c9d6e446216fdd7bad240a300e4d0d6d27af470756ff7d1413896b0;
- prediction seal canonical SHA-256:
  8d4466be2037420fb251f7ed70de8d463d9489264948245606a1a65b5d79987d;
- executor seal canonical SHA-256:
  490f60155dde4972df411d08717462e28b123883e3ef4aea15d708c982208ed6.

## Tests and stop

The focused suite covers exact frozen-input binding, DOY 219 header/grid
semantics, phase/LLI admission, the distinct DOY 219 decision guard,
authority-before-network, no overwrite, strict JSON, exact seal validation
and a complete injected one-shot path with zero observation-value
persistence.

Stop here. A later live run requires a separate review and an explicit
authority token plus the exact executor-seal SHA-256. The seal itself does not
authorize observation access.
