# G22/G30 DOY 219 repeated-pass outcome

Terminal physical outcome:

    ORBITAL_MODEL_REPEATED_PASS_PREFERRED

This is the single frozen DOY 219 execution. No retry, endpoint substitution,
date substitution or reserve fallback occurred. DOY 218 remains sealed.

## Measurement admission

- products: GOLD00USA and NLIB00USA, DOY 219 / 2026-08-07;
- complete artifact bytes: 2,214,151 and 2,510,612;
- each complete artifact was hashed before any decode;
- both headers cover the full frozen window at 30-second cadence;
- 139 raw epochs produced 137 feature epochs;
- all required L1C/L2W phase and LLI fields were present;
- same-path C1C/C2W code coverage was 1.0 on every station/satellite link;
- no blank or trailing-omitted required fields occurred;
- the largest geometry-free phase second difference was
  0.01016484946012497 m, below the frozen 0.09514683639918244 m limit.

The compressed and decoded artifacts existed only in RAM and were erased.
No phase, code, SNR or other observation values were persisted.

## Frozen comparison

The prefix-only constant-plus-rate nuisance was fitted exactly as frozen. Its
orbital-model calibration residual was 0.3591740227655169 m peak-to-peak and
0.10481513975282705 m RMS, within the predeclared
1,188.851495144414 m one-model envelope.

On the independent held-out suffix:

| Hypothesis | Held-out p-p (m) | Held-out RMS (m) |
| --- | ---: | ---: |
| ORBITAL_G22 | 2.268795848255616 | 1.3960371121559516 |
| WRONG_ORBIT_G01 | 8,988.224632404046 | 11,886.887395406222 |
| PREFIX_AFFINE | 11,571.484984297655 | 15,352.58316643476 |
| WRONG_ORBIT_G14 | 59,931.599039070425 | 38,446.766498296245 |
| WRONG_ORBIT_G17 | 121,984.24561981665 | 75,086.20807654297 |

The controlling orbital-versus-runner-up preference is
8,985.955836555791 m, above the frozen 2,377.702990288828 m guard by
6,608.252846266963 m.

## Claim scope

The result advances the exact GOLD/NLIB G22/G30 experiment from a single
prospective held-out preference to repeated-pass consistency across the frozen
DOY 220 primary and DOY 219 replication.

It does not establish catalog-wide GNSS identity, independence from systematics
shared by the same station pair, unconstrained orbit determination or a general
receiver claim. The replication is consumed and must never be retried or
rescored.

## Immutable ledger

- GOLD artifact SHA-256:
  `3902113234d44f33d03d1e9216631beda45a18377d224b44aa7bf0aba5433aeb`;
- NLIB artifact SHA-256:
  `091fa9477491b449f8e9259e83e0529b377123c19b6fd4d8944c816493e401ab`;
- executor seal SHA-256:
  `490f60155dde4972df411d08717462e28b123883e3ef4aea15d708c982208ed6`;
- plan manifest SHA-256:
  `a9c7b00feb9b2fa277e5cd8d71ec22d6726cc4068bf932ef67560b07d68250ed`;
- prediction SHA-256:
  `d408696d5c9d6e446216fdd7bad240a300e4d0d6d27af470756ff7d1413896b0`;
- outcome byte count: 10,056;
- outcome raw and canonical SHA-256:
  `629865857ccc3b17c54db14aefee60fe26eaf9b0c5ded7525c07bcdba30399da`.

Stop here. This outcome closes the repeated-pass experiment. Further work must
ask a new physical question and must not reopen DOY 219 or use DOY 218 as a
retry.
