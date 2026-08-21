# Cassini SAGR3 distributed header-only qualification

Date: 2026-08-21

Outcome: **`CASSINI_SAGR3_HEADER_TOPOLOGY_QUALIFIED`**

Forward status:
**`BLOCKED_BY_UNMODELED_COORDINATE_TRANSITION_INSIDE_HELDOUT`**

The three predeclared PDS products provide two independent X-band receive
hardware roots and one simultaneous X/Ka same-path witness. All 92,400 SFDU
control headers are complete and continuous. This is a control-path and causal
topology result only: no Data CHDO, IQ, amplitude, or signal-derived field was
requested, decoded, or persisted.

## What the real headers establish

| Role | Real identity | UTC coverage | RSN | Sample mode | RF/IF LO | DDC LO |
|---|---|---|---|---|---:|---:|
| DSS-25 X measurement | SPC 10 / DSS-25 / RSR 3 / A / 1 | 12:00:01–22:30:00 | 1–37800 | complex, 16 bit, 1 ksps | 8.100 GHz | 328 or 331 MHz |
| DSS-25 Ka witness | SPC 10 / DSS-25 / RSR 4 / B / 1 | 12:00:01–22:30:00 | 1–37800 | complex, 16 bit, 1 ksps | 31.700 GHz | 326 or 336 MHz |
| DSS-65 X measurement | SPC 60 / DSS-65 / RSR 3 / A / 1 | 12:00:01–16:40:00 | 0–16799 | complex, 16 bit, 1 ksps | 8.100 GHz | 328 or 330 MHz |

Every event-time step is exactly one second and every RSN step is one modulo
65,536. Frequency and phase polynomial coefficients are finite on every
record; frequency override is always false. The declared filter path is
16 Msps to 1 ksps, decimation 16,000. FIR coefficients are not encoded, so no
amplitude-response claim is authorized.

The ordered strict-JSON whitelist digests are:

- DSS-25 X: `8bfd1427a54da1f3a5b2bff981e0d440dcf59f0e75bae326dc18d64c1c37be69`;
- DSS-25 Ka: `f8749d8ec911f226f7aa43068a2662ba82114a719d96323efdcf3c2efc508d7a`;
- DSS-65 X: `33eb2f2fdc046f8883c9705c397914f62a76e12c22f8c06dcf546684858bea7f`.

## Causal topology

DSS-25 and DSS-65 are independent receive hardware roots for the distributed
X observable. DSS-25 X and Ka are genuinely simultaneous but use RSR 3/A and
RSR 4/B respectively. They are distinct receiver branches through one station,
not a third geographic root.

All three share the DSS-14 X uplink, Cassini coherent transponder, and the
interplanetary path before Earth-near divergence. The Ka branch may later
witness dispersive structure, but headers alone do not prove that a carrier is
present in either band.

## The unexpected coordinate transition

The raw NCO polynomial is not the complete frequency coordinate. The documented
inverse transform is:

```text
recorded baseband = sky - RF/IF LO - DDC LO + NCO
```

Each stream has exactly one DDC change. A bounded binary search localized all
three to the same next-SFDU event time:

| Stream | DDC before → after | Combined coordinate step |
|---|---:|---:|
| DSS-25 X | 328 → 331 MHz | −2,711,938.554554 Hz |
| DSS-25 Ka | 326 → 336 MHz | −10,305,404.583321 Hz |
| DSS-65 X | 328 → 330 MHz | −2,711,933.352047 Hz |

The transition occurs at `2006-09-08T14:57:32.000000Z`, record index 10,651
in each product. It falls after the 3,360-record calibration prefix and inside
the frozen 13,440-record held-out suffix of the distributed geometry screen.

The headers demonstrate a coordinated receiver-coordinate transition. They do
not establish whether its cause is an uplink/ramp change, spacecraft link-mode
change, receiver command, or another mechanism. Assigning any such cause would
be post-hoc inference without evidence.

## Access audit

The authoritative scan read 24,024,000 header bytes. The transition locator
read 15,340 additional header bytes. Earlier in the spike, one description
error consumed 26,000 header bytes and the pre-ledger-correction full scan read
24,024,000 header bytes. Across all attempts, 48,089,340 bytes from SFDU header
ranges were read; Data CHDO bytes requested/read remained exactly zero. No raw
header was written to disk.

The first error came from incorrectly treating the numeric source-product
suffix as the RSR ID. It was corrected as a descriptive-lineage defect before
the authoritative scan; the real RSR IDs come only from SFDU byte 44.

## What is and is not authorized

Authorized:

- complete control-header continuity;
- actual sample and receiver configuration;
- the two-root X topology;
- the distinct DSS-25 X/Ka witness topology;
- an exact piecewise frequency-coordinate ledger;
- the simultaneous coordinate-transition time.

Not authorized:

- the physical cause of the transition;
- carrier presence or detectability;
- an amplitude or FIR-response claim;
- a physical correction margin;
- detector or IQ access;
- orbital-model preference or Cassini identity evidence.

## Exact remaining blocker

The constant-carrier distributed screen cannot simply be compiled through the
entire held-out suffix because a large coordinated coordinate transition lies
inside it. Before any IQ access, the smallest physical next step is strictly
offline and metadata-only:

1. obtain outcome-independent link-mode/uplink-ramp provenance that explains
   the exact transition and can be applied identically to nominal and null
   models; or
2. predeclare a shorter pre-transition calibration/holdout interval, then
   rerun the geometric discriminability and correction envelope honestly.

If neither retains positive margin, this three-product path must be closed.

## Official product labels

- [DSS-25 X](https://atmos.nmsu.edu/PDS/data/PDS4/cassini-rss-raw-sagr/data-rsr01/2006/s23sags2006_251_1200x14x25rd.xml)
- [DSS-25 Ka](https://atmos.nmsu.edu/PDS/data/PDS4/cassini-rss-raw-sagr/data-rsr01/2006/s23sags2006_251_1200x14k25rd.xml)
- [DSS-65 X](https://atmos.nmsu.edu/PDS/data/PDS4/cassini-rss-raw-sagr/data-rsr01/2006/s23sags2006_251_1200x14x65rd.xml)
