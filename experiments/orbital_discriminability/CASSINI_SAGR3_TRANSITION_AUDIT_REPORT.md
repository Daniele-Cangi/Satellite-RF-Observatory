# Cassini SAGR3 coordinate-transition audit

Date: 2026-08-21

Full held-out status:
**BLOCKED_BY_UNMODELED_COORDINATE_TRANSITION_INSIDE_HELDOUT**

Pre-transition screen:
**CASSINI_SAGR3_PRETRANSITION_GEOMETRY_SCREEN_POSITIVE**, but **not
physically admitted**.

This bounded audit asked whether outcome-independent DSN metadata explains the
simultaneous receiver-coordinate transition at
**2006-09-08T14:57:32.000000Z**, or whether a strictly pre-transition interval
retains geometric discriminability. It accessed no RSR Data CHDO, IQ,
amplitude, signal diagnostic, or detector input.

## Metadata boundary

The only new binary bytes admitted were ODF records 201,366 through 201,425:
the four ramp groups for DSS-14, DSS-25, DSS-43, and DSS-65. The 2,160-byte
range has SHA-256
**136774e5b55002c2f5c78b614048b9177d14b3fb1215e4c59e39909745de485a**.
The ODF orbit-observable group and TNF tracking observables remained outside
scope. The frozen ramp parser manifest has SHA-256
**88adac47b77c2c9f7543a8ab42e150340a4bbbdd6c0852d56412d9638328f974**.

The PDS label describes ramp groups as station-ordered transmitter/receiver
tuning metadata. This makes the slice independent of target RF amplitude, but
not a pre-pass command log and not evidence of spacecraft lock state.

## What the ramp proves

Solving the two one-way light times from the common receive transition maps the
event to these uplink transmit epochs:

| Receive root | Spacecraft turnaround UTC | DSS-14 transmit UTC |
|---|---:|---:|
| DSS-25 | 13:33:59.788451 | 12:10:27.105870 |
| DSS-65 | 13:33:59.783705 | 12:10:27.101124 |

Both epochs fall inside the same DSS-14 ramp segment,
**12:10:15–12:11:21 UTC**, with rate **-152.324419999 Hz/s** and start
frequency **7174544992.57448 Hz**.

This establishes temporal compatibility. It does **not** establish that the
ramp caused the simultaneous DDC/NCO coordinate transition. The bounded
official metadata search found no explicit transponder-lock, link-mode, or
receiver-command event at the transition. The physical cause therefore remains
**UNRESOLVED**. The full held-out suffix cannot be compiled through the jump
without adding an outcome-conditioned explanation.

## Pre-transition geometric rerun

The coordinate boundary itself was selected from control headers before any IQ
access. The rerun keeps records 0–10,650: 3,360 frozen calibration records and
7,291 held-out records, ending at **14:57:31 UTC**. It uses the same exact-hash
LSK, PCK, station SPK, and pre-pass PREDICT spacecraft SPK as the distributed
screen. Manifest SHA-256:
**9d934499335f1ab0082f8173adead3b232d9820ed52076ff159b11c3b56d99bc**.

Joint visibility holds throughout:

| Station | Minimum elevation | Maximum elevation |
|---|---:|---:|
| DSS-25 | 8.280999° | 44.328114° |
| DSS-65 | 28.408368° | 59.354745° |

The geometry-only results are:

- raw distributed orbital span: **2731.3926883210 Hz**;
- affine-baseband null held-out span: **3266.4544576922 Hz**;
- controlling Saturn-center geometry-destroying residual:
  **0.0723137006 Hz** peak-to-peak and **0.0573667586 Hz** RMS;
- two-stream, two-sided 100 ns timing envelope: **0.0000074829 Hz**;
- best-case three-bin detector-resolution ceiling:
  **0.0241020726 Hz**.

The controlling separation is positive, but it is 76.7% smaller than the
**0.3098298838 Hz** full-window geometry-only value. Shortening the interval did
not rescue physical admission; it exposed a substantially tighter instrument
and correction budget.

## Claims and stop condition

Authorized:

- the three receiver-coordinate transitions are simultaneous on the RSR
  server-time grid;
- the two inferred uplink epochs fall within one common DSS-14 ramp segment;
- the pre-transition interval retains positive geometry-only separation from
  every frozen null.

Not authorized:

- that the ramp caused the coordinate transition;
- that Cassini changed link mode or lock state at that instant;
- that a carrier is present or detectable;
- that the pre-transition interval is ready for detector or IQ access;
- any RF-based orbital preference or identity claim.

The exact remaining blocker is
**PRETRANSITION_PHYSICAL_CORRECTION_ENVELOPE**. The next physical decision, if
authorized separately, is whether outcome-independent media, clock, hardware,
and USO bounds fit inside the new **0.0723137006 Hz** margin. This audit stops
before that work and before all IQ access.

## Official sources

- [Cassini RSS archive description](https://atmos.nmsu.edu/data_and_services/atmospheres_data/Cassini/inst-rss_curr.html)
- [PDS3 SAGR3 volume](https://atmos.nmsu.edu/pdsd/archive/data/co-s-rss-1-sagr3-v10/cors_0147/)
- [PDS4 ODF label](https://atmos.nmsu.edu/PDS/data/PDS4/cassini-rss-raw-sagr/data-odf/2006/s23sags2006_251_1151x14v1.xml)
