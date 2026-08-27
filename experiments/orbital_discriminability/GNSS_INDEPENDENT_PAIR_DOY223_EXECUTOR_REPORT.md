# DOY223 ALGO/MDO executor seal

## Outcome

`PRIMARY_EXECUTOR_FROZEN_OBSERVATION_UNOPENED`

The disposable DOY223 executor is frozen without requesting either ALGO or
MDO observation product. It binds the existing plan, prediction curves,
model-blind qualification transform, exact parser kernels, transport budget,
measurement clauses and held-out scoring rule.

This is not a new gate and it is not live authority. Its only purpose is to
make the already designed physical experiment executable without changing the
question after observation access.

## Information boundary

If separately authorized, one execution can determine whether the frozen
G22-relative-G30 ALGO-minus-MDO phase coordinate is measurable and whether its
held-out suffix prefers the orbital curve over the prefix-affine and three
wrong-orbit alternatives.

The executor cannot change station, date, product, mirror set, grid, feature,
calibration split, null, threshold or claim scope. It contains no discovery or
fallback path.

## Frozen source and evidence

- source commit:
  `af293090436468b43737677bd0b0a12dfb84ee0a`;
- source SHA-256:
  `4b7d032c414419c11844a974f97aa9239293557ffc704fa22c03f4525336bc08`;
- executor manifest SHA-256:
  `6748fb3acd8eb65cd868d205420a00841006861f14e904a6bcbeb5318cf3bb87`;
- executor seal canonical SHA-256:
  `130378385487a337e82aa215c083c5b97099162c5361bdf6f9651ce4f84f45b5`;
- primary plan manifest SHA-256:
  `2e7598068db8dd5c4fe27ee881340bb7096b8e878fda0a050048a11a70767055`;
- prediction artifact SHA-256:
  `c45df3e1ca2a18bf52bd7f33e31fceaf6c15a9e83d83d1078c3f092c81cbf15b`;
- prediction seal SHA-256:
  `4e94711d88a9c85c232585db83a3b7192713ba0b4900606076e8c386373c57fa`;
- qualified header-transform SHA-256:
  `7f106a5486ddd05cad12e034b4b7a14c87fc97ad77e77f73f660755c344d09bf`.

All locator-request, HEAD-request, header, payload-byte and value counters are
zero. No primary outcome artifact exists.

## Transport state machine

Retries are transport-only and end before any decode:

- two attempts per frozen mirror and four per product;
- 900 seconds maximum wall clock per product;
- 30-second connection timeout and 180-second idle timeout;
- same-mirror resume only with stable ETag or Last-Modified;
- no resume without a stable validator;
- partial bytes are erased before moving to the next frozen mirror;
- no cross-mirror append;
- both complete-file SHA-256 values must exist before the first decode;
- zero network attempts after both hashes;
- zero retry after header parsing, decoding, admission or scoring.

A failure before complete materialization is
`PRIMARY_ARTIFACT_MATERIALIZATION_FAILED`, never `MEASUREMENT_INVALID` and
never an orbital outcome.

## Measurement and scoring

Admission remains clause-based:

- full 139-epoch 30-second GPS grid at both stations;
- matching DOY217-qualified receiver, antenna and RINEX transforms;
- L1C/L2W on G22 and G30 with zero LLI;
- frozen C1C/C2W same-path coverage and boundary witnesses;
- unchanged geometry-free second-difference health limit;
- no interpolation or gap bridging.

Only after admission is the 137-epoch ionosphere-free double-difference phase
coordinate constructed. The 77-epoch prefix fits only constant and rate. The
60-epoch suffix is compared on the common grid. The pairwise preference guard
remains 3,142.164149 m and the one-model calibration admission limit is its
predeclared half, 1,571.082074 m.

## Stop

The seal explicitly sets `live_execution_authorized_by_seal` to `false`.
Execution requires a separate affirmative review, the exact seal hash and the
one-use DOY223 authority token. Until then ALGO and MDO remain unopened.
