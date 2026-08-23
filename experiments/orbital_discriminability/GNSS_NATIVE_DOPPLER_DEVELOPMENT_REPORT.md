# Native Doppler development outcome

Outcome: `NATIVE_DOPPLER_DEVELOPMENT_ENVELOPE_FROZEN`.

This is a development-path result only. It is not an orbital observation and
does not authorize access to DOY 219--221.

## What was actually opened

The exact KIRU and MAT1 DOY 214 artifacts were re-hashed in a fresh quarantine
before decompression. Their byte counts and SHA-256 values matched the prior
qualification receipt. The parser decoded only `D1C`, `D2W`, `C1C`, `S1C`,
`C2W`, and `S2W` for the predeclared G20/G22 pair over all 493 qualified
epochs. It decoded no phase observable. The broadcast-navigation product was
hashed independently before model compilation.

The quarantine contained four files and 19,253,446 bytes and was deleted after
the outcome. No decompressed RINEX, observation scalar, coordinate series, or
per-window series was persisted. DOY 215 remained closed; DOY 219--221 had
zero header and payload access.

## Result

All 114 possible 380-record windows were evaluated. No window was selected
from its measurement value. The controlling window was 16:37:30--19:47:00
GPS.

- Maximum held-out observed-minus-broadcast residual: `1.44001577563781 Hz`
  peak-to-peak.
- RMS in that controlling held-out window: `0.20441706976445329 Hz`.
- Analytic F14.3 Doppler quantization bound after the same prefix-affine
  projection: `0.26269820433436536 Hz` peak-to-peak.
- Provisional development-path envelope: `1.7027139799721753 Hz`.
- Provisional pairwise guard: `3.4054279599443507 Hz`.
- Dispersive network witness: `0.2717166666666344 Hz` peak-to-peak and
  `0.020413556785907148 Hz` RMS.

The frozen shortlist's smallest remaining geometry margin is about 6.743 kHz,
so this development residual is small relative to geometry. That comparison
does **not** yet make a future negative interpretable.

## Why primary is still blocked

The 1.7027 Hz quantity is not a pure receiver error. It contains receiver and
RINEX effects, broadcast-model mismatch, and unresolved path terms for the
development G20/G22 pair. A future G15/G22 run therefore still needs a
separate, outcome-independent model-error scope.

Both stations delivered complete 30 s code/SNR witnesses, but the aggregate
KIRU SNR minimum was only `2.25 dB-Hz` (MAT1: `37.95 dB-Hz`). A single
aggregate minimum cannot justify a post-hoc magnitude threshold, so the
transform manifest deliberately records the future SNR admission threshold as
`UNRESOLVED`, not zero and not 2.25 dB-Hz.

The next bounded task is to freeze a prospective transfer/admission rule that
keeps the same coordinate, requires same-path witness continuity, and treats
future G15/G22 broadcast-model uncertainty separately. Only after that can a
single DOY 219 primary be frozen and separately authorized.
