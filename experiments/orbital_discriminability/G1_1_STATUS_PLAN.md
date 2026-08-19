# Gate G1.1 — frozen status-only qualification plan

## Authority and stop

One execution may read only public descriptive/model metadata. It may not open
a receiver stream or request SND, IQ, waterfall, audio, FFT or spectrum data.
It stops after one terminal status outcome.

## Frozen sources

```text
transmitter metadata:
  https://db.satnogs.org/api/transmitters/?format=json

orbital elements:
  https://celestrak.org/NORAD/elements/gp.php?CATNR={norad}&FORMAT=JSON

capability directory entry:
  http://rx.kiwisdr.com
```

SatNOGS is used only as an already-established transmitter/model root. No
SatNOGS observation, waterfall or station artifact is requested.

## Candidate filter

Before any capability endpoint is considered, select at most five transmitter
descriptions satisfying all of:

- `alive=true`, `status=active`, `unconfirmed=false`;
- exact downlink carrier between 1 and 30 MHz;
- description contains `beacon`, `telemetry`, `TLM` or `sounder`;
- one deterministic description per NORAD identifier.

Each candidate must then have a current CelesTrak OMM document no older than
three days. Metadata age is recorded; it is not converted into emission
certainty or orbital uncertainty.

## Request budget

- zero retry;
- at most five OMM requests;
- one directory request;
- at most twenty `/status` requests, only for endpoints directly materialized
  by the directory response;
- 15-second timeout per request;
- 8 MiB transmitter-catalog limit, 1 MiB directory limit and 256 KiB limit for
  every OMM or status response;
- response bytes are SHA-256 hashed in RAM and destroyed after parsing.

The runner sends only ordinary `User-Agent` and `Accept` headers. If the
directory requires a user gesture, CAPTCHA-like step, cookie, token or custom
authorization header, the runner records `INTERACTION_REQUIRED` and stops. It
must not copy a header from page JavaScript or simulate the gesture.

## Qualification semantics

A successful `/status` response is merely a description. It may materialize
coordinates, a hardware-root identifier, a band and device-health hints. It
does not automatically materialize:

- guaranteed availability through a future pass;
- sample-level event-time semantics and error bound;
- frequency-feature resolution;
- sequence continuity and maximum gap;
- a complete antenna-to-feature transform ledger;
- same-path witnesses preserving the orbital ridge.

Missing fields are `DESCRIPTION_INSUFFICIENT`, not physical rejection.
Transport or parse failures are `QUALIFICATION_ERROR` and prevent a global
claim that no capability exists.

## Terminal outcomes

- `MODEL_METADATA_UNAVAILABLE`;
- `CAPABILITY_DISCOVERY_UNAVAILABLE`;
- `NO_CAPABILITY_DISCOVERED`;
- `CAPABILITY_QUALIFICATION_INCOMPLETE`;
- `NO_CAPABILITY_ADMITTED`;
- `CAPABILITY_DESCRIPTIONS_MATERIALIZED`.

Only the last outcome could proceed to pass-specific G1 admission. None of
these outcomes authorizes RF acquisition.
