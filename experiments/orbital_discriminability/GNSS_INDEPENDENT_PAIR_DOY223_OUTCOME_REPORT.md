# ALGO/MDO DOY223 primary outcome

## Terminal outcome

The single authorized execution stopped with:

`MEASUREMENT_INVALID`

Reason:

`HATANAKA_DECODE_FAILED:ALGO00CAN`

Both frozen products reached the transport-complete, full-file-hash boundary
before the first decode. The ALGO byte stream then failed the frozen Hatanaka
decoder. The MDO byte stream was consequently not decoded, measurement
admission did not begin, and the held-out comparison is `NOT_EVALUATED`.

This is not a preference for an orbital model or any frozen null. It does not
show that the planned G22/G30 coordinate was absent or physically invalid.
The receipt cannot distinguish a semantically wrong response body, a damaged
or incompatible compact-RINEX representation, or another decode-boundary
failure. No such cause is inferred after the fact.

## Frozen artifact receipts

| Station | Selected mirror | Attempts | Bytes | SHA-256 |
| --- | --- | ---: | ---: | --- |
| ALGO00CAN | CDDIS, frozen mirror index 1 | 3 | 11,064 | `28566afe3361bdcd2cacb5da83f2cfb5bba25d3ff2234256313df16d337326d1` |
| MDO100USA | CDDIS, frozen mirror index 1 | 3 | 11,064 | `dd6508377b50bb142297a52b52151ba602d6e17d2a8458aa8875861384be9235` |

For both products, the selected-mirror attempt was 1, resume was unused,
cross-mirror append was false, and hashing preceded every decode. Each
selected response exposed a weak ETag. These are transport facts only; they
do not establish that either byte stream was a valid observation product.

## Persistence and authority

- observation values persisted: `0`;
- compressed or decoded observation artifacts persisted: `0`;
- held-out hypotheses evaluated: `0`;
- post-hash network attempts: `0` by the frozen executor contract;
- retry, alternate endpoint, alternate date and second window: forbidden.

The strict-JSON receipt is 1,668 bytes with SHA-256:

`2f8e7f0f4261e32c159d312995f69899f591696f0b0ea6141c40706ce6d9153b`

The DOY223 ALGO/MDO primary is closed. Any future physical experiment must be
separately selected and frozen from orbit-first information; it cannot be a
retry or repair of this primary after observation access.
