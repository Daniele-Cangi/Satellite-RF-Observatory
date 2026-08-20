# RSP-03 closing audit

Status: **`BLOCKED_BY_ABSOLUTE_TIME_PROVENANCE`**

This is a closing audit inside the existing forward experiment, not a new
gate.  It does not alter the prospective plan, detector, dataset roles,
structural plan hash, primary metadata hash, or detector-manifest hash.  The
2026-02-09 primary IQ and 2026-02-13 replication reserve remain unopened.  The
primary IQ SHA-256 therefore remains deliberately **`UNMATERIALIZED`**.

## Frozen facts retained

- detector manifest SHA-256:
  `e72d62bee6844c6677f85ef50af02f088511b6788371f54f0933b7bc5acecddc`;
- primary role: `PRIMARY_HELD_OUT`, expected byte count `1,869,440,000`,
  preserved metadata SHA-256
  `0826fd8e6447d25a002697609e520ef152dc57a0cb787607aedbf99f9aa9d48c`;
- reserve role: `SEALED_REPLICATION_RESERVE`;
- with effective detector resolution `R_f = 250 Hz`, the frozen direct timing
  envelope leaves positive detectability through integer `B_t = 59 s`
  (`+145.639 Hz`) and becomes negative at `B_t = 60 s` (`-72.168 Hz`);
- replacing `B_t` with a free phase is inadmissible and does not repair the
  experiment: across the audited `[-600 s, +600 s]` phase range, 942 shifts
  are calibration-compatible at half the effective resolution (`125 Hz`),
  while their held-out predictions diverge by as much as approximately
  `14.8 kHz` (`14,768.407 Hz` in the frozen numerical audit).

## Timing-provenance finding

Public `vrt-iq-tools` commit
[`495e96ae`](https://github.com/tftelkamp/vrt-iq-tools/commit/495e96ae9aacc97a3892bdc17537446c50f9371d)
is dated 2026-08-03, after the 2026-02 recordings.  It is retained only as
**post-recording mechanism documentation**, not provenance for the deployed
binary.  The latest public pre-recording source inspected,
[`8a349812`](https://github.com/tftelkamp/vrt-iq-tools/blob/8a349812f7eb79c31b81dec2b796dceb6152e04b/usrp_to_vrt.cpp#L798-L825),
latches USRP time from host `gettimeofday()` at PPS and checks integer-second
agreement; it does not bound host UTC error.  The matching SigMF writer would
emit `vrt:cal_time` when timestamp calibration is present, but that field is
absent from the preserved sidecar.  No source inspected establishes which
binary/configuration ran or a finite timestamp-to-ADC error for this capture.

## Closure

RSP-03 cannot produce an interpretable negative under its frozen plan until a
same-path, recording-applicable absolute-time bound is supplied.  No timing
number is inferred from the PPS label, filename, HTTP date, observation
schedule, orbital fit, or ridge.  Primary access cannot repair this missing
pre-observation fact, so both sealed IQ roles remain closed.
